"""
Part 4 - Leak-free feature table, feature analysis and train-only preprocessing (BFT65B)

Steps
  1. Join the Part 3 features with the label and helper columns from the panel.
  2. Assign the time-ordered split (dev 1984-2006 | gap 2007 | test 2008-2025Q2)
     and count rows, banks, positive rows and failure events per period.
  3. Point-in-time proof ("truncation test"): recompute every feature on a panel
     CUT at the end of the dev period and check the features of all earlier rows
     are identical. A deliberately leaky feature (next quarter's assets) is
     included as a control and must FAIL the test.
  4. Feature analysis on the DEV period only: missing share, univariate ROC-AUC
     and average precision, and the sign of the relation with failure.
  5. Fit the preprocessing pipeline (winsorise, impute, scale) on dev only and
     save its learned parameters; show that the test period is only transformed.

Outputs: data/processed/model_table.parquet, data/processed/preprocessor.joblib,
         output/tables/part4_*.csv|md, output/figures/part4_univariate_auc.png

Run from the project root:
    python -X utf8 src/06_features.py
"""

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline_def import (DEV_END, DEV_START, FEATURES, GAP_END, GAP_START,  # noqa: E402
                          TEST_END, TEST_START, build_preprocessor)

PANEL_DIR = ROOT / "data" / "processed" / "panel"
FEAT_DIR = ROOT / "data" / "processed" / "features_core"
MODEL_TABLE = ROOT / "data" / "processed" / "model_table.parquet"
PREP_FILE = ROOT / "data" / "processed" / "preprocessor.joblib"
OUT_TAB = ROOT / "output" / "tables"
OUT_FIG = ROOT / "output" / "figures"

