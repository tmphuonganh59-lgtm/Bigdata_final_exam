# Part 1 - Storage benchmark results

Machine: date_run=2026-11-22 20:23, os=Windows-10-10.0.26200-SP0, cpu=Intel64 Family 6 Model 140 Stepping 1, GenuineIntel, logical_cores=8, ram_gb=7.8, python=3.11.9, polars=2.1.0, pyarrow=26.0.1, polars_threads=8, pandas=3.1.1

## Completeness
```
{
  "expected_quarters": 170,
  "quarters_present": 170,
  "missing_quarters": [],
  "unexpected_quarters": [],
  "raw_files": 170,
  "total_rows": 1682738,
  "distinct_banks_CERT": 24064,
  "duplicate_CERT_REPDTE": 0,
  "null_CERT": 0,
  "quarters_not_matching_api_total": 0,
  "manifest_check": "compared with manifest columns 'key', 'api_total'"
}
```

## In-memory size by schema
| representation | in_memory_MB |
|---|---|
| All columns as text (naive CSV read) | 403.3 |
| As downloaded (starter script types) | 465.6 |
| Explicit schema (Int32 / Date / Float64) | 458.2 |

## Size on disk
| layout | files | size_MB | vs_CSV_% | write_s |
|---|---|---|---|---|
| Raw download (starter, 170 files) | 170 | 250.1 | 54.060 | None |
| CSV (1 file) | 1 | 462.7 | 100.0 | 0.827 |
| Parquet uncompressed (1 file) | 1 | 418.1 | 90.369 | 0.728 |
| Parquet snappy (1 file) | 1 | 225.7 | 48.780 | 0.502 |
| Parquet zstd (1 file) | 1 | 163.5 | 35.329 | 0.876 |
| Parquet zstd, 170 files by quarter | 170 | 168.0 | 36.302 | 1.411 |
| Parquet zstd, partitioned by YEAR | 43 | 165.5 | 35.767 | 0.973 |

## Median read time, seconds (5 runs after 1 warm-up)
| tool | layout | query | median_s | min_s | max_s | runs |
|---|---|---|---|---|---|---|
| polars | CSV (1 file) | full_read | 1.058 | 0.785 | 1.186 | 5 |
| polars | CSV (1 file) | read_3_columns | 0.337 | 0.298 | 0.403 | 5 |
| polars | CSV (1 file) | read_year_2008 | 1.048 | 0.995 | 1.152 | 5 |
| polars | Parquet uncompressed (1 file) | full_read | 0.196 | 0.176 | 0.251 | 5 |
| polars | Parquet uncompressed (1 file) | read_3_columns | 0.010 | 0.009 | 0.064 | 5 |
| polars | Parquet uncompressed (1 file) | read_year_2008 | 0.017 | 0.012 | 0.022 | 5 |
| polars | Parquet snappy (1 file) | full_read | 0.258 | 0.232 | 0.269 | 5 |
| polars | Parquet snappy (1 file) | read_3_columns | 0.015 | 0.014 | 0.019 | 5 |
| polars | Parquet snappy (1 file) | read_year_2008 | 0.021 | 0.019 | 0.045 | 5 |
| polars | Parquet zstd (1 file) | full_read | 0.392 | 0.360 | 0.417 | 5 |
| polars | Parquet zstd (1 file) | read_3_columns | 0.018 | 0.015 | 0.019 | 5 |
| polars | Parquet zstd (1 file) | read_year_2008 | 0.027 | 0.024 | 0.028 | 5 |
| polars | Parquet zstd, 170 files by quarter | full_read | 0.417 | 0.396 | 0.472 | 5 |
| polars | Parquet zstd, 170 files by quarter | read_3_columns | 0.047 | 0.041 | 0.127 | 5 |
| polars | Parquet zstd, 170 files by quarter | read_year_2008 | 0.031 | 0.031 | 0.037 | 5 |
| polars | Parquet zstd, partitioned by YEAR | full_read | 0.351 | 0.347 | 0.384 | 5 |
| polars | Parquet zstd, partitioned by YEAR | read_3_columns | 0.043 | 0.035 | 0.133 | 5 |
| polars | Parquet zstd, partitioned by YEAR | read_year_2008 | 0.040 | 0.039 | 0.044 | 5 |
| pandas | CSV (1 file) | full_read | 1.496 | 1.211 | 2.024 | 5 |
| pandas | Parquet zstd (1 file) | full_read | 0.620 | 0.537 | 0.705 | 5 |

Result check across layouts: PASSED