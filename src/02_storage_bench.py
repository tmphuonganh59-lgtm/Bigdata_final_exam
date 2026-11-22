"""
Part 1 - Acquisition verification & Storage benchmark (BFT65B final project)

What this script does
  1. Verifies the downloaded FDIC data is complete
     (170 quarters, rows = API total per quarter, no duplicate CERT-REPDTE).
  2. Applies an explicit schema (CERT Int32, REPDTE Date, amounts Float64)
     and measures in-memory size before / after.
  3. Writes the same panel in 6 storage layouts and measures disk size
     and write time.
  4. Benchmarks 3 read queries on every layout (1 warm-up + 5 timed runs,
     median reported) and checks every layout returns identical results.
  5. Saves the Polars query plans that show predicate / projection pushdown
     and partition pruning.
  6. Saves the chosen layout to data/processed/financials/ (Parquet, zstd,
     partitioned by year) for the next parts of the pipeline.

Run from the project root:
    python src/02_storage_bench.py
Options:
    --repeats 5       number of timed runs per measurement
    --skip-pandas     skip the pandas read benchmark
    --keep-bench      keep the temporary benchmark files

Author: To Mai Phuong Anh. Code drafted with help from Claude (Anthropic).
"""

import argparse
import gc
import json
import os
import platform
import shutil
import statistics
import sys
import time
from datetime import date, datetime
from pathlib import Path

import polars as pl
import psutil

# --------------------------------------------------------------------------
# Paths (relative to the project root, so the script runs on any machine)
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data_raw" / "fdic"
RAW_FIN_DIR = RAW_DIR / "financials"
MANIFEST = RAW_DIR / "manifest_financials.json"
OUT_TAB = ROOT / "output" / "tables"
OUT_FIG = ROOT / "output" / "figures"
FINAL_DIR = ROOT / "data" / "processed" / "financials"
# Benchmark files are written OUTSIDE OneDrive so cloud sync does not
# upload ~1-2 GB of test files or disturb the timings.
BENCH_DIR = Path.home() / "bft65b_bench_tmp"

FIRST_Q = date(1984, 3, 31)
LAST_Q = date(2026, 6, 30)
TEST_YEAR = 2008  # year used for the "read one year" query


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def expected_quarters():
    """All quarter-end dates from 1984Q1 to 2026Q2 (should be 170)."""
    ends = {3: 31, 6: 30, 9: 30, 12: 31}
    out = []
    for y in range(FIRST_Q.year, LAST_Q.year + 1):
        for m in (3, 6, 9, 12):
            d = date(y, m, ends[m])
            if FIRST_Q <= d <= LAST_Q:
                out.append(d)
    return out


