# Part 5 - Modelling and validation
Generated 2026-11-24 15:22

Accuracy of the trivial 'no failure' prediction on dev: 99.1413% (this is why accuracy is not used).

## Time-ordered cross-validation on dev (expanding window, 1-year gap)
| fold | validation_years | model | positives | pr_auc | roc_auc | recall_top1pct | recall_top5pct |
|---|---|---|---|---|---|---|---|
| 1 | 1988-1989 | capital_rule | 3912 | 0.4561 | 0.9666 | 0.1616 | 0.7664 |
| 1 | 1988-1989 | logistic | 3912 | 0.5536 | 0.9688 | 0.2313 | 0.7620 |
| 1 | 1988-1989 | hgb_small | 3912 | 0.5493 | 0.9760 | 0.2186 | 0.8001 |
| 1 | 1988-1989 | hgb_medium | 3912 | 0.5401 | 0.9739 | 0.2175 | 0.7840 |
| 1 | 1988-1989 | hgb_large | 3912 | 0.5502 | 0.9758 | 0.2224 | 0.7975 |
| 2 | 1990-1991 | capital_rule | 1951 | 0.2396 | 0.9579 | 0.0533 | 0.8411 |
| 2 | 1990-1991 | logistic | 1951 | 0.2995 | 0.9719 | 0.1451 | 0.8806 |
| 2 | 1990-1991 | hgb_small | 1951 | 0.3567 | 0.9758 | 0.2788 | 0.8514 |
| 2 | 1990-1991 | hgb_medium | 1951 | 0.3411 | 0.9755 | 0.2645 | 0.8539 |
| 2 | 1990-1991 | hgb_large | 1951 | 0.3661 | 0.9761 | 0.3009 | 0.8560 |
| 3 | 1992-1993 | capital_rule | 471 | 0.1217 | 0.9369 | 0.5096 | 0.7643 |
| 3 | 1992-1993 | logistic | 471 | 0.2227 | 0.9604 | 0.6115 | 0.8280 |
| 3 | 1992-1993 | hgb_small | 471 | 0.3235 | 0.9726 | 0.6327 | 0.8705 |
| 3 | 1992-1993 | hgb_medium | 471 | 0.2850 | 0.9732 | 0.6157 | 0.8832 |
| 3 | 1992-1993 | hgb_large | 471 | 0.3359 | 0.9744 | 0.6306 | 0.8960 |
| 4 | 1994-2000 | capital_rule | 155 | 0.0886 | 0.8652 | 0.6452 | 0.6903 |
| 4 | 1994-2000 | logistic | 155 | 0.1687 | 0.9048 | 0.7226 | 0.7871 |
| 4 | 1994-2000 | hgb_small | 155 | 0.1927 | 0.9529 | 0.7613 | 0.8581 |
| 4 | 1994-2000 | hgb_medium | 155 | 0.1865 | 0.9434 | 0.7871 | 0.8581 |
| 4 | 1994-2000 | hgb_large | 155 | 0.2121 | 0.9481 | 0.7677 | 0.8581 |
| 5 | 2001-2006 | capital_rule | 81 | 0.0277 | 0.7511 | 0.2222 | 0.3210 |
| 5 | 2001-2006 | logistic | 81 | 0.0659 | 0.8428 | 0.5062 | 0.6173 |
| 5 | 2001-2006 | hgb_small | 81 | 0.0806 | 0.8882 | 0.5556 | 0.6914 |
| 5 | 2001-2006 | hgb_medium | 81 | 0.0622 | 0.8845 | 0.5309 | 0.6790 |
| 5 | 2001-2006 | hgb_large | 81 | 0.0844 | 0.8890 | 0.5556 | 0.6543 |

### Mean over folds (model chosen by mean PR-AUC)
| model | mean_pr_auc | sd_pr_auc | mean_roc_auc | mean_recall_top5pct | pooled_oof_pr_auc |
|---|---|---|---|---|---|
| hgb_large | 0.3097 | 0.1747 | 0.9527 | 0.8124 | 0.4255 |
| hgb_small | 0.3006 | 0.1772 | 0.9531 | 0.8143 | 0.4280 |
| hgb_medium | 0.2830 | 0.1785 | 0.9501 | 0.8116 | 0.4109 |
| logistic | 0.2621 | 0.1838 | 0.9298 | 0.7750 | 0.3760 |
| capital_rule | 0.1868 | 0.1692 | 0.8956 | 0.6766 | 0.3206 |

Best gradient-boosting setting: **hgb_large**. Model chosen for the test: **hgb_large**.

