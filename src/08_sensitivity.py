"""
Part 4-5 sensitivity checks (BFT65B) - DEVELOPMENT PERIOD ONLY (1984-2006).
The test period is never used in this script.

  1. Signed stand-alone ROC-AUC: each feature is multiplied by its expected sign
     from banking theory, so AUC > 0.5 confirms the sign (Figure 6, Table C1).
  2. Closures-only label: the chosen model (hgb_large) and the capital rule are
     re-run in the same time-ordered CV with a label that counts FDIC closures
     only (assistance events = 0). Model choice, threshold and test results of
     07_model.py are NOT changed.

Run from the project root (after 07_model.py):
    python -X utf8 src/08_sensitivity.py
"""

import importlib
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline_def import FEATURES, build_preprocessor  # noqa: E402

m07 = importlib.import_module("07_model")   # reuse folds, models and metrics (its main() is not run)

OUT_TAB = ROOT / "output" / "tables"
OUT_FIG = ROOT / "output" / "figures"
CHOSEN = "hgb_large"                        # model chosen in 07_model.py (fixed, not re-selected)

# Expected sign (Appendix C): +1 = higher value -> higher risk, -1 = lower value -> higher risk,
# 0 = no sign expected in advance (asset growth: fast growth and shrinking can both signal risk)
SIGN = {
    "F_EQ_TA": -1, "F_LEV_RATIO": -1, "F_EQ_TA_CHG_4Q": -1, "F_EQ_TA_PCTRANK": -1,
    "F_NPL": 1, "F_RES_LN": 1, "F_PROV_LN": 1, "F_NCO_LN": 1, "F_ORE_TA": 1,
    "F_NPL_CHG_1Q": 1, "F_NPL_PCTRANK": 1,
    "F_TA_GROWTH_4Q": 0,
    "F_ROA_Q": -1, "F_NIM_Q": -1, "F_ROA_4Q_AVG": -1, "F_ROA_VS_MEDIAN": -1,
    "F_LIQ": -1, "F_BRO_DEP": 1, "F_LN_DEP": 1,
    "F_LOG_TA": -1,
}
CAMELS = {
    "F_EQ_TA": "C", "F_LEV_RATIO": "C", "F_EQ_TA_CHG_4Q": "C", "F_EQ_TA_PCTRANK": "C",
    "F_NPL": "A", "F_RES_LN": "A", "F_PROV_LN": "A", "F_NCO_LN": "A", "F_ORE_TA": "A",
    "F_NPL_CHG_1Q": "A", "F_NPL_PCTRANK": "A",
    "F_TA_GROWTH_4Q": "M",
    "F_ROA_Q": "E", "F_NIM_Q": "E", "F_ROA_4Q_AVG": "E", "F_ROA_VS_MEDIAN": "E",
    "F_LIQ": "L", "F_BRO_DEP": "L", "F_LN_DEP": "L",
    "F_LOG_TA": "Size",
}
COLORS = {"C": "#3b6ea5", "A": "#c0504d", "M": "#9bbb59", "E": "#f79646", "L": "#8064a2", "Size": "#7f7f7f"}


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def signed_auc(X, y):
    rows = []
    for j, f in enumerate(FEATURES):
        ok = ~np.isnan(X[:, j])
        direction = SIGN[f] if SIGN[f] != 0 else 1        # no prior sign: report the raw direction
        auc = float(roc_auc_score(y[ok], direction * X[ok, j]))
        rows.append({"feature": f, "camels": CAMELS[f],
                     "expected_sign": {1: "+", -1: "-", 0: "none"}[SIGN[f]],
                     "signed_auc": auc,
                     "sign_confirmed": "n/a" if SIGN[f] == 0 else ("yes" if auc > 0.5 else "no"),
                     "old_max_auc": max(auc, 1 - auc),            # equals the value in the old Table C1
                     "non_missing_rows": int(ok.sum())})
    return pl.DataFrame(rows).sort("signed_auc", descending=True)


