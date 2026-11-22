"""
Part 2a - Automated data-quality report (BFT65B final project)

Checks every table systematically and writes:
  output/tables/part2_quality_report.md   (main report, for the appendix)
  output/tables/part2_*.csv               (full tables)
  output/figures/part2_missing_heatmap.png
  output/figures/part2_zero_heatmap.png

Run from the project root:
    python -X utf8 src/03_quality_report.py

Author: To Mai Phuong Anh. Code drafted with help from Claude (Anthropic).
"""

import json
from datetime import date, datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "fdic"
FIN_DIR = ROOT / "data" / "processed" / "financials"
OUT_TAB = ROOT / "output" / "tables"
OUT_FIG = ROOT / "output" / "figures"

PANEL_START = date(1984, 3, 31)
PANEL_END = date(2026, 6, 30)

# Variable groups (FDIC field dictionary)
YTD_FLOWS = ["INTINC", "EINTEXP", "ELNATR", "NTLNLS", "NETINC", "NONII", "NONIX"]
QUARTERLY_PROVIDED = {"NETINC": "NETINCQ", "NONII": "NONIIQ", "NONIX": "NONIXQ"}
# Balance-sheet stocks that cannot be negative
NON_NEGATIVE = ["ASSET", "DEP", "DEPDOM", "LNLSGR", "LNLSNET", "LNATRES", "LNRE",
                "LNCI", "LNCON", "SC", "CHBAL", "P3ASSET", "P9ASSET", "NAASSET",
                "NCLNLS", "ORE", "BRO"]
RATIOS = ["ROA", "ROE", "NIMY", "RBC1AAJ", "RBCRWAJ"]


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
    if df.height > max_rows:
        lines.append(f"\n*({df.height - max_rows} more rows in the CSV file)*")
    return "\n".join(lines)


def parse_mdy(col):
    """'4/19/1934' or '04/19/1934' -> Date (robust to missing zero padding)."""
    parts = pl.col(col).str.strip_chars().str.split("/")
    return pl.date(
        parts.list.get(2, null_on_oob=True).cast(pl.Int32, strict=False),
        parts.list.get(0, null_on_oob=True).cast(pl.Int32, strict=False),
        parts.list.get(1, null_on_oob=True).cast(pl.Int32, strict=False),
    )


def qidx(col):
    """Quarter index: year*4 + quarter-1, so consecutive quarters differ by 1."""
    return pl.col(col).dt.year().cast(pl.Int32) * 4 + (pl.col(col).dt.month().cast(pl.Int32) - 1) // 3


