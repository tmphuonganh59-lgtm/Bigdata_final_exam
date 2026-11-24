# Part 4 - Feature pipeline
Generated 2026-11-24 14:52

## Time-ordered split
| SPLIT | first_quarter | last_quarter | bank_quarters | banks | positive_rows | positive_rate | failure_events | of_which_closures |
|---|---|---|---|---|---|---|---|---|
| dev | 1984-03-31 | 2006-12-31 | 1195009 | 23624 | 10261 | 0.0086 | 2691 | 2293 |
| gap | 2007-03-31 | 2007-12-31 | 34754 | 8892 | 53 | 0.0015 | 32 | 27 |
| test | 2008-03-31 | 2025-06-30 | 435446 | 8798 | 2181 | 0.0050 | 558 | 545 |

Latest failure date used by a dev label: 2007-10-04 (test starts 2008-03-31), so no dev label overlaps the test period.

## Truncation test (point-in-time proof)
All features recomputed on data cut at 2006-12-31; rows up to the cut compared with the full-data features. Real features identical: **True**. Leaky control detected: **True**.
| feature | identical_after_cut | rows_different |
|---|---|---|
| F_EQ_TA | True | 0 |
| F_NPL | True | 0 |
| F_RES_LN | True | 0 |
| F_ROA_Q | True | 0 |
| F_NIM_Q | True | 0 |
| F_PROV_LN | True | 0 |
| F_NCO_LN | True | 0 |
| F_LIQ | True | 0 |
| F_BRO_DEP | True | 0 |
| F_ORE_TA | True | 0 |
| F_LN_DEP | True | 0 |
| F_LOG_TA | True | 0 |
| F_TA_GROWTH_4Q | True | 0 |
| F_EQ_TA_CHG_4Q | True | 0 |
| F_NPL_CHG_1Q | True | 0 |
| F_ROA_4Q_AVG | True | 0 |
| F_ROA_VS_MEDIAN | True | 0 |
| F_NPL_PCTRANK | True | 0 |
| F_EQ_TA_PCTRANK | True | 0 |
| LEAKY_NEXT_ASSET | False | 8710 |

## Univariate strength on the development period only
Positive rate in dev: 0.8587% (average precision of a random score = this rate).
| feature | camels | missing_share_dev | auc_dev | auc_strength | avg_precision_dev | observed_sign | expected_sign | sign_as_expected |
|---|---|---|---|---|---|---|---|---|
| F_LEV_RATIO | C | 0.0539 | 0.0434 | 0.9566 | 0.2187 | - | - | True |
| F_EQ_TA | C | 0.0024 | 0.0498 | 0.9502 | 0.2229 | - | - | True |
| F_ROA_4Q_AVG | E | 0.0616 | 0.0518 | 0.9482 | 0.1946 | - | - | True |
| F_EQ_TA_PCTRANK | C | 0.0024 | 0.0782 | 0.9218 | 0.1158 | - | - | True |
| F_NPL | A | 0.0112 | 0.9055 | 0.9055 | 0.1513 | + | + | True |
| F_ROA_Q | E | 0.0028 | 0.0972 | 0.9028 | 0.1370 | - | - | True |
| F_ROA_VS_MEDIAN | E | 0.0028 | 0.1028 | 0.8972 | 0.1354 | - | - | True |
| F_ORE_TA | A | 0.0029 | 0.8860 | 0.8860 | 0.1501 | + | + | True |
| F_NPL_PCTRANK | A | 0.0112 | 0.8674 | 0.8674 | 0.0857 | + | + | True |
| F_EQ_TA_CHG_4Q | C | 0.0800 | 0.1335 | 0.8665 | 0.0734 | - | - | True |
| F_NIM_Q | E | 0.0079 | 0.1934 | 0.8066 | 0.0960 | - | - | True |
| F_TA_GROWTH_4Q | M | 0.0777 | 0.1993 | 0.8007 | 0.0742 | - | +/- | True |
| F_NCO_LN | A | 0.0782 | 0.7441 | 0.7441 | 0.0650 | + | + | True |
| F_RES_LN | A | 0.0114 | 0.7384 | 0.7384 | 0.0709 | + | + | True |
| F_LIQ | L | 0.0001 | 0.2800 | 0.7200 | 0.0192 | - | - | True |
| F_PROV_LN | A | 0.0476 | 0.6864 | 0.6864 | 0.0902 | + | + | True |
| F_BRO_DEP | L | 0.0190 | 0.6180 | 0.6180 | 0.0166 | + | + | True |
| F_NPL_CHG_1Q | A | 0.0308 | 0.5716 | 0.5716 | 0.0546 | + | + | True |
| F_LN_DEP | L | 0.0062 | 0.5179 | 0.5179 | 0.0084 | + | + | True |
| F_LOG_TA | Size | 0.0000 | 0.4991 | 0.5009 | 0.0095 | - | - | True |

