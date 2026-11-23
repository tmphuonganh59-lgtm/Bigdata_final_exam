# Part 3 - Polars pipeline and pandas benchmark

Machine: date_run=2026-11-22 20:23, os=Windows-10-10.0.26200-SP0, cpu=Intel64 Family 6 Model 140 Stepping 1, GenuineIntel, logical_cores=8, ram_gb=7.8, python=3.11.9, polars=2.1.0, pyarrow=26.0.1, polars_threads=8, pandas=3.1.1

## Full pipeline time (1 warm-up + 5 runs)
| engine | median_s | min_s | max_s | runs | speedup_vs_pandas |
|---|---|---|---|---|---|
| pandas | 1.989 | 1.829 | 2.123 | 5 | 1.000 |
| polars_eager | 1.042 | 0.875 | 1.171 | 5 | 1.908 |
| polars_lazy | 1.157 | 1.041 | 1.431 | 5 | 1.718 |
| polars_streaming | 1.115 | 1.027 | 1.201 | 5 | 1.784 |
| pandas_sorted_shift | 1.994 | 1.850 | 2.466 | 5 | 0.998 |
| polars_lazy_sorted_shift | 1.160 | 1.066 | 1.333 | 5 | 1.715 |

## Time per step (median seconds)
| step | pandas | polars_eager | pandas_sorted_shift | speedup_eager |
|---|---|---|---|---|
| S1 read | 0.327 | 0.362 | 0.356 | 0.902 |
| S2 ratios | 0.174 | 0.069 | 0.198 | 2.510 |
| S3 windows | 0.229 | 0.220 | 0.160 | 1.039 |
| S4 quarter join+rank | 1.245 | 0.398 | 1.260 | 3.124 |

Polars lazy runs the whole plan at once (steps are fused), so it has no per-step times.

## Peak memory (fresh process per engine)
| engine | baseline_MB | peak_MB | extra_MB | cold_run_s | rows |
|---|---|---|---|---|---|
| pandas | 92.945 | 1,130.480 | 1,037.535 | 2.872 | 1682738 |
| polars_eager | 92.863 | 1,444.812 | 1,351.949 | 0.848 | 1682738 |
| polars_lazy | 92.918 | 1,651.934 | 1,559.016 | 1.325 | 1682738 |
| polars_streaming | 92.922 | 1,709.359 | 1,616.438 | 1.066 | 1682738 |
| pandas_sorted_shift | 92.828 | 1,320.465 | 1,227.637 | 2.009 | 1682738 |
| polars_lazy_sorted_shift | 92.805 | 1,678.973 | 1,586.168 | 0.918 | 1682738 |

## Result check: PASSED (details in part3_result_check.csv)

## Reference numbers for the Spark notebook
```
{
  "rows": 1682738,
  "sum_Y": 12495,
  "n_growth": 1587806,
  "sum_growth": 223494.07276020735,
  "sum_roa_vs_median": 2770916.428857274
}
```