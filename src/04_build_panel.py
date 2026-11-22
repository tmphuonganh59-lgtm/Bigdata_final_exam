"""
Part 2b - Clean, point-in-time bank-quarter panel with failure labels (BFT65B)

Cleaning rules (each one is logged with the number of rows affected):
  R1  drop rows with ASSET missing or <= 0 (no valid balance sheet)
  R2  capital ratio exactly 0 while equity > 0  -> missing ('not reported')
  R3  impossible negative balance-sheet stocks  -> missing
  R4  YTD income fields -> quarterly values (FDIC quarterly field preferred,
      otherwise YTD(q) - YTD(q-1) in the same year, only if q-1 exists)
  R5  internal gaps kept and flagged (HAS_PREV_Q); nothing is imputed here
Exits:
  every bank keeps all its rows; EXIT_TYPE = active / failure / assistance /
  other_exit (mergers etc.). Only the failures table defines a failure.
Label (task definition):
  Y = 1 if the bank has a failure event in (q, q + 4 quarters]
  Y is missing after 2025Q2 (label window not complete yet).
  Y_FAILURE_ONLY: same, counting RESTYPE == FAILURE only (sensitivity check).
  LATE_SIGNAL: event within 60 days of REPDTE (report not yet public then).

Output: data/processed/panel/YEAR=yyyy/part-0.parquet (+ summary tables)

Run from the project root:
    python -X utf8 src/04_build_panel.py

Author: To Mai Phuong Anh. Code drafted with help from Claude (Anthropic).
"""

import json
import shutil
from datetime import date, datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "fdic"
FIN_DIR = ROOT / "data" / "processed" / "financials"
PANEL_DIR = ROOT / "data" / "processed" / "panel"
OUT_TAB = ROOT / "output" / "tables"

PANEL_END = date(2026, 6, 30)
LABEL_END = date(2025, 6, 30)     # last quarter with a complete 4-quarter label window
HORIZON = 4                       # quarters
LATE_DAYS = 60

YTD_FLOWS = ["INTINC", "EINTEXP", "ELNATR", "NTLNLS", "NETINC", "NONII", "NONIX"]
QUARTERLY_PROVIDED = {"NETINC": "NETINCQ", "NONII": "NONIIQ", "NONIX": "NONIXQ"}
NON_NEGATIVE = ["ASSET", "DEP", "DEPDOM", "LNLSGR", "LNLSNET", "LNATRES", "LNRE",
                "LNCI", "LNCON", "SC", "CHBAL", "P3ASSET", "P9ASSET", "NAASSET",
                "NCLNLS", "ORE", "BRO"]
