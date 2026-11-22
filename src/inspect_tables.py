"""Print the structure of the three FDIC tables (helper for Part 2)."""
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "fdic"
FIN = ROOT / "data" / "processed" / "financials"

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(40)
pl.Config.set_tbl_width_chars(250)
pl.Config.set_fmt_str_lengths(40)

fin = pl.scan_parquet(FIN.as_posix() + "/**/*.parquet", hive_partitioning=True)
print("=== FINANCIALS schema ===")
print(fin.collect_schema())
print(fin.head(3).collect())

for name in ("failures", "institutions"):
    df = pl.read_parquet(RAW / f"{name}.parquet")
    print(f"\n=== {name.upper()} shape={df.shape} ===")
    print(df.schema)
    print(df.head(5))
    print("--- null counts ---")
    print(df.null_count())
    for col in ("CHANGEC1", "ACTIVE", "RESTYPE", "RESTYPE1", "CHCLASS1", "SAVR"):
        if col in df.columns:
            print(f"--- value counts: {col} ---")
            print(df[col].value_counts().sort("count", descending=True).head(30))