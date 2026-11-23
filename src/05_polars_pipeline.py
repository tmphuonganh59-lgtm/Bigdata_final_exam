"""
Part 3a - Core transformations in Polars + fair benchmark against pandas (BFT65B)

The SAME core transformations are implemented three ways:
  pandas (baseline) | Polars eager | Polars lazy (also run with the streaming engine)

Core transformations (all point-in-time: only the current or earlier quarters
of the same bank, or other banks in the SAME quarter, are used):
  S1 read     : selected columns of the clean panel (column projection)
  S2 ratios   : size-scaled CAMELS-style ratios (safe division, no inf)
  S3 windows  : per-bank lags, 4-quarter growth and averages, gap-safe
                (a lag is used only if it is exactly k quarters earlier)
  S4 quarter  : industry median per quarter joined back (group_by + join)
                and percentile rank of the bank inside its quarter
Benchmark rules: same machine, same files, same columns, 1 warm-up + N timed
runs (median), peak memory measured in a fresh process per engine, and the
outputs of all engines are checked to be identical.

Outputs:
  data/processed/features_core/YEAR=yyyy/part-0.parquet  (input for Part 4)
  data/processed/spark_input.parquet                     (one file for Colab)
  output/tables/part3_*.csv|md|txt, output/figures/part3_benchmark.png

Run from the project root:
    python -X utf8 src/05_polars_pipeline.py
"""

import argparse
import gc
import json
import multiprocessing as mp
import shutil
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl
import psutil

ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "data" / "processed" / "panel"
FEAT_DIR = ROOT / "data" / "processed" / "features_core"
SPARK_FILE = ROOT / "data" / "processed" / "spark_input.parquet"
OUT_TAB = ROOT / "output" / "tables"
OUT_FIG = ROOT / "output" / "figures"

COLS = ["CERT", "REPDTE", "QIDX", "ASSET", "EQ", "DEP", "LNLSGR", "NCLNLS", "LNATRES",
        "CHBAL", "SC", "BRO", "ORE", "NETINC_QTR", "INTINC_QTR", "EINTEXP_QTR",
        "ELNATR_QTR", "NTLNLS_QTR", "Y", "LABEL_AVAILABLE"]