## Alarm threshold from costs (chosen on out-of-fold dev predictions only)
C_FN (missed failure) = median FDIC resolution cost of 2,684 failures in 1984-2007 = **8,902 thousand USD** (from the data). C_FP (false alarm) = one extra examination, assumed **100 thousand USD** (not in the data), with a sensitivity analysis:
| C_FP_thousand_usd | cost_ratio_FN_FP | threshold | cost | tp | fp | fn | alarm_rate | recall | precision |
|---|---|---|---|---|---|---|---|---|---|
| 25 | 356 | 0.0025 | 3,608,085 | 6366 | 71687 | 204 | 0.0859 | 0.9689 | 0.0816 |
| 50 | 178 | 0.0050 | 5,091,746 | 6277 | 49672 | 293 | 0.0616 | 0.9554 | 0.1122 |
| 100 | 89 | 0.0079 | 7,274,579 | 6189 | 38831 | 381 | 0.0495 | 0.9420 | 0.1375 |
| 250 | 36 | 0.0169 | 11,763,594 | 5982 | 26118 | 588 | 0.0353 | 0.9105 | 0.1864 |
| 500 | 18 | 0.0427 | 16,479,945 | 5620 | 16047 | 950 | 0.0238 | 0.8554 | 0.2594 |
| 1,000 | 8.9015 | 0.0804 | 22,813,189 | 5262 | 11170 | 1308 | 0.0181 | 0.8009 | 0.3202 |

Base-case threshold: **0.0079** (alarm rate 4.95% of bank-quarters).

## Single evaluation on the test period (2008Q1-2025Q2)
Models re-fitted on all dev data; preprocessing = the Part 4 pipeline fitted on dev only.
| model | pr_auc | roc_auc | recall_top1pct | recall_top5pct | pr_auc_closures_only |
|---|---|---|---|---|---|
| capital_rule | 0.2759 | 0.9455 | 0.5685 | 0.8166 | 0.2807 |
| logistic | 0.6103 | 0.9773 | 0.7547 | 0.9321 | 0.6223 |
| hgb_large (chosen) | 0.5898 | 0.9809 | 0.7689 | 0.9276 | 0.6017 |

### Chosen model (hgb_large) at the cost-based threshold
```
{
  "threshold": 0.007919774028318751,
  "TP": 1944,
  "FP": 8845,
  "FN": 237,
  "TN": 424420,
  "recall": 0.8913342503438789,
  "precision": 0.18018352025210863,
  "alarm_rate": 0.024776895412978877,
  "recall_excluding_late_signal_rows": 0.8780350084697911,
  "failure_events": 558,
  "events_flagged_at_least_once": 528,
  "events_flagged_by_a_timely_row": 521,
  "expected_cost_model": 2994160.4390800004,
  "expected_cost_no_alarm": 19414216.95204,
  "expected_cost_alarm_all": 43326500.0
}
```

### Test results by year
| YEAR | rows | positives | tp | alarms | recall |
|---|---|---|---|---|---|
| 2008 | 34003 | 402 | 269 | 1089 | 0.6692 |
| 2009 | 32916 | 670 | 629 | 2523 | 0.9388 |
| 2010 | 31545 | 457 | 440 | 2303 | 0.9628 |
| 2011 | 30230 | 269 | 268 | 1628 | 0.9963 |
| 2012 | 29157 | 129 | 129 | 1069 | 1.0000 |
| 2013 | 27989 | 79 | 74 | 682 | 0.9367 |
| 2014 | 26805 | 46 | 45 | 386 | 0.9783 |
| 2015 | 25521 | 23 | 23 | 244 | 1.0000 |
| 2016 | 24356 | 29 | 26 | 164 | 0.8966 |
| 2017 | 23325 | 9 | 6 | 119 | 0.6667 |
| 2018 | 22301 | 6 | 3 | 81 | 0.5000 |
| 2019 | 21366 | 19 | 16 | 56 | 0.8421 |
| 2020 | 20478 | 7 | 7 | 62 | 1.0000 |
| 2021 | 19942 | 0 | 0 | 31 | nan |
| 2022 | 19285 | 14 | 1 | 77 | 0.0714 |
| 2023 | 18798 | 9 | 5 | 101 | 0.5556 |
| 2024 | 18399 | 9 | 0 | 116 | 0.0000 |
| 2025 | 9030 | 4 | 3 | 58 | 0.7500 |

### Logistic regression: standardised coefficients (top 15)
| term | std_coefficient |
|---|---|
| F_EQ_TA | -2.0954 |
| F_LEV_RATIO | -1.7357 |
| F_ROA_4Q_AVG | -0.4261 |
| F_NPL_PCTRANK | 0.4045 |
| missingindicator_F_LEV_RATIO | 0.3445 |
| F_LIQ | -0.3200 |
| missingindicator_F_PROV_LN | -0.2975 |
| F_ROA_VS_MEDIAN | 0.2938 |
| F_EQ_TA_PCTRANK | 0.2649 |
| missingindicator_F_EQ_TA_CHG_4Q | -0.2434 |
| missingindicator_F_TA_GROWTH_4Q | -0.2291 |
| missingindicator_F_LN_DEP | -0.2268 |
| F_RES_LN | -0.2065 |
| missingindicator_F_ROA_4Q_AVG | 0.2054 |
| missingindicator_F_NCO_LN | -0.2044 |
