"""
Part 5 - Modelling & validation (BFT65B)

Design (all choices are made on the development period 1984-2006 only):
  * Validation: expanding-window, time-ordered cross-validation with a one-year
    gap between training and validation (labels look 4 quarters ahead, so the
    gap stops training labels from overlapping the validation years).
    The preprocessing pipeline is re-fitted inside every fold (train part only).
  * Metrics for rare events: PR-AUC (average precision) is the main metric;
    ROC-AUC and recall among the top 1% / 5% riskiest bank-quarters are also
    reported. Accuracy is NOT used (predicting "no failure" for everyone already
    gives 99.1% accuracy on dev).
  * Models: (1) baseline = simple capital rule (lower equity/assets = riskier),
    (2) logistic regression, (3) histogram gradient boosting (3 settings tuned
    by mean validation PR-AUC).
  * Alarm threshold: minimise expected cost C_FN*FN + C_FP*FP on the out-of-fold
    dev predictions. C_FN = median FDIC resolution cost of dev-period failures
    (from the data); C_FP = cost of one extra examination (not in the data:
    assumed, with a sensitivity analysis).
  * The chosen model is re-fitted on all dev data and evaluated ONCE on the
    test period 2008Q1-2025Q2.

Run from the project root:
    python -X utf8 src/07_model.py
"""

import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline_def import DEV_END, FEATURES, build_preprocessor  # noqa: E402

MODEL_TABLE = ROOT / "data" / "processed" / "model_table.parquet"
FAILURES = ROOT / "data" / "processed" / "failures_clean.parquet"
PREP_FILE = ROOT / "data" / "processed" / "preprocessor.joblib"
OUT_TAB = ROOT / "output" / "tables"
OUT_FIG = ROOT / "output" / "figures"
SEED = 42