def dir_size_mb(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size / 1024**2
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024**2


def n_files(path):
    path = Path(path)
    if path.is_file():
        return 1
    return sum(1 for f in path.rglob("*.parquet"))


def to_markdown(df):
    """Small markdown table writer (no extra package needed)."""
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in df.iter_rows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:,.3f}" if abs(v) < 100 else f"{v:,.1f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Step 0 - machine info (needed for a fair, reproducible benchmark)
# --------------------------------------------------------------------------
def machine_info():
    import pyarrow

    info = {
        "date_run": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "os": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "logical_cores": os.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        "python": sys.version.split()[0],
        "polars": pl.__version__,
        "pyarrow": pyarrow.__version__,
        "polars_threads": pl.thread_pool_size(),
    }
    try:
        import pandas as pd

        info["pandas"] = pd.__version__
    except ImportError:
        pass
    return info


# --------------------------------------------------------------------------
# Step 1 - load raw quarterly files
# --------------------------------------------------------------------------
def load_raw():
    files = sorted(RAW_FIN_DIR.glob("*.parquet"))
    if not files:
        sys.exit(f"ERROR: no parquet files found in {RAW_FIN_DIR}")
    frames, per_file = [], []
    for f in files:
        df = pl.read_parquet(f)
        qkey = f.stem.split("=")[-1]  # 'REPDTE=19840331' -> '19840331'
        if "REPDTE" not in df.columns:
            df = df.with_columns(pl.lit(qkey).alias("REPDTE"))
        per_file.append({"file_quarter": qkey, "rows_in_file": df.height})
        frames.append(df)
    raw = pl.concat(frames, how="diagonal_relaxed")
    return raw, pl.DataFrame(per_file), files


# --------------------------------------------------------------------------
# Step 2 - explicit schema
# --------------------------------------------------------------------------
def parse_repdte(dtype):
    c = pl.col("REPDTE")
    if dtype == pl.Date:
        return c
    if dtype == pl.Datetime:
        return c.dt.date()
    s = c.cast(pl.String).str.slice(0, 10)
    return pl.coalesce(
        s.str.strptime(pl.Date, "%Y%m%d", strict=False),
        s.str.strptime(pl.Date, "%Y-%m-%d", strict=False),
        s.str.strptime(pl.Date, "%m/%d/%Y", strict=False),
    )


def apply_schema(raw):
    exprs, text_cols = [], []
    for c, dt in raw.schema.items():
        if c == "CERT":
            exprs.append(pl.col(c).cast(pl.Float64).cast(pl.Int32))
        elif c == "REPDTE":
            exprs.append(parse_repdte(dt).alias("REPDTE"))
        elif dt == pl.Null or dt.is_numeric():
            exprs.append(pl.col(c).cast(pl.Float64))
        elif dt == pl.String:
            as_num = raw[c].cast(pl.Float64, strict=False)
            if as_num.null_count() == raw[c].null_count():
                exprs.append(pl.col(c).cast(pl.Float64, strict=False))
            else:
                exprs.append(pl.col(c))
                text_cols.append(c)
        else:
            exprs.append(pl.col(c))
    typed = raw.select(exprs)
    bad = typed["REPDTE"].null_count()
    if bad:
        sys.exit(f"ERROR: {bad} REPDTE values could not be parsed as dates")
    typed = typed.with_columns(pl.col("REPDTE").dt.year().cast(pl.Int16).alias("YEAR"))
    # Sorting by date then bank keeps each row group to a narrow date range,
    # so Parquet min/max statistics can skip row groups when filtering.
    typed = typed.sort(["REPDTE", "CERT"])
    return typed, text_cols


# --------------------------------------------------------------------------
# Step 3 - completeness checks
# --------------------------------------------------------------------------
def load_manifest():
    """Read the download manifest whatever its exact JSON shape."""
    import pandas as pd

    with open(MANIFEST, encoding="utf-8") as fh:
        m = json.load(fh)
    if isinstance(m, dict):
        if m and all(isinstance(v, dict) for v in m.values()):
            rows = [{"key": k, **v} for k, v in m.items()]
        else:
            rows = next((v for v in m.values() if isinstance(v, list)), [m])
    else:
        rows = m
    return pl.from_pandas(pd.json_normalize(rows).astype(str))


def completeness(typed, per_file):
    exp = expected_quarters()
    counts = typed.group_by("REPDTE").len().rename({"len": "rows_in_data"}).sort("REPDTE")
    present = set(counts["REPDTE"].to_list())
    missing = [d for d in exp if d not in present]
    extra = [d for d in present if d not in set(exp)]
    dups = typed.height - typed.select(["CERT", "REPDTE"]).unique().height
    null_cert = typed["CERT"].null_count()

    table = counts.with_columns(pl.col("REPDTE").dt.strftime("%Y%m%d").alias("qkey"))

    manifest_note = "manifest not found"
    manifest_mismatch = None
    if MANIFEST.exists():
        try:
            man = load_manifest()
            lower = {c.lower(): c for c in man.columns}
            tot = next((lower[c] for c in lower if "total" in c), None)
            rws = next((lower[c] for c in lower if "row" in c and "total" not in c), None)
            keyc = next(
                (lower[c] for c in lower if c in ("key", "repdte", "quarter", "date", "q")),
                None,
            )
            if tot and keyc:
                man = man.with_columns(
                    pl.col(keyc).str.replace_all("-", "").str.slice(0, 8).alias("qkey"),
                    pl.col(tot).cast(pl.Float64, strict=False).cast(pl.Int64, strict=False).alias("api_total"),
                )
                keep = ["qkey", "api_total"]
                if rws:
                    man = man.with_columns(
                        pl.col(rws).cast(pl.Float64, strict=False).cast(pl.Int64, strict=False).alias("manifest_rows")
                    )
                    keep.append("manifest_rows")
                table = table.join(man.select(keep), on="qkey", how="left").with_columns(
                    (pl.col("rows_in_data") == pl.col("api_total")).alias("matches_api_total")
                )
                manifest_mismatch = int((~table["matches_api_total"].fill_null(False)).sum())
                manifest_note = f"compared with manifest columns '{keyc}', '{tot}'"
            else:
                manifest_note = f"manifest read, columns not recognised: {man.columns}"
        except Exception as e:  # never stop the benchmark because of the manifest
            manifest_note = f"manifest could not be parsed: {e}"

    summary = {
        "expected_quarters": len(exp),
        "quarters_present": len(present),
        "missing_quarters": [d.isoformat() for d in missing],
        "unexpected_quarters": [d.isoformat() for d in extra],
        "raw_files": per_file.height,
        "total_rows": typed.height,
        "distinct_banks_CERT": typed["CERT"].n_unique(),
        "duplicate_CERT_REPDTE": dups,
        "null_CERT": null_cert,
        "quarters_not_matching_api_total": manifest_mismatch,
        "manifest_check": manifest_note,
    }
    return table.drop("qkey"), summary


# --------------------------------------------------------------------------
# Step 4 - write the layouts
# --------------------------------------------------------------------------
def write_layouts(typed):
    if BENCH_DIR.exists():
        shutil.rmtree(BENCH_DIR)
    BENCH_DIR.mkdir(parents=True)
    layouts = {}

    def timed(fn):
        t = time.perf_counter()
        fn()
        return time.perf_counter() - t

    p = BENCH_DIR / "fin.csv"
    layouts["CSV (1 file)"] = {"path": p, "write_s": timed(lambda: typed.write_csv(p))}

    for comp in ("uncompressed", "snappy", "zstd"):
        p = BENCH_DIR / f"fin_{comp}.parquet"
        layouts[f"Parquet {comp} (1 file)"] = {
            "path": p,
            "write_s": timed(lambda p=p, comp=comp: typed.write_parquet(p, compression=comp, statistics=True)),
        }

    qdir = BENCH_DIR / "by_quarter"

    def write_quarters():
        qdir.mkdir()
        for q in typed["REPDTE"].unique().sort().to_list():
            typed.filter(pl.col("REPDTE") == q).write_parquet(
                qdir / f"{q:%Y%m%d}.parquet", compression="zstd", statistics=True
            )

    layouts["Parquet zstd, 170 files by quarter"] = {"path": qdir, "write_s": timed(write_quarters)}

    ydir = BENCH_DIR / "by_year"

    def write_years(target=ydir):
        target.mkdir(parents=True, exist_ok=True)
        for y in typed["YEAR"].unique().sort().to_list():
            d = target / f"YEAR={y}"
            d.mkdir(exist_ok=True)
            typed.filter(pl.col("YEAR") == y).drop("YEAR").write_parquet(
                d / "part-0.parquet", compression="zstd", statistics=True
            )

    layouts["Parquet zstd, partitioned by YEAR"] = {"path": ydir, "write_s": timed(write_years)}
    return layouts, write_years


def scan(name, path, schema):
    if name.startswith("CSV"):
        return pl.scan_csv(path, schema=schema)
    if "partitioned" in name:
        return pl.scan_parquet(path.as_posix() + "/**/*.parquet", hive_partitioning=True)
    if "170 files" in name:
        return pl.scan_parquet(path.as_posix() + "/*.parquet", hive_partitioning=False)
    return pl.scan_parquet(path)


# --------------------------------------------------------------------------
# Step 5 - read benchmark
# --------------------------------------------------------------------------
def bench(fn, repeats):
    out = fn()  # warm-up run (not timed); also used for the result check
    times = []
    for _ in range(repeats):
        gc.collect()
        t = time.perf_counter()
        res = fn()
        times.append(time.perf_counter() - t)
        del res
    return out, times


def fingerprint(df, value_col):
    return (df.height, round(float(df[value_col].sum() or 0.0), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--skip-pandas", action="store_true")
    ap.add_argument("--keep-bench", action="store_true")
    args = ap.parse_args()

    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)

    # 0. machine
    info = machine_info()
    log("Machine: " + ", ".join(f"{k}={v}" for k, v in info.items()))
    (OUT_TAB / "part1_machine.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    # 1. raw
    log(f"Reading raw files from {RAW_FIN_DIR} ...")
    raw, per_file, raw_files = load_raw()
    log(f"Raw panel: {raw.height:,} rows x {raw.width} columns from {len(raw_files)} files")

    # 2. schema
    typed, text_cols = apply_schema(raw)
    log(f"Explicit schema applied. Text columns kept as String: {text_cols or 'none'}")
    schema_rows = [
        {"column": c, "raw_dtype": str(raw.schema.get(c, "-")), "final_dtype": str(t)}
        for c, t in typed.schema.items()
    ]
    pl.DataFrame(schema_rows).write_csv(OUT_TAB / "part1_schema.csv")

    # 3. completeness
    comp_table, comp = completeness(typed, per_file)
    comp_table.write_csv(OUT_TAB / "part1_completeness_by_quarter.csv")
    (OUT_TAB / "part1_completeness_summary.json").write_text(json.dumps(comp, indent=2), encoding="utf-8")
    log("Completeness: " + json.dumps(comp))

    # 4. layouts
    log(f"Writing 6 storage layouts to {BENCH_DIR} (outside OneDrive) ...")
    layouts, write_years = write_layouts(typed)

    # memory: how much RAM the same data needs with different types
    csv_path = layouts["CSV (1 file)"]["path"]
    mem_rows = [
        {"representation": "All columns as text (naive CSV read)",
         "in_memory_MB": pl.read_csv(csv_path, infer_schema_length=0).estimated_size("mb")},
        {"representation": "As downloaded (starter script types)",
         "in_memory_MB": raw.estimated_size("mb")},
        {"representation": "Explicit schema (Int32 / Date / Float64)",
         "in_memory_MB": typed.estimated_size("mb")},
    ]
    mem = pl.DataFrame(mem_rows)
    mem.write_csv(OUT_TAB / "part1_memory_by_schema.csv")
    log("\n" + to_markdown(mem))

    raw_size = dir_size_mb(RAW_FIN_DIR)
    csv_mb = dir_size_mb(csv_path)
    size_rows = [{"layout": "Raw download (starter, 170 files)", "files": len(raw_files),
                  "size_MB": raw_size, "vs_CSV_%": 100 * raw_size / csv_mb, "write_s": None}]
    for name, meta in layouts.items():
        mb = dir_size_mb(meta["path"])
        size_rows.append({"layout": name, "files": n_files(meta["path"]), "size_MB": mb,
                          "vs_CSV_%": 100 * mb / csv_mb, "write_s": meta["write_s"]})
    sizes = pl.DataFrame(size_rows)
    sizes.write_csv(OUT_TAB / "part1_storage_size.csv")
    log("\n" + to_markdown(sizes))

    # 5. read benchmark
    schema = typed.schema
    value_col = "ASSET" if "ASSET" in typed.columns else next(
        c for c, t in schema.items() if t == pl.Float64)
    three_cols = ["CERT", "REPDTE", value_col]
    queries = {
        "full_read": lambda lf: lf.collect(),
        "read_3_columns": lambda lf: lf.select(three_cols).collect(),
        f"read_year_{TEST_YEAR}": lambda lf: lf.filter(pl.col("YEAR") == TEST_YEAR).collect(),
    }

    rows, checks = [], {}
    for name, meta in layouts.items():
        for qname, q in queries.items():
            log(f"Benchmark: {name} | {qname} ({args.repeats} runs + warm-up)")
            out, times = bench(lambda: q(scan(name, meta["path"], schema)), args.repeats)
            checks.setdefault(qname, {})[name] = fingerprint(out, value_col)
            rows.append({"tool": "polars", "layout": name, "query": qname,
                         "median_s": statistics.median(times), "min_s": min(times),
                         "max_s": max(times), "runs": len(times)})
            del out

    if not args.skip_pandas:
        import pandas as pd

        pd_cases = {"CSV (1 file)": lambda: pd.read_csv(layouts["CSV (1 file)"]["path"]),
                    "Parquet zstd (1 file)": lambda: pd.read_parquet(layouts["Parquet zstd (1 file)"]["path"])}
        for name, fn in pd_cases.items():
            log(f"Benchmark: pandas | {name} | full_read")
            out, times = bench(fn, args.repeats)
            del out
            rows.append({"tool": "pandas", "layout": name, "query": "full_read",
                         "median_s": statistics.median(times), "min_s": min(times),
                         "max_s": max(times), "runs": len(times)})

    reads = pl.DataFrame(rows)
    reads.write_csv(OUT_TAB / "part1_read_benchmark.csv")

    # result check: every layout must return exactly the same data
    check_rows, all_ok = [], True
    for qname, d in checks.items():
        ref = next(iter(d.values()))
        for name, fp in d.items():
            ok = fp[0] == ref[0] and abs(fp[1] - ref[1]) <= 1e-6 * max(1.0, abs(ref[1]))
            all_ok &= ok
            check_rows.append({"query": qname, "layout": name, "rows": fp[0],
                               f"sum_{value_col}": fp[1], "same_as_reference": ok})
    pl.DataFrame(check_rows).write_csv(OUT_TAB / "part1_result_check.csv")
    log(f"Result check (all layouts return identical data): {'PASSED' if all_ok else 'FAILED'}")

    wide = reads.filter(pl.col("tool") == "polars").pivot(
        on="query", index="layout", values="median_s")
    log("\nMedian read time in seconds (Polars):\n" + to_markdown(wide))

    # 6. query plans: evidence of pushdown and partition pruning
    plans = []
    for name in ("CSV (1 file)", "Parquet zstd (1 file)",
                 "Parquet zstd, 170 files by quarter", "Parquet zstd, partitioned by YEAR"):
        lf = scan(name, layouts[name]["path"], schema).filter(
            pl.col("YEAR") == TEST_YEAR).select(three_cols)
        plans.append(f"===== {name} | optimized plan =====\n{lf.explain()}\n")
        plans.append(f"===== {name} | NOT optimized =====\n{lf.explain(optimized=False)}\n")
    ydir = layouts["Parquet zstd, partitioned by YEAR"]["path"]
    part_mb = dir_size_mb(ydir / f"YEAR={TEST_YEAR}")
    plans.append(f"Partition pruning: a query for {TEST_YEAR} only needs folder YEAR={TEST_YEAR} "
                 f"({part_mb:.1f} MB) out of {n_files(ydir)} files ({dir_size_mb(ydir):.1f} MB).")
    (OUT_TAB / "part1_query_plans.txt").write_text("\n".join(plans), encoding="utf-8")

    # figures
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 4.5))
        s = sizes.sort("size_MB")
        ax.barh(s["layout"].to_list(), s["size_MB"].to_list(), color="#3b6ea5")
        for i, v in enumerate(s["size_MB"].to_list()):
            ax.text(v, i, f" {v:,.0f} MB", va="center", fontsize=8)
        ax.set_xlabel("Size on disk (MB)")
        ax.set_title("Figure 1. Disk size of the same FDIC panel by storage layout")
        fig.tight_layout()
        fig.savefig(OUT_FIG / "part1_storage_size.png", dpi=200)
        plt.close(fig)

        qnames = list(queries)
        names = wide["layout"].to_list()
        fig, ax = plt.subplots(figsize=(10, 5))
        width = 0.8 / len(qnames)
        for j, qn in enumerate(qnames):
            ax.bar([i + j * width for i in range(len(names))], wide[qn].to_list(), width, label=qn)
        ax.set_xticks([i + width for i in range(len(names))])
        ax.set_xticklabels(names, rotation=20, ha="right", fontsize=8)
        ax.set_ylabel(f"Median seconds ({args.repeats} runs)")
        ax.set_yscale("log")
        ax.set_title("Figure 2. Read time by storage layout and query (Polars, log scale)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT_FIG / "part1_read_time.png", dpi=200)
        plt.close(fig)
        log("Figures saved to output/figures/")
    except ImportError:
        log("matplotlib not installed - figures skipped (pip install matplotlib)")

    # markdown summary for the report
    md = ["# Part 1 - Storage benchmark results", "",
          "Machine: " + ", ".join(f"{k}={v}" for k, v in info.items()), "",
          "## Completeness", "```", json.dumps(comp, indent=2), "```", "",
          "## In-memory size by schema", to_markdown(mem), "",
          "## Size on disk", to_markdown(sizes), "",
          f"## Median read time, seconds ({args.repeats} runs after 1 warm-up)",
          to_markdown(reads), "",
          f"Result check across layouts: {'PASSED' if all_ok else 'FAILED'}"]
    (OUT_TAB / "part1_summary.md").write_text("\n".join(md), encoding="utf-8")

    # 7. save chosen layout for the next parts
    log(f"Saving chosen layout (Parquet zstd, partitioned by YEAR) to {FINAL_DIR} ...")
    if FINAL_DIR.exists():
        shutil.rmtree(FINAL_DIR)
    write_years(FINAL_DIR)

    if not args.keep_bench:
        shutil.rmtree(BENCH_DIR, ignore_errors=True)
        log("Temporary benchmark files deleted.")
    log("DONE. Results are in output/tables/ and output/figures/")


if __name__ == "__main__":
    main()