FEATURES = ["F_EQ_TA", "F_NPL", "F_RES_LN", "F_ROA_Q", "F_NIM_Q", "F_PROV_LN", "F_NCO_LN",
            "F_LIQ", "F_BRO_DEP", "F_ORE_TA", "F_LN_DEP", "F_LOG_TA",
            "F_TA_GROWTH_4Q", "F_EQ_TA_CHG_4Q", "F_NPL_CHG_1Q", "F_ROA_4Q_AVG",
            "F_ROA_VS_MEDIAN", "F_NPL_PCTRANK", "F_EQ_TA_PCTRANK"]


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def to_markdown(df):
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in df.iter_rows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:,.3f}")
            else:
                cells.append("" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ============================================================ POLARS
def pdiv(num, den):
    """Safe division: missing when the denominator is missing or <= 0."""
    return pl.when(den > 0).then(num / den).otherwise(None)


def pl_ratios(f):
    c = pl.col
    return f.with_columns(
        (pdiv(c("EQ"), c("ASSET")) * 100).alias("F_EQ_TA"),
        (pdiv(c("NCLNLS"), c("LNLSGR")) * 100).alias("F_NPL"),
        (pdiv(c("LNATRES"), c("LNLSGR")) * 100).alias("F_RES_LN"),
        (pdiv(c("NETINC_QTR") * 4, c("ASSET")) * 100).alias("F_ROA_Q"),
        (pdiv((c("INTINC_QTR") - c("EINTEXP_QTR")) * 4, c("ASSET")) * 100).alias("F_NIM_Q"),
        (pdiv(c("ELNATR_QTR") * 4, c("LNLSGR")) * 100).alias("F_PROV_LN"),
        (pdiv(c("NTLNLS_QTR") * 4, c("LNLSGR")) * 100).alias("F_NCO_LN"),
        (pdiv(c("CHBAL") + c("SC"), c("ASSET")) * 100).alias("F_LIQ"),
        (pdiv(c("BRO"), c("DEP")) * 100).alias("F_BRO_DEP"),
        (pdiv(c("ORE"), c("ASSET")) * 100).alias("F_ORE_TA"),
        (pdiv(c("LNLSGR"), c("DEP")) * 100).alias("F_LN_DEP"),
        c("ASSET").log().alias("F_LOG_TA"),
    )


def pl_windows(f):
    c = pl.col

    def lag(col, k):
        return c(col).shift(k).over("CERT")

    gap4 = (c("QIDX") - lag("QIDX", 4)) == 4
    gap3 = (c("QIDX") - lag("QIDX", 3)) == 3
    gap1 = (c("QIDX") - lag("QIDX", 1)) == 1
    return f.with_columns(
        pl.when(gap4).then(pdiv(c("ASSET"), lag("ASSET", 4)) - 1).otherwise(None).alias("F_TA_GROWTH_4Q"),
        pl.when(gap4).then(c("F_EQ_TA") - lag("F_EQ_TA", 4)).otherwise(None).alias("F_EQ_TA_CHG_4Q"),
        pl.when(gap1).then(c("F_NPL") - lag("F_NPL", 1)).otherwise(None).alias("F_NPL_CHG_1Q"),
        pl.when(gap3).then((c("F_ROA_Q") + lag("F_ROA_Q", 1) + lag("F_ROA_Q", 2) + lag("F_ROA_Q", 3)) / 4)
        .otherwise(None).alias("F_ROA_4Q_AVG"),
    )


def pl_windows_sorted(f):
    """Same features, but uses the fact that rows are sorted by (CERT, QIDX):
    a plain shift is a lag of the same bank when CERT(t-k) == CERT(t).
    This avoids building per-bank groups for every lag expression."""
    c = pl.col

    def ok(k):
        return (c("CERT").shift(k) == c("CERT")) & ((c("QIDX") - c("QIDX").shift(k)) == k)

    return f.with_columns(
        pl.when(ok(4)).then(pdiv(c("ASSET"), c("ASSET").shift(4)) - 1).otherwise(None).alias("F_TA_GROWTH_4Q"),
        pl.when(ok(4)).then(c("F_EQ_TA") - c("F_EQ_TA").shift(4)).otherwise(None).alias("F_EQ_TA_CHG_4Q"),
        pl.when(ok(1)).then(c("F_NPL") - c("F_NPL").shift(1)).otherwise(None).alias("F_NPL_CHG_1Q"),
        pl.when(ok(3)).then((c("F_ROA_Q") + c("F_ROA_Q").shift(1) + c("F_ROA_Q").shift(2)
                             + c("F_ROA_Q").shift(3)) / 4).otherwise(None).alias("F_ROA_4Q_AVG"),
    )


def pl_quarter(f):
    c = pl.col
    med = f.group_by("REPDTE").agg(c("F_ROA_Q").median().alias("ROA_MEDIAN_Q"))
    f = f.join(med, on="REPDTE", how="left")
    return f.with_columns(
        (c("F_ROA_Q") - c("ROA_MEDIAN_Q")).alias("F_ROA_VS_MEDIAN"),
        (c("F_NPL").rank("average").over("REPDTE") / c("F_NPL").count().over("REPDTE")).alias("F_NPL_PCTRANK"),
        (c("F_EQ_TA").rank("average").over("REPDTE") / c("F_EQ_TA").count().over("REPDTE"))
        .alias("F_EQ_TA_PCTRANK"),
    ).drop("ROA_MEDIAN_Q").sort(["CERT", "QIDX"])


def panel_scan():
    return pl.scan_parquet(PANEL_DIR.as_posix() + "/**/*.parquet", hive_partitioning=True).select(COLS)


def lazy_plan():
    lf = panel_scan().sort(["CERT", "QIDX"])
    return pl_quarter(pl_windows(pl_ratios(lf)))


def lazy_plan_sorted():
    lf = panel_scan().sort(["CERT", "QIDX"])
    return pl_quarter(pl_windows_sorted(pl_ratios(lf)))


def run_polars_eager(timer=None):
    t = time.perf_counter()
    df = panel_scan().collect().sort(["CERT", "QIDX"])
    marks = [("S1 read", time.perf_counter() - t)]
    for name, fn in (("S2 ratios", pl_ratios), ("S3 windows", pl_windows), ("S4 quarter join+rank", pl_quarter)):
        t = time.perf_counter()
        df = fn(df)
        marks.append((name, time.perf_counter() - t))
    if timer is not None:
        timer.extend(marks)
    return df


def run_polars_lazy(timer=None):
    return lazy_plan().collect()


def run_polars_streaming(timer=None):
    return lazy_plan().collect(engine="streaming")


def run_polars_lazy_sorted(timer=None):
    return lazy_plan_sorted().collect()


# ============================================================ PANDAS
def run_pandas(timer=None, sorted_shift=False):
    import pandas as pd

    def ndiv(num, den):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(den > 0, num / den, np.nan)

    marks = []
    t = time.perf_counter()
    df = pd.read_parquet(PANEL_DIR, columns=COLS).sort_values(["CERT", "QIDX"]).reset_index(drop=True)
    for col in COLS:
        if col not in ("CERT", "REPDTE", "QIDX", "LABEL_AVAILABLE", "Y"):
            df[col] = df[col].astype("float64")
    marks.append(("S1 read", time.perf_counter() - t))

    t = time.perf_counter()
    df["F_EQ_TA"] = ndiv(df["EQ"], df["ASSET"]) * 100
    df["F_NPL"] = ndiv(df["NCLNLS"], df["LNLSGR"]) * 100
    df["F_RES_LN"] = ndiv(df["LNATRES"], df["LNLSGR"]) * 100
    df["F_ROA_Q"] = ndiv(df["NETINC_QTR"] * 4, df["ASSET"]) * 100
    df["F_NIM_Q"] = ndiv((df["INTINC_QTR"] - df["EINTEXP_QTR"]) * 4, df["ASSET"]) * 100
    df["F_PROV_LN"] = ndiv(df["ELNATR_QTR"] * 4, df["LNLSGR"]) * 100
    df["F_NCO_LN"] = ndiv(df["NTLNLS_QTR"] * 4, df["LNLSGR"]) * 100
    df["F_LIQ"] = ndiv(df["CHBAL"] + df["SC"], df["ASSET"]) * 100
    df["F_BRO_DEP"] = ndiv(df["BRO"], df["DEP"]) * 100
    df["F_ORE_TA"] = ndiv(df["ORE"], df["ASSET"]) * 100
    df["F_LN_DEP"] = ndiv(df["LNLSGR"], df["DEP"]) * 100
    df["F_LOG_TA"] = np.log(df["ASSET"])
    marks.append(("S2 ratios", time.perf_counter() - t))

    t = time.perf_counter()
    q = df["QIDX"].astype("float64")
    if sorted_shift:   # rows are sorted by (CERT, QIDX): plain shift + same-bank check
        def sh(col, k):
            return df[col].shift(k)
        same = {k: (df["CERT"].shift(k) == df["CERT"]).to_numpy() for k in (1, 3, 4)}
    else:              # idiomatic group-wise shift
        g = df.groupby("CERT", sort=False)

        def sh(col, k):
            return g[col].shift(k)
        same = {k: True for k in (1, 3, 4)}
    q1, q3, q4 = (sh("QIDX", k).astype("float64") for k in (1, 3, 4))
    a4, e4, n1 = sh("ASSET", 4), sh("F_EQ_TA", 4), sh("F_NPL", 1)
    r1, r2, r3 = (sh("F_ROA_Q", k) for k in (1, 2, 3))
    ok4 = same[4] & (q - q4 == 4)
    df["F_TA_GROWTH_4Q"] = np.where(ok4, ndiv(df["ASSET"], a4) - 1, np.nan)
    df["F_EQ_TA_CHG_4Q"] = np.where(ok4, df["F_EQ_TA"] - e4, np.nan)
    df["F_NPL_CHG_1Q"] = np.where(same[1] & (q - q1 == 1), df["F_NPL"] - n1, np.nan)
    df["F_ROA_4Q_AVG"] = np.where(same[3] & (q - q3 == 3), (df["F_ROA_Q"] + r1 + r2 + r3) / 4, np.nan)
    marks.append(("S3 windows", time.perf_counter() - t))

    t = time.perf_counter()
    med = df.groupby("REPDTE")["F_ROA_Q"].median().rename("ROA_MEDIAN_Q").reset_index()
    df = df.merge(med, on="REPDTE", how="left")
    df["F_ROA_VS_MEDIAN"] = df["F_ROA_Q"] - df["ROA_MEDIAN_Q"]
    gq = df.groupby("REPDTE")
    df["F_NPL_PCTRANK"] = gq["F_NPL"].rank(method="average", pct=True)
    df["F_EQ_TA_PCTRANK"] = gq["F_EQ_TA"].rank(method="average", pct=True)
    df = df.drop(columns="ROA_MEDIAN_Q").sort_values(["CERT", "QIDX"]).reset_index(drop=True)
    marks.append(("S4 quarter join+rank", time.perf_counter() - t))
    if timer is not None:
        timer.extend(marks)
    return df


def run_pandas_sorted(timer=None):
    return run_pandas(timer, sorted_shift=True)


ENGINES = {"pandas": run_pandas, "polars_eager": run_polars_eager,
           "polars_lazy": run_polars_lazy, "polars_streaming": run_polars_streaming,
           "pandas_sorted_shift": run_pandas_sorted, "polars_lazy_sorted_shift": run_polars_lazy_sorted}


# ============================================================ MEMORY (fresh process)
def _mem_child(engine, queue):
    import pandas  # noqa: F401  (imported before the baseline for fairness)
    proc = psutil.Process()
    gc.collect()
    base = proc.memory_info().rss
    peak = [base]
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            peak[0] = max(peak[0], proc.memory_info().rss)
            time.sleep(0.005)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    t = time.perf_counter()
    out = ENGINES[engine]()
    secs = time.perf_counter() - t
    peak[0] = max(peak[0], proc.memory_info().rss)
    stop.set()
    th.join()
    queue.put({"engine": engine, "baseline_MB": base / 1024**2, "peak_MB": peak[0] / 1024**2,
               "extra_MB": (peak[0] - base) / 1024**2, "cold_run_s": secs, "rows": len(out)})


def measure_memory(engine):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_mem_child, args=(engine, q))
    p.start()
    res = q.get()
    p.join()
    return res