# (last training year, first validation year, last validation year); one gap year in between
FOLDS = [(1986, 1988, 1989), (1988, 1990, 1991), (1990, 1992, 1993), (1992, 1994, 2000), (1999, 2001, 2006)]
HGB_GRID = {
    "hgb_small": dict(learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100, l2_regularization=1.0),
    "hgb_medium": dict(learning_rate=0.1, max_leaf_nodes=31, min_samples_leaf=100, l2_regularization=1.0),
    "hgb_large": dict(learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0),
}
C_FP_BASE = 100.0                     # thousand USD per false alarm (assumption, see report)
C_FP_GRID = [25.0, 50.0, 100.0, 250.0, 500.0, 1000.0]


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def to_markdown(df):
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in df.iter_rows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:,.4f}" if abs(v) < 10 else f"{v:,.0f}")
            else:
                cells.append("" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def make_model(name):
    if name == "logistic":
        return LogisticRegression(max_iter=2000, C=1.0)
    return HistGradientBoostingClassifier(max_iter=200, early_stopping=False, random_state=SEED, **HGB_GRID[name])


def capital_rule_score(X, train_median):
    """Baseline: risk = minus equity/assets; a missing value gets the TRAINING median."""
    eq = X[:, FEATURES.index("F_EQ_TA")]
    return -np.where(np.isnan(eq), train_median, eq)


def metrics(y, s):
    order = np.argsort(-s)
    out = {"pr_auc": float(average_precision_score(y, s)), "roc_auc": float(roc_auc_score(y, s))}
    for k in (0.01, 0.05):
        top = order[: max(1, int(len(s) * k))]
        out[f"recall_top{int(k * 100)}pct"] = float(y[top].sum() / max(1, y.sum()))
    return out


def cost_curve(y, s, c_fn, c_fp):
    """Expected cost for every possible threshold (flag all rows with score >= t)."""
    order = np.argsort(-s, kind="mergesort")
    ys, ss = y[order], s[order]
    tp = np.cumsum(ys)
    fp = np.cumsum(1 - ys)
    last_of_tie = np.r_[ss[1:] != ss[:-1], True]           # evaluate only where the score changes
    tp, fp, thr = tp[last_of_tie], fp[last_of_tie], ss[last_of_tie]
    fn = y.sum() - tp
    return thr, tp, fp, fn, c_fn * fn + c_fp * fp


def best_threshold(y, s, c_fn, c_fp):
    thr, tp, fp, fn, cost = cost_curve(y, s, c_fn, c_fp)
    i = int(np.argmin(cost))
    pos = int(y.sum())
    return {"threshold": float(thr[i]), "cost": float(cost[i]), "tp": int(tp[i]), "fp": int(fp[i]),
            "fn": int(fn[i]), "alarm_rate": float((tp[i] + fp[i]) / len(y)), "recall": float(tp[i] / max(1, pos)),
            "precision": float(tp[i] / max(1, tp[i] + fp[i]))}


def main():
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()
    tab = pl.read_parquet(MODEL_TABLE)
    dev = tab.filter(pl.col("SPLIT") == "dev")
    test = tab.filter(pl.col("SPLIT") == "test")
    X_dev, y_dev = dev.select(FEATURES).to_numpy().astype("float64"), dev["Y"].to_numpy().astype(int)
    yr_dev = dev["YEAR"].to_numpy()
    X_test, y_test = test.select(FEATURES).to_numpy().astype("float64"), test["Y"].to_numpy().astype(int)
    log(f"dev {len(y_dev):,} rows ({y_dev.sum():,} positive) | test {len(y_test):,} rows ({y_test.sum():,} positive)")
    md = ["# Part 5 - Modelling and validation", f"Generated {datetime.now():%Y-%m-%d %H:%M}", "",
          f"Accuracy of the trivial 'no failure' prediction on dev: {1 - y_dev.mean():.4%} "
          "(this is why accuracy is not used).", ""]

    # ------------------------------------------------------------ 1. time-ordered CV on dev
    models = ["capital_rule", "logistic"] + list(HGB_GRID)
    oof = {m: np.full(len(y_dev), np.nan) for m in models}
    cv_rows = []
    for k, (tr_end, va_start, va_end) in enumerate(FOLDS, 1):
        tr = yr_dev <= tr_end
        va = (yr_dev >= va_start) & (yr_dev <= va_end)
        log(f"Fold {k}: train 1984-{tr_end} ({tr.sum():,} rows) | gap {tr_end + 1}-{va_start - 1} | "
            f"validate {va_start}-{va_end} ({va.sum():,} rows, {y_dev[va].sum()} positive)")
        med_tr = float(np.nanmedian(X_dev[tr][:, FEATURES.index("F_EQ_TA")]))
        oof["capital_rule"][va] = capital_rule_score(X_dev[va], med_tr)
        for m in models[1:]:
            t0 = time.perf_counter()
            pipe = Pipeline([("prep", build_preprocessor()), ("model", make_model(m))])
            pipe.fit(X_dev[tr], y_dev[tr])                       # preprocessing fitted on the training fold only
            oof[m][va] = pipe.predict_proba(X_dev[va])[:, 1]
            log(f"   {m}: {time.perf_counter() - t0:.0f} s")
        for m in models:
            cv_rows.append({"fold": k, "validation_years": f"{va_start}-{va_end}", "model": m,
                            "positives": int(y_dev[va].sum()), **metrics(y_dev[va], oof[m][va])})
    cv = pl.DataFrame(cv_rows)
    cv.write_csv(OUT_TAB / "part5_cv_by_fold.csv")
    covered = ~np.isnan(oof["logistic"])
    cv_mean = (cv.group_by("model").agg(pl.col("pr_auc").mean().alias("mean_pr_auc"),
                                        pl.col("pr_auc").std().alias("sd_pr_auc"),
                                        pl.col("roc_auc").mean().alias("mean_roc_auc"),
                                        pl.col("recall_top5pct").mean().alias("mean_recall_top5pct"))
               .sort("mean_pr_auc", descending=True))
    pooled = pl.DataFrame([{"model": m, **metrics(y_dev[covered], oof[m][covered])} for m in models])
    cv_mean = (cv_mean.join(pooled.select(["model", pl.col("pr_auc").alias("pooled_oof_pr_auc")]), on="model")
               .sort("mean_pr_auc", descending=True))   # re-sort: a join does not keep row order
    cv_mean.write_csv(OUT_TAB / "part5_cv_summary.csv")
    best_hgb = cv_mean.filter(pl.col("model").str.starts_with("hgb"))["model"][0]
    chosen = cv_mean["model"][0]
    log("CV summary:\n" + to_markdown(cv_mean))
    md += ["## Time-ordered cross-validation on dev (expanding window, 1-year gap)",
           to_markdown(cv), "", "### Mean over folds (model chosen by mean PR-AUC)", to_markdown(cv_mean), "",
           f"Best gradient-boosting setting: **{best_hgb}**. Model chosen for the test: **{chosen}**.", ""]

    # ------------------------------------------------------------ 2. costs and threshold (dev only)
    fail = pl.read_parquet(FAILURES)
    dev_cost = fail.filter((pl.col("FAIL_DT") >= date(1984, 1, 1)) & (pl.col("FAIL_DT") <= date(2007, 12, 31))
                           & pl.col("COST").is_not_null())["COST"]
    c_fn = float(dev_cost.median())
    log(f"C_FN = median resolution cost of {dev_cost.len():,} dev-period failures = {c_fn:,.0f} thousand USD")
    s_oof = oof[chosen][covered]
    y_oof = y_dev[covered]
    sens = []
    for c_fp in C_FP_GRID:
        b = best_threshold(y_oof, s_oof, c_fn, c_fp)
        sens.append({"C_FP_thousand_usd": c_fp, "cost_ratio_FN_FP": c_fn / c_fp, **b})
    sens_df = pl.DataFrame(sens)
    sens_df.write_csv(OUT_TAB / "part5_threshold_sensitivity.csv")
    thr = next(r for r in sens if r["C_FP_thousand_usd"] == C_FP_BASE)
    md += ["## Alarm threshold from costs (chosen on out-of-fold dev predictions only)",
           f"C_FN (missed failure) = median FDIC resolution cost of {dev_cost.len():,} failures in 1984-2007 "
           f"= **{c_fn:,.0f} thousand USD** (from the data). C_FP (false alarm) = one extra examination, "
           f"assumed **{C_FP_BASE:,.0f} thousand USD** (not in the data), with a sensitivity analysis:",
           to_markdown(sens_df), "",
           f"Base-case threshold: **{thr['threshold']:.4f}** (alarm rate {thr['alarm_rate']:.2%} of bank-quarters).", ""]

    # ------------------------------------------------------------ 3. final fit on all dev, ONE test evaluation
    prep = joblib.load(PREP_FILE)                     # fitted on all dev in Part 4
    Z_dev, Z_test = prep.transform(X_dev), prep.transform(X_test)
    finals = {}
    for m in ["logistic", best_hgb]:
        t0 = time.perf_counter()
        finals[m] = make_model(m).fit(Z_dev, y_dev)
        log(f"Final {m} fitted on all dev in {time.perf_counter() - t0:.0f} s")
        joblib.dump(finals[m], ROOT / "data" / "processed" / f"model_{m}.joblib")
    med_dev = float(np.nanmedian(X_dev[:, FEATURES.index("F_EQ_TA")]))
    s_test = {"capital_rule": capital_rule_score(X_test, med_dev),
              "logistic": finals["logistic"].predict_proba(Z_test)[:, 1],
              best_hgb: finals[best_hgb].predict_proba(Z_test)[:, 1]}
    test_rows = [{"model": m + (" (chosen)" if m == chosen else ""), **metrics(y_test, s)} for m, s in s_test.items()]
    y_fo = test["Y_FAILURE_ONLY"].to_numpy().astype(int)
    for r, (m, s) in zip(test_rows, s_test.items()):
        r["pr_auc_closures_only"] = float(average_precision_score(y_fo, s))
    test_df = pl.DataFrame(test_rows)
    test_df.write_csv(OUT_TAB / "part5_test_metrics.csv")

    s = s_test[chosen]
    alarm = s >= thr["threshold"]
    tp = int((alarm & (y_test == 1)).sum()); fp = int((alarm & (y_test == 0)).sum())
    fn = int(((~alarm) & (y_test == 1)).sum()); tn = int(((~alarm) & (y_test == 0)).sum())
    late = test["LATE_SIGNAL"].to_numpy()
    ev = test.select(["CERT", "NEXT_EVENT_DT", "Y"]).with_columns(pl.Series("ALARM", alarm),
                                                                  pl.Series("LATE", late))
    ev = ev.filter(pl.col("Y") == 1).group_by(["CERT", "NEXT_EVENT_DT"]).agg(
        pl.col("ALARM").any().alias("flagged"),
        (pl.col("ALARM") & ~pl.col("LATE")).any().alias("flagged_in_time"))
    conf = {"threshold": thr["threshold"], "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "recall": tp / max(1, tp + fn), "precision": tp / max(1, tp + fp),
            "alarm_rate": float(alarm.mean()),
            "recall_excluding_late_signal_rows": float((alarm & (y_test == 1) & ~late).sum()
                                                       / max(1, ((y_test == 1) & ~late).sum())),
            "failure_events": ev.height, "events_flagged_at_least_once": int(ev["flagged"].sum()),
            "events_flagged_by_a_timely_row": int(ev["flagged_in_time"].sum()),
            "expected_cost_model": c_fn * fn + C_FP_BASE * fp,
            "expected_cost_no_alarm": c_fn * int(y_test.sum()),
            "expected_cost_alarm_all": C_FP_BASE * int((y_test == 0).sum())}
    (OUT_TAB / "part5_test_confusion.json").write_text(json.dumps(conf, indent=2), encoding="utf-8")
    log("Test metrics:\n" + to_markdown(test_df))
    log("Confusion at cost threshold: " + json.dumps(conf))

    by_year = (test.select(["YEAR", "Y"]).with_columns(pl.Series("score", s), pl.Series("ALARM", alarm))
               .group_by("YEAR").agg(pl.len().alias("rows"), pl.col("Y").sum().alias("positives"),
                                     (pl.col("ALARM") & (pl.col("Y") == 1)).sum().alias("tp"),
                                     pl.col("ALARM").sum().alias("alarms"))
               .with_columns((pl.col("tp") / pl.col("positives")).alias("recall")).sort("YEAR"))
    by_year.write_csv(OUT_TAB / "part5_test_by_year.csv")

    # feature importance proxy for the logistic model (standardised coefficients)
    try:
        names = list(prep.get_feature_names_out(FEATURES))
    except Exception:
        names = None
    coef = finals["logistic"].coef_[0]
    if names is None or len(names) != len(coef):
        names = FEATURES + [f"missing_flag_{i}" for i in range(len(coef) - len(FEATURES))]
    coef_df = pl.DataFrame({"term": names, "std_coefficient": coef}).with_columns(
        pl.col("std_coefficient").abs().alias("abs")).sort("abs", descending=True).drop("abs")
    coef_df.write_csv(OUT_TAB / "part5_logistic_coefficients.csv")

    md += ["## Single evaluation on the test period (2008Q1-2025Q2)",
           "Models re-fitted on all dev data; preprocessing = the Part 4 pipeline fitted on dev only.",
           to_markdown(test_df), "",
           f"### Chosen model ({chosen}) at the cost-based threshold",
           "```", json.dumps(conf, indent=2), "```", "",
           "### Test results by year", to_markdown(by_year), "",
           "### Logistic regression: standardised coefficients (top 15)", to_markdown(coef_df.head(15)), ""]

    # ------------------------------------------------------------ 4. figures
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        for m in models:
            if m in ("capital_rule", "logistic", best_hgb):
                p, r, _ = precision_recall_curve(y_oof, oof[m][covered])
                axes[0].plot(r, p, label=f"{m} (AP {average_precision_score(y_oof, oof[m][covered]):.3f})")
        axes[0].axhline(y_oof.mean(), color="grey", ls="--", lw=0.8, label="random")
        axes[0].set_title("Dev, out-of-fold (1988-2006)")
        for m, sc in s_test.items():
            p, r, _ = precision_recall_curve(y_test, sc)
            axes[1].plot(r, p, label=f"{m} (AP {average_precision_score(y_test, sc):.3f})")
        axes[1].axhline(y_test.mean(), color="grey", ls="--", lw=0.8, label="random")
        axes[1].scatter([conf["recall"]], [conf["precision"]], color="black", zorder=5, label="cost threshold")
        axes[1].set_title("Test, single evaluation (2008-2025Q2)")
        for ax in axes:
            ax.set_xlabel("Recall"); ax.set_ylabel("Precision"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            ax.legend(fontsize=8)
        fig.suptitle("Figure 7. Precision-recall curves")
        fig.tight_layout()
        fig.savefig(OUT_FIG / "part5_pr_curves.png", dpi=200)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4.2))
        for c_fp in (50.0, 100.0, 250.0):
            thr_c, tp_c, fp_c, fn_c, cost_c = cost_curve(y_oof, s_oof, c_fn, c_fp)
            rate = (tp_c + fp_c) / len(y_oof) * 100
            keep = rate <= 20
            ax.plot(rate[keep], cost_c[keep] / 1e6, label=f"C_FP = {c_fp:,.0f}k USD")
        ax.set_xlabel("Alarm rate (% of bank-quarters flagged)")
        ax.set_ylabel("Expected cost (billion USD, dev OOF)")
        ax.set_title("Figure 8. Expected cost vs alarm rate (dev, out-of-fold)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT_FIG / "part5_cost_curve.png", dpi=200)
        plt.close(fig)
    except ImportError:
        pass

    # data for the Spark MLlib demo (one small file to upload to Colab)
    (tab.filter(pl.col("SPLIT").is_in(["dev", "test"])).select(["SPLIT", "Y"] + FEATURES)
        .write_parquet(ROOT / "data" / "processed" / "mllib_input.parquet", compression="zstd"))
    (OUT_TAB / "part5_report.md").write_text("\n".join(md), encoding="utf-8")
    log(f"DONE in {(time.perf_counter() - t_start) / 60:.1f} min. Report: output/tables/part5_report.md")


if __name__ == "__main__":
    main()