def plot_auc(auc_df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = auc_df.sort("signed_auc")
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(d["feature"].to_list(), d["signed_auc"].to_list(),
            color=[COLORS[c] for c in d["camels"].to_list()])
    ax.axvline(0.5, color="black", ls="--", lw=0.8)
    ax.set_xlim(0, 1)
    ax.set_xlabel("ROC-AUC with the feature oriented by its expected sign (> 0.5 = sign confirmed)")
    ax.set_title("Figure 6. Stand-alone strength of each feature (dev 1984-2006 only)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=v) for v in COLORS.values()]
    ax.legend(handles, list(COLORS), title="CAMELS", loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_FIG / "part4_feature_auc_signed.png", dpi=200)
    plt.close(fig)


def closures_only_cv(X, y_fo, yr):
    rows = []
    for k, (tr_end, va_start, va_end) in enumerate(m07.FOLDS, 1):
        tr = yr <= tr_end
        va = (yr >= va_start) & (yr <= va_end)
        med_tr = float(np.nanmedian(X[tr][:, FEATURES.index("F_EQ_TA")]))
        t0 = time.perf_counter()
        pipe = Pipeline([("prep", build_preprocessor()), ("model", m07.make_model(CHOSEN))])
        pipe.fit(X[tr], y_fo[tr])                     # preprocessing fitted on the training fold only
        scores = {"capital_rule": m07.capital_rule_score(X[va], med_tr),
                  CHOSEN: pipe.predict_proba(X[va])[:, 1]}
        log(f"Fold {k} ({va_start}-{va_end}): {int(y_fo[va].sum())} closure-positive rows, "
            f"{time.perf_counter() - t0:.0f} s")
        for name, s in scores.items():
            rows.append({"fold": k, "validation_years": f"{va_start}-{va_end}", "model": name,
                         "positives": int(y_fo[va].sum()), "positive_rate": float(y_fo[va].mean()),
                         **m07.metrics(y_fo[va], s)})
    return pl.DataFrame(rows)


def main():
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()
    missing = [f for f in FEATURES if f not in SIGN]
    assert not missing, f"No expected sign defined for: {missing}"

    dev = pl.read_parquet(m07.MODEL_TABLE).filter(pl.col("SPLIT") == "dev")   # test rows are dropped here
    assert dev["Y_FAILURE_ONLY"].null_count() == 0, "Y_FAILURE_ONLY has missing values on dev"
    X = dev.select(FEATURES).to_numpy().astype("float64")
    y = dev["Y"].to_numpy().astype(int)
    y_fo = dev["Y_FAILURE_ONLY"].to_numpy().astype(int)
    yr = dev["YEAR"].to_numpy()
    log(f"dev {len(y):,} rows | positives: main label {y.sum():,}, closures only {y_fo.sum():,}")

    # 1. signed stand-alone AUC
    auc_df = signed_auc(X, y)
    auc_df.write_csv(OUT_TAB / "part4_feature_auc_signed.csv")
    try:
        plot_auc(auc_df)
    except ImportError:
        pass
    log("Signed AUC (dev):\n" + m07.to_markdown(auc_df))

    # 2. closures-only label in the same time-ordered CV
    cv = closures_only_cv(X, y_fo, yr)
    cv.write_csv(OUT_TAB / "part5_cv_closures_only_by_fold.csv")
    summ = cv.group_by("model").agg(pl.col("pr_auc").mean().alias("mean_pr_auc_closures_only"),
                                    pl.col("pr_auc").std().alias("sd_pr_auc_closures_only"),
                                    pl.col("roc_auc").mean().alias("mean_roc_auc_closures_only"),
                                    pl.col("positive_rate").mean().alias("mean_positive_rate"))
    main_cv = OUT_TAB / "part5_cv_by_fold.csv"
    if main_cv.exists():
        ref = (pl.read_csv(main_cv).filter(pl.col("model").is_in(["capital_rule", CHOSEN]))
               .group_by("model").agg(pl.col("pr_auc").mean().alias("mean_pr_auc_main_label")))
        summ = summ.join(ref, on="model", how="left")
    summ = summ.sort("model")
    summ.write_csv(OUT_TAB / "part5_cv_closures_only_summary.csv")
    log("Closures-only CV summary (dev):\n" + m07.to_markdown(summ))
    log(f"DONE in {(time.perf_counter() - t_start) / 60:.1f} min")


if __name__ == "__main__":
    main()