DICTIONARY = [
    # name, CAMELS, definition, why it matters, expected sign for failure risk
    ("F_EQ_TA", "C", "EQ / ASSET x 100", "Loss-absorbing capital; thin equity is the closest precursor of insolvency", "-"),
    ("F_LEV_RATIO", "C", "Tier 1 leverage ratio (RBC1AAJ, %)", "Regulatory capital measure used for prompt corrective action", "-"),
    ("F_EQ_TA_CHG_4Q", "C", "F_EQ_TA(q) - F_EQ_TA(q-4)", "Capital erosion over the last year", "-"),
    ("F_EQ_TA_PCTRANK", "C", "Percentile rank of F_EQ_TA among banks in the same quarter", "Capital relative to peers, robust to economy-wide shifts", "-"),
    ("F_NPL", "A", "NCLNLS / LNLSGR x 100", "Non-current loans: the main driver of losses", "+"),
    ("F_RES_LN", "A", "LNATRES / LNLSGR x 100", "Loss reserves; high reserves signal expected losses", "+"),
    ("F_PROV_LN", "A", "Quarterly provisions x 4 / LNLSGR x 100", "New loss recognition", "+"),
    ("F_NCO_LN", "A", "Quarterly net charge-offs x 4 / LNLSGR x 100", "Realised loan losses", "+"),
    ("F_ORE_TA", "A", "ORE / ASSET x 100", "Foreclosed real estate: problem assets already repossessed", "+"),
    ("F_NPL_CHG_1Q", "A", "F_NPL(q) - F_NPL(q-1)", "Speed of asset-quality deterioration", "+"),
    ("F_NPL_PCTRANK", "A", "Percentile rank of F_NPL in the same quarter", "Asset quality relative to peers", "+"),
    ("F_TA_GROWTH_4Q", "M", "ASSET(q) / ASSET(q-4) - 1", "Aggressive growth (management risk) or forced shrinking", "+/-"),
    ("F_ROA_Q", "E", "Quarterly net income x 4 / ASSET x 100", "Current profitability; losses consume capital", "-"),
    ("F_NIM_Q", "E", "(Interest income - interest expense) x 4 / ASSET x 100", "Core earning power", "-"),
    ("F_ROA_4Q_AVG", "E", "Mean of the last 4 quarterly ROA", "Persistent (not one-off) losses", "-"),
    ("F_ROA_VS_MEDIAN", "E", "F_ROA_Q - industry median ROA of the quarter", "Profitability relative to the cycle", "-"),
    ("F_LIQ", "L", "(CHBAL + SC) / ASSET x 100", "Liquid assets available to meet withdrawals", "-"),
    ("F_BRO_DEP", "L", "BRO / DEP x 100", "Reliance on volatile brokered deposits", "+"),
    ("F_LN_DEP", "L", "LNLSGR / DEP x 100", "Loans funded by deposits; high values mean funding strain", "+"),
    ("F_LOG_TA", "Size", "ln(ASSET)", "Small banks fail more often and are less diversified", "-"),
]


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def to_markdown(df):
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in df.iter_rows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:,.4f}" if abs(v) < 10 else f"{v:,.1f}")
            else:
                cells.append("" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_part3_module():
    spec = importlib.util.spec_from_file_location("p3", ROOT / "src" / "05_polars_pipeline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    md = ["# Part 4 - Feature pipeline", f"Generated {datetime.now():%Y-%m-%d %H:%M}", ""]

    # ------------------------------------------------------------ 1. feature table + label
    feats = pl.scan_parquet(FEAT_DIR.as_posix() + "/**/*.parquet", hive_partitioning=True).collect()
    extra = (pl.scan_parquet(PANEL_DIR.as_posix() + "/**/*.parquet", hive_partitioning=True)
             .select(["CERT", "REPDTE", "RBC1AAJ", "Y_FAILURE_ONLY", "LATE_SIGNAL",
                      "NEXT_EVENT_DT", "NEXT_EVENT_TYPE", "QUARTERS_TO_EVENT"])
             .collect())
    tab = (feats.join(extra, on=["CERT", "REPDTE"], how="left")
           .with_columns(pl.col("RBC1AAJ").alias("F_LEV_RATIO"))
           .filter(pl.col("LABEL_AVAILABLE"))
           .with_columns(
               pl.when(pl.col("REPDTE").is_between(DEV_START, DEV_END)).then(pl.lit("dev"))
               .when(pl.col("REPDTE").is_between(GAP_START, GAP_END)).then(pl.lit("gap"))
               .when(pl.col("REPDTE").is_between(TEST_START, TEST_END)).then(pl.lit("test"))
               .otherwise(pl.lit("out")).alias("SPLIT")))
    keep = (["CERT", "REPDTE", "QIDX", "YEAR", "SPLIT", "Y", "Y_FAILURE_ONLY", "LATE_SIGNAL",
             "NEXT_EVENT_DT", "NEXT_EVENT_TYPE", "QUARTERS_TO_EVENT"] + FEATURES)
    tab = tab.select([c for c in keep if c in tab.columns]).sort(["CERT", "QIDX"])
    assert tab.select(["CERT", "REPDTE"]).is_duplicated().sum() == 0, "duplicate keys after join"
    tab.write_parquet(MODEL_TABLE, compression="zstd")
    log(f"Model table: {tab.height:,} labelled rows x {len(FEATURES)} features -> {MODEL_TABLE}")

    # ------------------------------------------------------------ 2. split summary
    split = (tab.group_by("SPLIT")
             .agg(pl.col("REPDTE").min().alias("first_quarter"), pl.col("REPDTE").max().alias("last_quarter"),
                  pl.len().alias("bank_quarters"), pl.col("CERT").n_unique().alias("banks"),
                  pl.col("Y").sum().alias("positive_rows"),
                  (pl.col("Y").sum() / pl.len()).alias("positive_rate"),
                  pl.struct(["CERT", "NEXT_EVENT_DT"]).filter(pl.col("Y") == 1).n_unique()
                  .alias("failure_events"),
                  pl.struct(["CERT", "NEXT_EVENT_DT"]).filter((pl.col("Y") == 1)
                                                              & (pl.col("NEXT_EVENT_TYPE") == "FAILURE"))
                  .n_unique().alias("of_which_closures"))
             .sort("first_quarter"))
    split.write_csv(OUT_TAB / "part4_split_summary.csv")
    dev_last_label = tab.filter(pl.col("SPLIT") == "dev")["NEXT_EVENT_DT"].max()
    md += ["## Time-ordered split", to_markdown(split), "",
           f"Latest failure date used by a dev label: {dev_last_label} (test starts {TEST_START}), "
           "so no dev label overlaps the test period.", ""]
    log("Split:\n" + to_markdown(split))

    # ------------------------------------------------------------ 3. truncation test (point-in-time proof)
    p3 = load_part3_module()
    cut = DEV_END
    lf_cut = p3.panel_scan().filter(pl.col("REPDTE") <= cut).sort(["CERT", "QIDX"])
    trunc = p3.pl_quarter(p3.pl_windows(p3.pl_ratios(lf_cut))).collect()
    full = feats.filter(pl.col("REPDTE") <= cut).sort(["CERT", "QIDX"])
    # control: a deliberately leaky feature (uses the NEXT quarter)
    leak = pl.col("ASSET").shift(-1).over("CERT").alias("LEAKY_NEXT_ASSET")
    trunc = trunc.with_columns(leak)
    full_leak = (p3.panel_scan().sort(["CERT", "QIDX"]).with_columns(leak)
                 .filter(pl.col("REPDTE") <= cut).select(["CERT", "QIDX", "LEAKY_NEXT_ASSET"]).collect())
    full = full.join(full_leak, on=["CERT", "QIDX"], how="left").sort(["CERT", "QIDX"])
    rows = []
    for f in [c for c in p3.FEATURES] + ["LEAKY_NEXT_ASSET"]:
        a = full[f].to_numpy().astype("float64")
        b = trunc[f].to_numpy().astype("float64")
        same = bool(np.allclose(a, b, rtol=1e-12, atol=1e-12, equal_nan=True))
        n_diff = int((~np.isclose(a, b, rtol=1e-12, atol=1e-12, equal_nan=True)).sum())
        rows.append({"feature": f, "identical_after_cut": same, "rows_different": n_diff})
    tt = pl.DataFrame(rows)
    tt.write_csv(OUT_TAB / "part4_truncation_test.csv")
    real_ok = tt.filter(pl.col("feature") != "LEAKY_NEXT_ASSET")["identical_after_cut"].all()
    ctrl_caught = not tt.filter(pl.col("feature") == "LEAKY_NEXT_ASSET")["identical_after_cut"][0]
    md += ["## Truncation test (point-in-time proof)",
           f"All features recomputed on data cut at {cut}; rows up to the cut compared with the full-data "
           f"features. Real features identical: **{real_ok}**. Leaky control detected: **{ctrl_caught}**.",
           to_markdown(tt), ""]
    log(f"Truncation test - real features identical: {real_ok}; leaky control detected: {ctrl_caught}")

    # ------------------------------------------------------------ 4. feature analysis on DEV only
    dev = tab.filter(pl.col("SPLIT") == "dev")
    y_dev = dev["Y"].to_numpy()
    stats = []
    for f in FEATURES:
        x = dev[f].to_numpy().astype("float64")
        ok = ~np.isnan(x)
        auc = roc_auc_score(y_dev[ok], x[ok]) if ok.sum() and y_dev[ok].min() != y_dev[ok].max() else np.nan
        ap = average_precision_score(y_dev[ok], x[ok] if auc >= 0.5 else -x[ok]) if ok.sum() else np.nan
        exp = next(d[4] for d in DICTIONARY if d[0] == f)
        sign = "+" if auc >= 0.5 else "-"
        stats.append({"feature": f, "camels": next(d[1] for d in DICTIONARY if d[0] == f),
                      "missing_share_dev": float(1 - ok.mean()),
                      "auc_dev": float(auc), "auc_strength": float(max(auc, 1 - auc)),
                      "avg_precision_dev": float(ap), "observed_sign": sign, "expected_sign": exp,
                      "sign_as_expected": (exp == "+/-") or (exp == sign)})
    st = pl.DataFrame(stats).sort("auc_strength", descending=True)
    st.write_csv(OUT_TAB / "part4_feature_stats_dev.csv")
    pl.DataFrame([{"feature": d[0], "camels": d[1], "definition": d[2], "rationale": d[3],
                   "expected_sign": d[4]} for d in DICTIONARY]).write_csv(OUT_TAB / "part4_feature_dictionary.csv")
    base_rate = float(y_dev.mean())
    md += ["## Univariate strength on the development period only",
           f"Positive rate in dev: {base_rate:.4%} (average precision of a random score = this rate).",
           to_markdown(st), ""]

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        s = st.sort("auc_strength")
        colors = {"C": "#3b6ea5", "A": "#c0504d", "M": "#9bbb59", "E": "#f79646", "L": "#8064a2", "Size": "#7f7f7f"}
        fig, ax = plt.subplots(figsize=(9, 6.5))
        ax.barh(s["feature"].to_list(), s["auc_strength"].to_list(),
                color=[colors[c] for c in s["camels"].to_list()])
        ax.axvline(0.5, color="black", lw=0.8, ls="--")
        ax.set_xlim(0.45, 1.0)
        ax.set_xlabel("Univariate ROC-AUC on the development period (max(AUC, 1-AUC))")
        ax.set_title("Figure 6. Stand-alone strength of each feature (dev 1984-2006 only)")
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=col, label=g) for g, col in colors.items()],
                  title="CAMELS", loc="lower right", fontsize=8)
        fig.tight_layout()
        fig.savefig(OUT_FIG / "part4_univariate_auc.png", dpi=200)
        plt.close(fig)
    except ImportError:
        pass

    # ------------------------------------------------------------ 5. preprocessing fitted on dev only
    X_dev = dev.select(FEATURES).to_numpy().astype("float64")
    prep = build_preprocessor().fit(X_dev)
    joblib.dump(prep, PREP_FILE)
    w, imp, sc = prep.named_steps["winsorize"], prep.named_steps["impute"], prep.named_steps["scale"]
    params = pl.DataFrame({"feature": FEATURES, "winsor_low_p01": w.low_, "winsor_high_p99": w.high_,
                           "impute_median": imp.statistics_,
                           "scale_mean": sc.mean_[:len(FEATURES)], "scale_std": sc.scale_[:len(FEATURES)]})
    params.write_csv(OUT_TAB / "part4_preprocessor_params_dev.csv")
    test = tab.filter(pl.col("SPLIT") == "test")
    X_test = test.select(FEATURES).to_numpy().astype("float64")
    Z_dev, Z_test = prep.transform(X_dev), prep.transform(X_test)
    shift = pl.DataFrame({"feature": FEATURES,
                          "dev_mean_after_scaling": Z_dev[:, :len(FEATURES)].mean(axis=0),
                          "test_mean_after_scaling": Z_test[:, :len(FEATURES)].mean(axis=0)})
    shift.write_csv(OUT_TAB / "part4_dev_vs_test_scaled_means.csv")
    n_flags = Z_dev.shape[1] - len(FEATURES)
    md += ["## Preprocessing pipeline (fitted on dev only)",
           "Winsorise at the dev 1st/99th percentiles -> impute dev medians (+ missing-value flags) -> "
           "standardise with dev mean and standard deviation. The fitted object is reused unchanged in Part 5.",
           f"Output columns: {Z_dev.shape[1]} ({len(FEATURES)} features + {n_flags} missing flags).", "",
           to_markdown(params), "",
           "After scaling, dev means are 0 by construction; test means are not, which shows the test data "
           "were only transformed with dev parameters (and reveals the shift between periods):",
           to_markdown(shift), ""]
    (OUT_TAB / "part4_report.md").write_text("\n".join(md), encoding="utf-8")
    summary = {"rows": tab.height, "features": len(FEATURES), "dev_positive_rate": base_rate,
               "truncation_test_real_features_identical": bool(real_ok),
               "truncation_test_leaky_control_detected": bool(ctrl_caught),
               "preprocessed_columns": int(Z_dev.shape[1])}
    (OUT_TAB / "part4_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log("Summary: " + json.dumps(summary))
    log("DONE. Report: output/tables/part4_report.md")


if __name__ == "__main__":
    main()