CAPITAL_RATIOS = ["RBC1AAJ", "RBCRWAJ"]


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def to_markdown(df, max_rows=60):
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in df.head(max_rows).iter_rows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(f"{v:,.4f}" if abs(v) < 1 else f"{v:,.2f}")
            else:
                cells.append("" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def parse_mdy(col):
    parts = pl.col(col).str.strip_chars().str.split("/")
    return pl.date(
        parts.list.get(2, null_on_oob=True).cast(pl.Int32, strict=False),
        parts.list.get(0, null_on_oob=True).cast(pl.Int32, strict=False),
        parts.list.get(1, null_on_oob=True).cast(pl.Int32, strict=False),
    )


def qidx(col):
    return pl.col(col).dt.year().cast(pl.Int32) * 4 + (pl.col(col).dt.month().cast(pl.Int32) - 1) // 3


def main():
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    clog = []

    # ------------------------------------------------------------------ load
    fin = pl.scan_parquet(FIN_DIR.as_posix() + "/**/*.parquet", hive_partitioning=True).collect()
    fin = fin.with_columns(
        pl.col("YEAR").cast(pl.Int16),
        qidx("REPDTE").alias("QIDX"),
        (pl.col("REPDTE").dt.month() // 3).cast(pl.Int8).alias("QOFY"),
    ).sort(["CERT", "QIDX"])
    n0 = fin.height
    log(f"Loaded {n0:,} bank-quarters")

    # R1 invalid balance sheet
    fin = fin.filter(pl.col("ASSET").is_not_null() & (pl.col("ASSET") > 0))
    clog.append({"rule": "R1 drop rows with ASSET missing or <= 0", "rows_affected": n0 - fin.height})

    # R2 capital ratios: 0 with positive equity means 'not reported'
    #     (before 1990: rules not yet in force; from 2020: banks using the
    #      Community Bank Leverage Ratio do not report risk-based ratios)
    periods = {"1984-1989": pl.col("YEAR") < 1990,
               "1990-2019": (pl.col("YEAR") >= 1990) & (pl.col("YEAR") < 2020),
               "2020-2026": pl.col("YEAR") >= 2020}
    for c in CAPITAL_RATIOS:
        cond = (pl.col(c) == 0) & (pl.col("EQ") > 0)
        for pname, pcond in periods.items():
            clog.append({"rule": f"R2 {c} == 0 with EQ > 0 -> missing ({pname})",
                         "rows_affected": fin.filter(cond & pcond).height})
        fin = fin.with_columns(pl.when(cond).then(None).otherwise(pl.col(c)).alias(c))

    # Diagnostic (no change): deposits above assets should only happen when equity < 0
    clog.append({"rule": "CHECK DEP > ASSET with EQ < 0 (insolvent, kept)",
                 "rows_affected": fin.filter((pl.col("DEP") > pl.col("ASSET")) & (pl.col("EQ") < 0)).height})
    clog.append({"rule": "CHECK DEP > ASSET with EQ >= 0 (inconsistent, kept and flagged)",
                 "rows_affected": fin.filter((pl.col("DEP") > pl.col("ASSET")) & (pl.col("EQ") >= 0)).height})
    fin = fin.with_columns(((pl.col("DEP") > pl.col("ASSET")) & (pl.col("EQ") >= 0))
                           .fill_null(False).alias("FLAG_DEP_GT_ASSET"))

    # R3 impossible negatives
    for c in NON_NEGATIVE:
        n = fin.filter(pl.col(c) < 0).height
        if n:
            fin = fin.with_columns(pl.when(pl.col(c) < 0).then(None).otherwise(pl.col(c)).alias(c))
        clog.append({"rule": f"R3 {c} < 0 -> missing", "rows_affected": n})

    # R4 YTD -> quarterly (uses only the current and the previous quarter: no look-ahead)
    prev_q = pl.col("QIDX").shift(1).over("CERT")
    fin = fin.with_columns((prev_q == pl.col("QIDX") - 1).fill_null(False).alias("HAS_PREV_Q"))
    for v in YTD_FLOWS:
        derived = (pl.when(pl.col("QOFY") == 1).then(pl.col(v))
                   .when(pl.col("HAS_PREV_Q")).then(pl.col(v) - pl.col(v).shift(1).over("CERT"))
                   .otherwise(None))
        if v in QUARTERLY_PROVIDED:
            expr = pl.coalesce(pl.col(QUARTERLY_PROVIDED[v]), derived)
        else:
            expr = derived
        fin = fin.with_columns(expr.alias(f"{v}_QTR"))
        clog.append({"rule": f"R4 {v}_QTR missing (Q2-Q4 without previous quarter)",
                     "rows_affected": fin.filter(pl.col(f"{v}_QTR").is_null() & pl.col(v).is_not_null()).height})
    clog.append({"rule": "R5 rows without the previous quarter (gap or first report), flagged HAS_PREV_Q",
                 "rows_affected": fin.filter(~pl.col("HAS_PREV_Q")).height})

    # ------------------------------------------------------------------ events
    fail = (pl.read_parquet(RAW / "failures.parquet")
            .with_columns(parse_mdy("FAILDATE").alias("FAIL_DT"),
                          pl.col("CERT").cast(pl.Int32, strict=False))
            .filter(pl.col("CERT").is_not_null() & (pl.col("FAIL_DT") >= date(1984, 1, 1)))
            .with_columns(qidx("FAIL_DT").alias("FAIL_Q"))
            .select(["CERT", "FAIL_DT", "FAIL_Q", "RESTYPE", "COST"]))
    fail.write_parquet(ROOT / "data" / "processed" / "failures_clean.parquet")

    rows = fin.with_row_index("ROW_ID")
    base = rows.select(["ROW_ID", "CERT", "QIDX", "REPDTE"])

    def next_event(events, suffix):
        hit = (base.join(events, on="CERT", how="inner")
               .filter((pl.col("FAIL_Q") > pl.col("QIDX")) & (pl.col("FAIL_Q") <= pl.col("QIDX") + HORIZON))
               .sort(["ROW_ID", "FAIL_DT"])
               .group_by("ROW_ID", maintain_order=True)
               .agg(pl.col("FAIL_DT").first().alias(f"NEXT_EVENT_DT{suffix}"),
                    pl.col("FAIL_Q").first().alias(f"NEXT_EVENT_Q{suffix}"),
                    pl.col("RESTYPE").first().alias(f"NEXT_EVENT_TYPE{suffix}")))
        return hit

    hit_all = next_event(fail, "")
    hit_fail = next_event(fail.filter(pl.col("RESTYPE") == "FAILURE"), "_F")
    rows = (rows.join(hit_all, on="ROW_ID", how="left")
            .join(hit_fail.select(["ROW_ID", "NEXT_EVENT_Q_F"]), on="ROW_ID", how="left"))

    avail = pl.col("REPDTE") <= LABEL_END
    rows = rows.with_columns(
        avail.alias("LABEL_AVAILABLE"),
        pl.when(avail).then(pl.col("NEXT_EVENT_Q").is_not_null().cast(pl.Int8)).otherwise(None).alias("Y"),
        pl.when(avail).then(pl.col("NEXT_EVENT_Q_F").is_not_null().cast(pl.Int8)).otherwise(None)
        .alias("Y_FAILURE_ONLY"),
        (pl.col("NEXT_EVENT_Q") - pl.col("QIDX")).alias("QUARTERS_TO_EVENT"),
        ((pl.col("NEXT_EVENT_DT") - pl.col("REPDTE")).dt.total_days() <= LATE_DAYS)
        .fill_null(False).alias("LATE_SIGNAL"),
    ).drop("NEXT_EVENT_Q_F")

    # ------------------------------------------------------------------ exits
    inst = pl.read_parquet(RAW / "institutions.parquet").with_columns(
        pl.col("CERT").cast(pl.Int32, strict=False)).select(["CERT", "CHANGEC1"])
    last = rows.group_by("CERT").agg(pl.col("QIDX").max().alias("LAST_Q"),
                                     pl.col("REPDTE").max().alias("LAST_REPDTE"))
    later_ev = (last.join(fail, on="CERT", how="inner")
                .filter(pl.col("FAIL_Q") > pl.col("LAST_Q"))
                .sort(["CERT", "FAIL_DT"])
                .group_by("CERT", maintain_order=True)
                .agg(pl.col("RESTYPE").first().alias("EXIT_EVENT")))
    exits = (last.join(later_ev, on="CERT", how="left").join(inst, on="CERT", how="left")
             .with_columns(
                 pl.when(pl.col("LAST_REPDTE") == PANEL_END).then(pl.lit("active"))
                 .when(pl.col("EXIT_EVENT") == "FAILURE").then(pl.lit("failure"))
                 .when(pl.col("EXIT_EVENT") == "ASSISTANCE").then(pl.lit("assistance"))
                 .otherwise(pl.lit("other_exit")).alias("EXIT_TYPE"))
             .select(["CERT", "LAST_REPDTE", "EXIT_TYPE", "CHANGEC1"]))
    rows = rows.join(exits, on="CERT", how="left").drop("ROW_ID")

    # ------------------------------------------------------------------ save panel
    if PANEL_DIR.exists():
        shutil.rmtree(PANEL_DIR)
    for y in rows["YEAR"].unique().sort().to_list():
        d = PANEL_DIR / f"YEAR={y}"
        d.mkdir(parents=True, exist_ok=True)
        rows.filter(pl.col("YEAR") == y).drop("YEAR").write_parquet(d / "part-0.parquet", compression="zstd")
    log(f"Panel saved: {rows.height:,} rows x {rows.width} columns -> {PANEL_DIR}")

    # ------------------------------------------------------------------ summaries
    cl = pl.DataFrame(clog)
    cl.write_csv(OUT_TAB / "part2_cleaning_log.csv")

    exit_tab = exits.group_by("EXIT_TYPE").agg(pl.len().alias("banks")).sort("banks", descending=True)
    exit_tab.write_csv(OUT_TAB / "part2_exit_types.csv")

    lab = rows.filter(pl.col("LABEL_AVAILABLE"))
    # failure events that produce at least one positive row, by year of the event
    ev_year = (lab.filter(pl.col("Y") == 1)
               .select(["CERT", "NEXT_EVENT_DT", "NEXT_EVENT_TYPE"]).unique()
               .with_columns(pl.col("NEXT_EVENT_DT").dt.year().alias("EVENT_YEAR"))
               .group_by("EVENT_YEAR")
               .agg(pl.len().alias("events_with_positive_rows"),
                    (pl.col("NEXT_EVENT_TYPE") == "FAILURE").sum().alias("of_which_FAILURE"))
               .sort("EVENT_YEAR"))
    by_year = (lab.group_by("YEAR")
               .agg(pl.len().alias("bank_quarters"), pl.col("CERT").n_unique().alias("banks"),
                    pl.col("Y").sum().alias("positives_Y"),
                    pl.col("Y_FAILURE_ONLY").sum().alias("positives_failure_only"),
                    pl.col("LATE_SIGNAL").sum().alias("late_signal_rows"))
               .with_columns((pl.col("positives_Y") / pl.col("bank_quarters")).alias("positive_rate"))
               .sort("YEAR")
               .join(ev_year.rename({"EVENT_YEAR": "YEAR"}).with_columns(pl.col("YEAR").cast(pl.Int16)),
                     on="YEAR", how="left"))
    by_year.write_csv(OUT_TAB / "part2_labels_by_year.csv")

    summary = {
        "rows_loaded": n0,
        "rows_in_panel": rows.height,
        "rows_with_label": lab.height,
        "positives_Y": int(lab["Y"].sum()),
        "positive_rate": float(lab["Y"].mean()),
        "positives_failure_only": int(lab["Y_FAILURE_ONLY"].sum()),
        "late_signal_positive_rows": int(lab.filter(pl.col("Y") == 1)["LATE_SIGNAL"].sum()),
        "distinct_events_with_positive_rows": int(ev_year["events_with_positive_rows"].sum()),
        "banks": exits.height,
    }
    (OUT_TAB / "part2_panel_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = ["# Part 2 - Clean panel and labels", "", "## Summary", "```", json.dumps(summary, indent=2), "```", "",
          "## Cleaning log", to_markdown(cl), "", "## Exit types (banks)", to_markdown(exit_tab), "",
          "## Labels by year (quarters up to 2025Q2)", to_markdown(by_year, max_rows=60)]
    (OUT_TAB / "part2_panel_report.md").write_text("\n".join(md), encoding="utf-8")
    log("Summary: " + json.dumps(summary))
    log("DONE. Report: output/tables/part2_panel_report.md")


if __name__ == "__main__":
    main()