# ============================================================ CHECK
def outputs_identical(ref_pd, other_pd, label):
    rows = []
    ok_all = len(ref_pd) == len(other_pd)
    for col in FEATURES:
        a = ref_pd[col].to_numpy(dtype="float64", na_value=np.nan)
        b = other_pd[col].to_numpy(dtype="float64", na_value=np.nan)
        same_nan = bool((np.isnan(a) == np.isnan(b)).all())
        close = bool(np.allclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True))
        ok_all &= same_nan and close
        rows.append({"comparison": label, "feature": col, "same_missing": same_nan, "values_equal": close})
    return ok_all, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------- 1. engine explanation
    plan = lazy_plan()
    (OUT_TAB / "part3_polars_plan.txt").write_text(
        "===== OPTIMIZED PLAN =====\n" + plan.explain()
        + "\n\n===== NOT OPTIMIZED =====\n" + plan.explain(optimized=False)
        + "\n\n===== OPTIMIZED PLAN, SORTED-SHIFT VERSION =====\n" + lazy_plan_sorted().explain(),
        encoding="utf-8")
    log("Polars query plans saved")

    # ---------------------------------------------------- 2. peak memory (fresh process each, run first while RAM is free)
    mem_rows = []
    for name in ENGINES:
        log(f"Peak memory: {name} (fresh process)")
        mem_rows.append(measure_memory(name))
    mem_df = pl.DataFrame(mem_rows)
    mem_df.write_csv(OUT_TAB / "part3_benchmark_memory.csv")

    # ---------------------------------------------------- 3. timing (warm-up + N runs)
    step_rows, total_rows, outputs = [], [], {}
    for name, fn in ENGINES.items():
        log(f"Timing {name}: 1 warm-up + {args.repeats} runs")
        outputs[name] = fn()  # warm-up, result kept for the equality check
        totals, steps = [], {}
        for _ in range(args.repeats):
            gc.collect()
            marks = []
            t = time.perf_counter()
            res = fn(marks)
            totals.append(time.perf_counter() - t)
            for s, v in marks:
                steps.setdefault(s, []).append(v)
            del res
        total_rows.append({"engine": name, "median_s": statistics.median(totals),
                           "min_s": min(totals), "max_s": max(totals), "runs": len(totals)})
        for s, vals in steps.items():
            step_rows.append({"engine": name, "step": s, "median_s": statistics.median(vals)})

    totals_df = pl.DataFrame(total_rows)
    base = totals_df.filter(pl.col("engine") == "pandas")["median_s"][0]
    totals_df = totals_df.with_columns((base / pl.col("median_s")).alias("speedup_vs_pandas"))
    steps_df = pl.DataFrame(step_rows).pivot(on="engine", index="step", values="median_s")
    if "pandas" in steps_df.columns and "polars_eager" in steps_df.columns:
        steps_df = steps_df.with_columns((pl.col("pandas") / pl.col("polars_eager")).alias("speedup_eager"))
    totals_df.write_csv(OUT_TAB / "part3_benchmark_total.csv")
    steps_df.write_csv(OUT_TAB / "part3_benchmark_steps.csv")

    # ---------------------------------------------------- 4. identical results?
    ref = outputs["pandas"]
    checks, all_ok = [], True
    for name in [n for n in ENGINES if n != "pandas"]:
        other = outputs[name] if name.startswith("pandas") else outputs[name].to_pandas()
        ok, rows = outputs_identical(ref, other, f"pandas vs {name}")
        all_ok &= ok
        checks += rows
    pl.DataFrame(checks).write_csv(OUT_TAB / "part3_result_check.csv")
    log(f"Result check (all {len(ENGINES)} engines give identical features): {'PASSED' if all_ok else 'FAILED'}")

    # ---------------------------------------------------- 5. save outputs for Part 4 and Spark
    out = outputs["polars_lazy"].with_columns(pl.col("REPDTE").dt.year().cast(pl.Int16).alias("YEAR"))
    if FEAT_DIR.exists():
        shutil.rmtree(FEAT_DIR)
    for y in out["YEAR"].unique().sort().to_list():
        d = FEAT_DIR / f"YEAR={y}"
        d.mkdir(parents=True, exist_ok=True)
        out.filter(pl.col("YEAR") == y).drop("YEAR").write_parquet(d / "part-0.parquet", compression="zstd")
    panel_scan().collect().write_parquet(SPARK_FILE, compression="zstd")
    log(f"Features saved to {FEAT_DIR}; Spark input saved to {SPARK_FILE} "
        f"({SPARK_FILE.stat().st_size / 1024**2:.1f} MB)")

    # reference numbers that the Spark notebook must reproduce
    ref_year = (out.group_by("YEAR")
                .agg(pl.len().alias("rows"),
                     pl.col("Y").sum().alias("sum_Y"),
                     pl.col("F_TA_GROWTH_4Q").count().alias("n_growth"),
                     pl.col("F_TA_GROWTH_4Q").mean().alias("mean_growth"),
                     pl.col("F_ROA_VS_MEDIAN").mean().alias("mean_roa_vs_median"))
                .sort("YEAR"))
    ref_year.write_csv(OUT_TAB / "part3_spark_reference_by_year.csv")
    ref_tot = {"rows": out.height, "sum_Y": int(out["Y"].sum()),
               "n_growth": int(out["F_TA_GROWTH_4Q"].count()),
               "sum_growth": float(out["F_TA_GROWTH_4Q"].sum()),
               "sum_roa_vs_median": float(out["F_ROA_VS_MEDIAN"].sum())}
    (OUT_TAB / "part3_spark_reference.json").write_text(json.dumps(ref_tot, indent=2), encoding="utf-8")

    # ---------------------------------------------------- 6. figure + report
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        names = totals_df["engine"].to_list()
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
        axes[0].bar(names, totals_df["median_s"].to_list(), color="#3b6ea5")
        axes[0].set_ylabel(f"Median seconds ({args.repeats} runs)")
        axes[0].set_title("Full pipeline time")
        mm = {r["engine"]: r["extra_MB"] for r in mem_rows}
        axes[1].bar(names, [mm[n] for n in names], color="#c0504d")
        axes[1].set_ylabel("Extra peak memory (MB)")
        axes[1].set_title("Peak memory above baseline")
        for ax in axes:
            ax.tick_params(axis="x", rotation=25, labelsize=8)
            for p in ax.patches:
                ax.annotate(f"{p.get_height():,.1f}", (p.get_x() + p.get_width() / 2, p.get_height()),
                            ha="center", va="bottom", fontsize=9)
        fig.suptitle("Figure 5. Same pipeline in pandas and Polars (1.68 million bank-quarters)")
        fig.tight_layout()
        fig.savefig(OUT_FIG / "part3_benchmark.png", dpi=200)
        plt.close(fig)
    except ImportError:
        pass

    machine = json.loads((OUT_TAB / "part1_machine.json").read_text(encoding="utf-8")) \
        if (OUT_TAB / "part1_machine.json").exists() else {}
    md = ["# Part 3 - Polars pipeline and pandas benchmark", "",
          "Machine: " + ", ".join(f"{k}={v}" for k, v in machine.items()), "",
          f"## Full pipeline time (1 warm-up + {args.repeats} runs)", to_markdown(totals_df), "",
          "## Time per step (median seconds)", to_markdown(steps_df), "",
          "Polars lazy runs the whole plan at once (steps are fused), so it has no per-step times.", "",
          "## Peak memory (fresh process per engine)", to_markdown(mem_df), "",
          f"## Result check: {'PASSED' if all_ok else 'FAILED'} (details in part3_result_check.csv)", "",
          "## Reference numbers for the Spark notebook", "```", json.dumps(ref_tot, indent=2), "```"]
    (OUT_TAB / "part3_benchmark.md").write_text("\n".join(md), encoding="utf-8")
    log("DONE. Report: output/tables/part3_benchmark.md")


if __name__ == "__main__":
    main()