## Preprocessing pipeline (fitted on dev only)
Winsorise at the dev 1st/99th percentiles -> impute dev medians (+ missing-value flags) -> standardise with dev mean and standard deviation. The fitted object is reused unchanged in Part 5.
Output columns: 39 (20 features + 19 missing flags).

| feature | winsor_low_p01 | winsor_high_p99 | impute_median | scale_mean | scale_std |
|---|---|---|---|---|---|
| F_EQ_TA | -1.2612 | 52.6 | 8.6834 | 9.8347 | 6.2131 |
| F_LEV_RATIO | 0.0000 | 60.7 | 8.7074 | 10.0 | 6.7640 |
| F_EQ_TA_CHG_4Q | -12.7 | 5.2266 | 0.0811 | -0.1632 | 1.9430 |
| F_EQ_TA_PCTRANK | 0.0100 | 0.9900 | 0.5000 | 0.5000 | 0.2882 |
| F_NPL | 0.0000 | 14.9 | 0.9970 | 1.8713 | 2.5471 |
| F_RES_LN | 0.0000 | 6.5907 | 1.2409 | 1.4657 | 1.0631 |
| F_PROV_LN | -0.7048 | 10.7 | 0.2312 | 0.6672 | 1.5252 |
| F_NCO_LN | -1.2397 | 9.1711 | 0.0761 | 0.5005 | 1.3722 |
| F_ORE_TA | 0.0000 | 6.2602 | 0.0613 | 0.4376 | 0.9738 |
| F_NPL_CHG_1Q | -3.7787 | 4.3188 | -0.0003 | 0.0083 | 1.0258 |
| F_NPL_PCTRANK | 0.0254 | 0.9900 | 0.5000 | 0.5000 | 0.2869 |
| F_TA_GROWTH_4Q | -0.2150 | 1.3360 | 0.0564 | 0.0953 | 0.1959 |
| F_ROA_Q | -8.6873 | 4.2421 | 0.9980 | 0.7490 | 1.5880 |
| F_NIM_Q | 0.1600 | 7.2323 | 3.8863 | 3.8435 | 1.1066 |
| F_ROA_4Q_AVG | -5.5387 | 3.3100 | 0.9828 | 0.8052 | 1.1277 |
| F_ROA_VS_MEDIAN | -9.5814 | 3.2681 | 0.0000 | -0.2340 | 1.5670 |
| F_LIQ | 3.7373 | 77.9 | 31.6 | 33.2 | 16.0 |
| F_BRO_DEP | 0.0000 | 23.1 | 0.0000 | 0.7601 | 3.1974 |
| F_LN_DEP | 15.7 | 137.3 | 68.9 | 68.7 | 21.4 |
| F_LOG_TA | 8.4636 | 15.6 | 11.0 | 11.2 | 1.3381 |

After scaling, dev means are 0 by construction; test means are not, which shows the test data were only transformed with dev parameters (and reveals the shift between periods):
| feature | dev_mean_after_scaling | test_mean_after_scaling |
|---|---|---|
| F_EQ_TA | 0.0000 | 0.3170 |
| F_LEV_RATIO | -0.0000 | 0.2603 |
| F_EQ_TA_CHG_4Q | -0.0000 | -0.0013 |
| F_EQ_TA_PCTRANK | 0.0000 | 0.0001 |
| F_NPL | -0.0000 | -0.1041 |
| F_RES_LN | -0.0000 | 0.0416 |
| F_PROV_LN | -0.0000 | -0.1334 |
| F_NCO_LN | -0.0000 | -0.0934 |
| F_ORE_TA | 0.0000 | -0.0331 |
| F_NPL_CHG_1Q | -0.0000 | 0.0072 |
| F_NPL_PCTRANK | 0.0000 | 0.0001 |
| F_TA_GROWTH_4Q | 0.0000 | -0.1211 |
| F_ROA_Q | 0.0000 | -0.0076 |
| F_NIM_Q | 0.0000 | -0.4508 |
| F_ROA_4Q_AVG | 0.0000 | -0.0550 |
| F_ROA_VS_MEDIAN | -0.0000 | 0.0801 |
| F_LIQ | -0.0000 | -0.1427 |
| F_BRO_DEP | 0.0000 | 0.6622 |
| F_LN_DEP | 0.0000 | 0.3580 |
| F_LOG_TA | -0.0000 | 0.8444 |