def heatmap(table, value_name, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    years = table["YEAR"].to_list()
    vars_ = [c for c in table.columns if c != "YEAR"]
    data = table.select(vars_).to_numpy().T
    fig, ax = plt.subplots(figsize=(14, 8))
    im = ax.imshow(data, aspect="auto", cmap="Reds", vmin=0, vmax=1)
    ax.set_yticks(range(len(vars_)))
    ax.set_yticklabels(vars_, fontsize=7)
    step = 2
    ax.set_xticks(range(0, len(years), step))
    ax.set_xticklabels(years[::step], rotation=90, fontsize=7)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label=value_name)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    md = ["# Part 2 - Automated data-quality report",
          f"Generated {datetime.now():%Y-%m-%d %H:%M} by src/03_quality_report.py", ""]
    summary = {}

    # ------------------------------------------------------------------ load
    fin = pl.scan_parquet(FIN_DIR.as_posix() + "/**/*.parquet", hive_partitioning=True).collect()
    fin = fin.with_columns(pl.col("YEAR").cast(pl.Int32), qidx("REPDTE").alias("QIDX"))
    num_vars = [c for c, t in fin.schema.items() if t == pl.Float64]
    log(f"Financials: {fin.height:,} rows, {len(num_vars)} numeric variables")

    fail = pl.read_parquet(RAW / "failures.parquet").with_columns(
        parse_mdy("FAILDATE").alias("FAIL_DT"),
        pl.col("CERT").cast(pl.Int32, strict=False),
    )
    inst = pl.read_parquet(RAW / "institutions.parquet").with_columns(
        pl.col("CERT").cast(pl.Int32, strict=False),
        parse_mdy("ENDEFYMD").alias("END_DT"),
    )

    # ===================================================== A. FINANCIALS
    md += ["## A. Financials table", ""]

    # A1 missing share by variable x year
    miss = fin.group_by("YEAR").agg([pl.col(c).is_null().mean().alias(c) for c in num_vars]).sort("YEAR")
    miss.write_csv(OUT_TAB / "part2_missing_by_year.csv")
    heatmap(miss, "share missing", "Figure 3. Share of missing values by variable and year",
            OUT_FIG / "part2_missing_heatmap.png")
    overall_miss = (fin.select([pl.col(c).is_null().mean().alias(c) for c in num_vars])
                    .unpivot(variable_name="variable", value_name="share_missing")
                    .sort("share_missing", descending=True))
    overall_miss.write_csv(OUT_TAB / "part2_missing_overall.csv")
    md += ["### A1. Missing values (overall; by year in part2_missing_by_year.csv, Figure 3)",
           to_markdown(overall_miss.filter(pl.col("share_missing") > 0)), ""]

    # A2 exact-zero share by variable x year (zeros used as 'not reported')
    zero = fin.group_by("YEAR").agg([(pl.col(c) == 0).mean().alias(c) for c in num_vars]).sort("YEAR")
    zero.write_csv(OUT_TAB / "part2_zero_by_year.csv")
    heatmap(zero, "share exactly 0", "Figure 4. Share of exact zeros by variable and year",
            OUT_FIG / "part2_zero_heatmap.png")
    cap_zero = (fin.group_by("YEAR")
                .agg([(pl.col(c) == 0).mean().alias(f"{c}_zero_share") for c in ("RBC1AAJ", "RBCRWAJ")]
                     + [pl.col(c).is_null().mean().alias(f"{c}_null_share") for c in ("RBC1AAJ", "RBCRWAJ")])
                .sort("YEAR"))
    cap_zero.write_csv(OUT_TAB / "part2_capital_ratio_zero_null.csv")
    md += ["### A2. Capital ratios: exact zeros and nulls by year",
           "A ratio of exactly 0 for a bank with positive equity is impossible, so a high zero share "
           "in early years means 'not reported' (risk-based capital rules started around 1990).",
           to_markdown(cap_zero, max_rows=50), ""]

    # A3 impossible negatives
    neg_rows = []
    for c in NON_NEGATIVE:
        if c in fin.columns:
            n = fin.filter(pl.col(c) < 0).height
            neg_rows.append({"variable": c, "negative_rows": n, "share": n / fin.height})
    neg = pl.DataFrame(neg_rows)
    neg.write_csv(OUT_TAB / "part2_impossible_negatives.csv")
    asset_bad = fin.filter(pl.col("ASSET").is_null() | (pl.col("ASSET") <= 0)).height
    eq_neg = fin.filter(pl.col("EQ") < 0).height
    summary.update({"rows_asset_null_or_nonpositive": asset_bad, "rows_negative_equity": eq_neg})
    md += ["### A3. Impossible negative values (balance-sheet stocks)", to_markdown(neg), "",
           f"Rows with ASSET null or <= 0: **{asset_bad:,}**. "
           f"Rows with negative equity (EQ < 0): **{eq_neg:,}** (economically possible for insolvent "
           "banks, so kept: it is a strong failure signal).", ""]

    # A4 accounting identities
    tol = pl.max_horizontal(pl.lit(1.0), 0.01 * pl.col("ASSET").abs())
    ident = {
        "DEP > ASSET": fin.filter(pl.col("DEP") > pl.col("ASSET") + tol).height,
        "EQ > ASSET": fin.filter(pl.col("EQ") > pl.col("ASSET") + tol).height,
        "DEPDOM > DEP": fin.filter(pl.col("DEPDOM") > pl.col("DEP") + tol).height,
        "LNLSNET > LNLSGR": fin.filter(pl.col("LNLSNET") > pl.col("LNLSGR") + tol).height,
        "NCLNLS > LNLSGR": fin.filter(pl.col("NCLNLS") > pl.col("LNLSGR") + tol).height,
        "LNATRES > LNLSGR": fin.filter(pl.col("LNATRES") > pl.col("LNLSGR") + tol).height,
    }
    ident_df = pl.DataFrame({"identity_violated": list(ident), "rows": list(ident.values())})
    ident_df.write_csv(OUT_TAB / "part2_identity_checks.csv")
    md += ["### A4. Accounting identity checks (tolerance: max(1, 1% of ASSET))", to_markdown(ident_df), ""]

    # A5 ratio ranges
    rr = []
    for c in RATIOS:
        s = fin[c].drop_nulls()
        rr.append({"ratio": c, "min": s.min(), "p01": s.quantile(0.01), "median": s.median(),
                   "p99": s.quantile(0.99), "max": s.max(),
                   "abs_gt_100": int((s.abs() > 100).sum())})
    rr_df = pl.DataFrame(rr)
    rr_df.write_csv(OUT_TAB / "part2_ratio_ranges.csv")
    md += ["### A5. Ratio ranges (percent)", to_markdown(rr_df), ""]

    # A6 distribution / outliers for all numeric variables
    dist = []
    for c in num_vars:
        s = fin[c].drop_nulls()
        if s.len() == 0:
            continue
        p01, p99 = s.quantile(0.01), s.quantile(0.99)
        med = s.median()
        mad = (s - med).abs().median()
        far = int(((s - med).abs() > 10 * 1.4826 * mad).sum()) if mad and mad > 0 else None
        dist.append({"variable": c, "min": s.min(), "p01": p01, "median": med, "p99": p99,
                     "max": s.max(), "beyond_10_MAD": far})
    dist_df = pl.DataFrame(dist)
    dist_df.write_csv(OUT_TAB / "part2_distributions.csv")
    md += ["### A6. Distributions and extreme values (10 robust SD = 10 x 1.4826 x MAD)",
           "Amounts are heavily skewed by bank size, so outliers are handled later with size-scaled "
           "ratios and winsorisation fitted on the training period only (Part 4).",
           to_markdown(dist_df), ""]

    # A7 duplicates and gaps in each bank's quarterly series
    dups = fin.height - fin.select(["CERT", "REPDTE"]).unique().height
    gaps = (fin.group_by("CERT")
            .agg(pl.len().alias("n"), pl.col("QIDX").min().alias("first"), pl.col("QIDX").max().alias("last"))
            .with_columns((pl.col("last") - pl.col("first") + 1 - pl.col("n")).alias("missing_quarters")))
    banks_with_gaps = gaps.filter(pl.col("missing_quarters") > 0).height
    summary.update({"duplicate_CERT_REPDTE": dups, "banks": gaps.height,
                    "banks_with_internal_gaps": banks_with_gaps,
                    "missing_internal_quarters": int(gaps["missing_quarters"].sum())})
    gaps.filter(pl.col("missing_quarters") > 0).sort("missing_quarters", descending=True) \
        .write_csv(OUT_TAB / "part2_series_gaps.csv")
    md += ["### A7. Duplicates and gaps in bank series",
           f"Duplicate (CERT, REPDTE): **{dups}**. Banks: **{gaps.height:,}**. "
           f"Banks with at least one missing quarter between their first and last report: "
           f"**{banks_with_gaps:,}** ({int(gaps['missing_quarters'].sum()):,} missing bank-quarters).", ""]

    # A8 YTD check: derive quarterly values and compare with FDIC quarterly fields
    srt = fin.sort(["CERT", "QIDX"])
    qy = (pl.col("REPDTE").dt.month() // 3)
    prev_q = pl.col("QIDX").shift(1).over("CERT")
    ytd_rows = []
    for ytd, qcol in QUARTERLY_PROVIDED.items():
        derived = (pl.when(qy == 1).then(pl.col(ytd))
                   .when(prev_q == pl.col("QIDX") - 1).then(pl.col(ytd) - pl.col(ytd).shift(1).over("CERT"))
                   .otherwise(None))
        t = srt.with_columns(derived.alias("derived"), qy.alias("QOFY")).filter(
            pl.col("derived").is_not_null() & pl.col(qcol).is_not_null())
        for label, sub in (("Q1", t.filter(pl.col("QOFY") == 1)), ("Q2-Q4", t.filter(pl.col("QOFY") > 1))):
            match = sub.filter((pl.col("derived") - pl.col(qcol)).abs() <= 1).height
            ytd_rows.append({"ytd_field": ytd, "fdic_quarterly_field": qcol, "quarters": label,
                             "rows_compared": sub.height,
                             "share_matching_within_1k": match / sub.height if sub.height else None})
    ytd_df = pl.DataFrame(ytd_rows)
    ytd_df.write_csv(OUT_TAB / "part2_ytd_check.csv")
    cum = (srt.with_columns(qy.alias("QOFY"))
           .group_by("QOFY").agg(pl.col("INTINC").median().alias("median_INTINC"),
                                  pl.col("NETINC").median().alias("median_NETINC"))
           .sort("QOFY"))
    cum.write_csv(OUT_TAB / "part2_ytd_median_by_quarter.csv")
    md += ["### A8. Year-to-date (YTD) income fields",
           "Income and expense fields (" + ", ".join(YTD_FLOWS) + ") are cumulative from January. "
           "Evidence: the median grows steadily from Q1 to Q4 within a year:",
           to_markdown(cum), "",
           "Quarterly values are derived as Q1 = YTD(Q1) and Qk = YTD(Qk) - YTD(Qk-1) within the same "
           "year, only when the previous quarter exists. The derivation is validated against the "
           "quarterly fields that FDIC also publishes:",
           to_markdown(ytd_df), ""]

    # ===================================================== B. FAILURES
    md += ["## B. Failures table", ""]
    fail_scope = fail.filter((pl.col("FAIL_DT") >= date(1984, 1, 1)))
    by_type = fail.group_by("RESTYPE").agg(
        pl.len().alias("all_events"),
        (pl.col("FAIL_DT") >= date(1984, 1, 1)).sum().alias("events_1984_on"),
        pl.col("CERT").is_null().sum().alias("missing_CERT"),
        pl.col("COST").is_null().sum().alias("missing_COST"))
    by_type.write_csv(OUT_TAB / "part2_failures_by_type.csv")
    bad_dates = fail.filter(pl.col("FAIL_DT").is_null()).height
    multi = fail_scope.filter(pl.col("CERT").is_not_null()).group_by("CERT").len().filter(pl.col("len") > 1).height
    md += ["### B1. Event types, missing keys and costs", to_markdown(by_type), "",
           f"Unparseable FAILDATE: **{bad_dates}**. Banks with more than one event since 1984: **{multi}**.", ""]

    # B2 link failures to financials + gap between last report and failure
    fin_q = fin.select(["CERT", "QIDX", "REPDTE"])
    ev = (fail_scope.filter(pl.col("CERT").is_not_null())
          .with_columns(qidx("FAIL_DT").alias("FAIL_Q"))
          .with_row_index("EVENT_ID"))
    last_before = (ev.join(fin_q, on="CERT", how="inner")
                   .filter(pl.col("QIDX") < pl.col("FAIL_Q"))
                   .group_by("EVENT_ID")
                   .agg(pl.col("QIDX").max().alias("LAST_Q"), pl.col("REPDTE").max().alias("LAST_REPDTE")))
    ev = ev.join(last_before, on="EVENT_ID", how="left").with_columns(
        (pl.col("FAIL_Q") - pl.col("LAST_Q")).alias("QUARTERS_AFTER_LAST_REPORT"),
        (pl.col("FAIL_DT") - pl.col("LAST_REPDTE")).dt.total_days().alias("DAYS_AFTER_LAST_REPORT"))
    link = (ev.with_columns(
        pl.when(pl.col("LAST_Q").is_null()).then(pl.lit("no report before event"))
        .when(pl.col("QUARTERS_AFTER_LAST_REPORT") <= 4)
        .then(pl.col("QUARTERS_AFTER_LAST_REPORT").cast(pl.String) + pl.lit(" quarter(s)"))
        .otherwise(pl.lit("> 4 quarters")).alias("gap"))
        .group_by(["RESTYPE", "gap"]).len().sort(["RESTYPE", "gap"]))
    link.write_csv(OUT_TAB / "part2_failure_link_gap.csv")
    linked = ev.filter(pl.col("LAST_Q").is_not_null()).height
    usable = ev.filter(pl.col("QUARTERS_AFTER_LAST_REPORT") <= 4).height
    within_60 = ev.filter(pl.col("DAYS_AFTER_LAST_REPORT") <= 60).height
    no_cert_scope = fail_scope.filter(pl.col("CERT").is_null()).height
    summary.update({"events_since_1984": fail_scope.height, "events_since_1984_missing_CERT": no_cert_scope,
                    "events_linked_to_financials": linked, "events_usable_for_label_gap_le_4q": usable,
                    "events_within_60_days_of_last_report": within_60})
    md += ["### B2. Linking failures to financials",
           f"Events since 1984: **{fail_scope.height:,}** ({no_cert_scope} without CERT). "
           f"Linked to at least one earlier financial report: **{linked:,}** "
           f"({linked / max(1, ev.height):.1%} of events with CERT). "
           f"Last report at most 4 quarters before the event (so a positive label exists): **{usable:,}**.",
           "", "Gap between the last financial report and the event (quarters):", to_markdown(link), "",
           f"**Point-in-time note:** {within_60:,} events happen within 60 days after the last report date. "
           "Call Reports are filed about 30 days after quarter end and published later, so at the "
           "real decision date such a report was not yet available. These cases are flagged in the panel.",
           ""]

    # ===================================================== C. INSTITUTIONS
    md += ["## C. Institutions table and exits", ""]
    fail_certs = fail.filter(pl.col("CERT").is_not_null()).select("CERT").unique().with_columns(
        pl.lit(True).alias("IN_FAILURES"))
    last_rep = fin.group_by("CERT").agg(pl.col("REPDTE").max().alias("LAST_REPDTE"))
    exited = (last_rep.filter(pl.col("LAST_REPDTE") < PANEL_END)
              .join(inst.select(["CERT", "CHANGEC1", "ACTIVE"]), on="CERT", how="left")
              .join(fail_certs, on="CERT", how="left")
              .with_columns(pl.col("IN_FAILURES").fill_null(False)))
    code_tab = (exited.group_by("CHANGEC1")
                .agg(pl.len().alias("exited_banks"), pl.col("IN_FAILURES").sum().alias("in_failures_table"))
                .with_columns((pl.col("in_failures_table") / pl.col("exited_banks")).alias("share_in_failures"))
                .sort("exited_banks", descending=True))
    code_tab.write_csv(OUT_TAB / "part2_exit_codes_vs_failures.csv")
    not_in_inst = fin.select("CERT").unique().join(inst.select("CERT"), on="CERT", how="anti").height
    active_but_stopped = last_rep.join(inst.select(["CERT", "ACTIVE"]), on="CERT").filter(
        (pl.col("ACTIVE") == 1) & (pl.col("LAST_REPDTE") < PANEL_END)).height
    inactive_but_reporting = last_rep.join(inst.select(["CERT", "ACTIVE"]), on="CERT").filter(
        (pl.col("ACTIVE") == 0) & (pl.col("LAST_REPDTE") == PANEL_END)).height
    summary.update({"banks_exited_before_2026Q2": exited.height,
                    "exited_banks_in_failures_table": int(exited["IN_FAILURES"].sum()),
                    "financial_CERT_not_in_institutions": not_in_inst,
                    "active_flag_but_stopped_reporting": active_but_stopped,
                    "inactive_flag_but_reporting_2026Q2": inactive_but_reporting})
    md += ["### C1. Why banks stop reporting: exit code (CHANGEC1) vs the failures table",
           "Instead of assuming what each code means, each code is cross-checked against the failures "
           "table. Only banks in the failures table are labelled as failures; every other exit "
           "(mainly mergers) stays in the panel with y = 0 until it exits, which avoids survivorship bias.",
           to_markdown(code_tab), "",
           f"Banks that stopped reporting before 2026Q2: **{exited.height:,}**, of which in the failures "
           f"table: **{int(exited['IN_FAILURES'].sum()):,}**. CERTs in financials but not in institutions: "
           f"**{not_in_inst}**. ACTIVE = 1 but stopped reporting: **{active_but_stopped}**. "
           f"ACTIVE = 0 but still reporting in 2026Q2: **{inactive_but_reporting}**.", ""]

    # ------------------------------------------------------------------ save
    (OUT_TAB / "part2_quality_summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                                         encoding="utf-8")
    md = md[:3] + ["## Summary", "```", json.dumps(summary, indent=2, default=str), "```", ""] + md[3:]
    (OUT_TAB / "part2_quality_report.md").write_text("\n".join(md), encoding="utf-8")
    log("Summary: " + json.dumps(summary, default=str))
    log("DONE. Report: output/tables/part2_quality_report.md")


if __name__ == "__main__":
    main()