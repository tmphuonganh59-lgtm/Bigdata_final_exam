# Part 2 - Automated data-quality report
Generated 2026-11-22 21:19 by src/03_quality_report.py

## Summary
```
{
  "rows_asset_null_or_nonpositive": 0,
  "rows_negative_equity": 15647,
  "duplicate_CERT_REPDTE": 0,
  "banks": 24064,
  "banks_with_internal_gaps": 32,
  "missing_internal_quarters": 92,
  "events_since_1984": 3275,
  "events_since_1984_missing_CERT": 0,
  "events_linked_to_financials": 3253,
  "events_usable_for_label_gap_le_4q": 3253,
  "events_within_60_days_of_last_report": 1732,
  "banks_exited_before_2026Q2": 19751,
  "exited_banks_in_failures_table": 3234,
  "financial_CERT_not_in_institutions": 232,
  "active_flag_but_stopped_reporting": 2,
  "inactive_flag_but_reporting_2026Q2": 58
}
```

## A. Financials table

### A1. Missing values (overall; by year in part2_missing_by_year.csv, Figure 3)
| variable | share_missing |
|---|---|
| P3ASSET | 0.5777 |
| NTLNLS | 0.0475 |
| P9ASSET | 0.0462 |
| NAASSET | 0.0462 |
| ELNATR | 0.0257 |
| ROE | 0.0111 |
| BRO | 0.0100 |
| EINTEXP | 0.0038 |
| INTINC | 0.0028 |
| NONIXQ | 0.0028 |
| NONIX | 0.0028 |
| NETINC | 0.0028 |
| NONIIQ | 0.0028 |
| NETINCQ | 0.0028 |
| NONII | 0.0028 |
| ORE | 0.0025 |
| LNATRES | 0.0025 |
| EQ | 0.0025 |
| LNCON | 0.0023 |
| NCLNLS | 0.0015 |
| LNCI | 0.0000 |
| SC | 0.0000 |
| LNRE | 0.0000 |
| LNLSNET | 0.0000 |
| DEPDOM | 0.0000 |
| LNLSGR | 0.0000 |
| DEP | 0.0000 |
| CHBAL | 0.0000 |

### A2. Capital ratios: exact zeros and nulls by year
A ratio of exactly 0 for a bank with positive equity is impossible, so a high zero share in early years means 'not reported' (risk-based capital rules started around 1990).
| YEAR | RBC1AAJ_zero_share | RBCRWAJ_zero_share | RBC1AAJ_null_share | RBCRWAJ_null_share |
|---|---|---|---|---|
| 1984 | 0.1774 | 1.00 | 0.0000 | 0.0000 |
| 1985 | 0.1804 | 1.00 | 0.0000 | 0.0000 |
| 1986 | 0.1821 | 1.00 | 0.0000 | 0.0000 |
| 1987 | 0.1832 | 1.00 | 0.0000 | 0.0000 |
| 1988 | 0.1830 | 1.00 | 0.0000 | 0.0000 |
| 1989 | 0.1817 | 1.00 | 0.0000 | 0.0000 |
| 1990 | 0.0032 | 0.0035 | 0.0000 | 0.0000 |
| 1991 | 0.0028 | 0.0029 | 0.0000 | 0.0000 |
| 1992 | 0.0029 | 0.0030 | 0.0000 | 0.0000 |
| 1993 | 0.0032 | 0.0033 | 0.0000 | 0.0000 |
| 1994 | 0.0033 | 0.0033 | 0.0000 | 0.0000 |
| 1995 | 0.0032 | 0.0033 | 0.0000 | 0.0000 |
| 1996 | 0.0031 | 0.0032 | 0.0000 | 0.0000 |
| 1997 | 0.0031 | 0.0031 | 0.0000 | 0.0000 |
| 1998 | 0.0028 | 0.0028 | 0.0000 | 0.0000 |
| 1999 | 0.0024 | 0.0024 | 0.0000 | 0.0000 |
| 2000 | 0.0024 | 0.0024 | 0.0000 | 0.0000 |
| 2001 | 0.0023 | 0.0023 | 0.0000 | 0.0000 |
| 2002 | 0.0023 | 0.0023 | 0.0000 | 0.0000 |
| 2003 | 0.0023 | 0.0023 | 0.0000 | 0.0000 |
| 2004 | 0.0021 | 0.0022 | 0.0000 | 0.0000 |
| 2005 | 0.0021 | 0.0022 | 0.0000 | 0.0000 |
| 2006 | 0.0020 | 0.0021 | 0.0000 | 0.0000 |
| 2007 | 0.0020 | 0.0020 | 0.0000 | 0.0000 |
| 2008 | 0.0020 | 0.0021 | 0.0000 | 0.0000 |
| 2009 | 0.0022 | 0.0022 | 0.0000 | 0.0000 |
| 2010 | 0.0022 | 0.0022 | 0.0000 | 0.0000 |
| 2011 | 0.0022 | 0.0022 | 0.0000 | 0.0000 |
| 2012 | 0.0023 | 0.0023 | 0.0000 | 0.0000 |
| 2013 | 0.0025 | 0.0025 | 0.0000 | 0.0000 |
| 2014 | 0.0026 | 0.0026 | 0.0000 | 0.0000 |
| 2015 | 0.0027 | 0.0027 | 0.0000 | 0.0000 |
| 2016 | 0.0028 | 0.0028 | 0.0000 | 0.0000 |
| 2017 | 0.0029 | 0.0029 | 0.0000 | 0.0000 |
| 2018 | 0.0030 | 0.0030 | 0.0000 | 0.0000 |
| 2019 | 0.0032 | 0.0032 | 0.0000 | 0.0000 |
| 2020 | 0.0033 | 0.3640 | 0.0000 | 0.0000 |
| 2021 | 0.0034 | 0.3706 | 0.0000 | 0.0000 |
| 2022 | 0.0035 | 0.3521 | 0.0000 | 0.0000 |
| 2023 | 0.0036 | 0.3631 | 0.0000 | 0.0000 |
| 2024 | 0.0037 | 0.3719 | 0.0000 | 0.0000 |
| 2025 | 0.0038 | 0.3893 | 0.0000 | 0.0000 |
| 2026 | 0.0039 | 0.4150 | 0.0000 | 0.0000 |

### A3. Impossible negative values (balance-sheet stocks)
| variable | negative_rows | share |
|---|---|---|
| ASSET | 0 | 0.0000 |
| DEP | 0 | 0.0000 |
| DEPDOM | 0 | 0.0000 |
| LNLSGR | 33 | 0.0000 |
| LNLSNET | 51 | 0.0000 |
| LNATRES | 9 | 0.0000 |
| LNRE | 6 | 0.0000 |
| LNCI | 2 | 0.0000 |
| LNCON | 0 | 0.0000 |
| SC | 96 | 0.0001 |
| CHBAL | 2 | 0.0000 |
| P3ASSET | 0 | 0.0000 |
| P9ASSET | 0 | 0.0000 |
| NAASSET | 2 | 0.0000 |
| NCLNLS | 3 | 0.0000 |
| ORE | 645 | 0.0004 |
| BRO | 0 | 0.0000 |

Rows with ASSET null or <= 0: **0**. Rows with negative equity (EQ < 0): **15,647** (economically possible for insolvent banks, so kept: it is a strong failure signal).

### A4. Accounting identity checks (tolerance: max(1, 1% of ASSET))
| identity_violated | rows |
|---|---|
| DEP > ASSET | 5176 |
| EQ > ASSET | 0 |
| DEPDOM > DEP | 0 |
| LNLSNET > LNLSGR | 2 |
| NCLNLS > LNLSGR | 30 |
| LNATRES > LNLSGR | 28 |

### A5. Ratio ranges (percent)
| ratio | min | p01 | median | p99 | max | abs_gt_100 |
|---|---|---|---|---|---|---|
| ROA | -761.90 | -5.66 | 0.9745 | 4.16 | 860.61 | 244 |
| ROE | -354,657.80 | -60.14 | 10.34 | 38.95 | 301,050.00 | 11721 |
| NIMY | -4,515.15 | 0.2383 | 4.05 | 7.72 | 1,125.00 | 131 |
| RBC1AAJ | -1,524.07 | 0.0000 | 9.10 | 68.07 | 466,500.00 | 2969 |
| RBCRWAJ | -16,629.63 | 0.0000 | 13.28 | 109.14 | 274,636.36 | 18325 |

### A6. Distributions and extreme values (10 robust SD = 10 x 1.4826 x MAD)
Amounts are heavily skewed by bank size, so outliers are handled later with size-scaled ratios and winsorisation fitted on the training period only (Part 4).
| variable | min | p01 | median | p99 | max | beyond_10_MAD |
|---|---|---|---|---|---|---|
| EINTEXP | -159,000.00 | 5.00 | 1,183.00 | 146,600.00 | 74,797,000.00 | 110596 |
| NIMY | -4,515.15 | 0.2383 | 4.05 | 7.72 | 1,125.00 | 4086 |
| ORE | -37,906.00 | 0.0000 | 52.00 | 27,868.00 | 5,794,000.00 | 283448 |
| LNATRES | -85,980.00 | 0.0000 | 603.00 | 100,000.00 | 32,071,000.00 | 131068 |
| ELNATR | -9,296,000.00 | -235.00 | 57.00 | 25,395.00 | 29,395,292.00 | 177398 |
| RBC1AAJ | -1,524.07 | 0.0000 | 9.10 | 68.07 | 466,500.00 | 28795 |
| INTINC | -6,563.00 | 108.00 | 3,176.00 | 356,186.00 | 169,911,000.00 | 107454 |
| LNCI | -833.00 | 0.0000 | 5,237.00 | 1,253,307.00 | 353,653,000.00 | 128324 |
| SC | -965,382.00 | 0.0000 | 18,251.00 | 2,042,213.00 | 941,778,000.00 | 107071 |
| NTLNLS | -179,647.00 | -223.00 | 21.00 | 20,782.00 | 20,007,000.00 | 218735 |
| NCLNLS | -17,196.00 | 0.0000 | 467.00 | 105,874.00 | 65,914,905.00 | 144617 |
| LNRE | -354.00 | 0.0000 | 30,684.00 | 3,864,132.00 | 513,768,000.00 | 127011 |
| LNLSNET | -62,969.00 | 0.0000 | 49,405.00 | 6,799,237.00 | 1,535,635,000.00 | 122099 |
| NONIXQ | -1,071,217.00 | 49.00 | 642.00 | 77,473.00 | 24,757,000.00 | 117356 |
| ROA | -761.90 | -5.66 | 0.9745 | 4.16 | 860.61 | 29404 |
| DEPDOM | 0.0000 | 501.00 | 72,931.00 | 7,293,847.00 | 2,226,790,000.00 | 109434 |
| ROE | -354,657.80 | -60.14 | 10.34 | 38.95 | 301,050.00 | 21397 |
| ASSET | 1.00 | 5,408.00 | 86,111.00 | 10,488,361.00 | 4,091,315,000.00 | 116416 |
| LNLSGR | -61,697.00 | 0.0000 | 50,113.00 | 6,914,876.00 | 1,561,577,000.00 | 122204 |
| NONIX | -172,742.00 | 76.00 | 1,412.00 | 183,859.00 | 86,128,000.00 | 119839 |
| NETINC | -24,593,679.00 | -4,316.00 | 392.00 | 69,169.00 | 52,502,000.00 | 137620 |
| EQ | -4,565,197.00 | 102.00 | 7,998.00 | 1,023,873.00 | 341,580,000.00 | 116781 |
| DEP | 0.0000 | 504.00 | 73,025.00 | 7,542,501.00 | 2,820,284,000.00 | 109977 |
| NAASSET | -17,196.00 | 0.0000 | 249.00 | 79,080.00 | 33,970,096.00 | 176621 |
| LNCON | 0.0000 | 0.0000 | 3,620.00 | 642,751.00 | 349,114,408.00 | 107727 |
| NONIIQ | -3,993,000.00 | -8.00 | 121.00 | 39,797.00 | 20,182,000.00 | 161544 |
| RBCRWAJ | -16,629.63 | 0.0000 | 13.28 | 109.14 | 274,636.36 | 17905 |
| NETINCQ | -13,469,374.00 | -2,627.00 | 179.00 | 29,770.00 | 17,361,000.00 | 132246 |
| P9ASSET | 0.0000 | 0.0000 | 41.00 | 15,033.00 | 42,768,781.00 | 203959 |
| CHBAL | -178.00 | 138.00 | 4,294.00 | 636,063.00 | 760,259,000.00 | 127325 |
| P3ASSET | 0.0000 | 0.0000 | 699.00 | 94,057.00 | 17,863,000.00 | 38541 |
| NONII | -1,815,900.00 | 0.0000 | 268.00 | 93,356.00 | 66,240,000.00 | 164693 |
| BRO | 0.0000 | 0.0000 | 0.0000 | 396,232.00 | 151,509,000.00 |  |

### A7. Duplicates and gaps in bank series
Duplicate (CERT, REPDTE): **0**. Banks: **24,064**. Banks with at least one missing quarter between their first and last report: **32** (92 missing bank-quarters).

### A8. Year-to-date (YTD) income fields
Income and expense fields (INTINC, EINTEXP, ELNATR, NTLNLS, NETINC, NONII, NONIX) are cumulative from January. Evidence: the median grows steadily from Q1 to Q4 within a year:
| QOFY | median_INTINC | median_NETINC |
|---|---|---|
| 1 | 1,400.00 | 181.00 |
| 2 | 2,815.00 | 366.00 |
| 3 | 4,200.00 | 542.00 |
| 4 | 5,616.00 | 683.00 |

Quarterly values are derived as Q1 = YTD(Q1) and Qk = YTD(Qk) - YTD(Qk-1) within the same year, only when the previous quarter exists. The derivation is validated against the quarterly fields that FDIC also publishes:
| ytd_field | fdic_quarterly_field | quarters | rows_compared | share_matching_within_1k |
|---|---|---|---|---|
| NETINC | NETINCQ | Q1 | 426554 | 1.00 |
| NETINC | NETINCQ | Q2-Q4 | 1246223 | 0.9949 |
| NONII | NONIIQ | Q1 | 426554 | 1.00 |
| NONII | NONIIQ | Q2-Q4 | 1246223 | 0.9949 |
| NONIX | NONIXQ | Q1 | 426554 | 1.00 |
| NONIX | NONIXQ | Q2-Q4 | 1246223 | 0.9949 |

## B. Failures table

### B1. Event types, missing keys and costs
| RESTYPE | all_events | events_1984_on | missing_CERT | missing_COST |
|---|---|---|---|---|
| FAILURE | 3524 | 2863 | 485 | 582 |
| ASSISTANCE | 593 | 412 | 3 | 55 |

Unparseable FAILDATE: **0**. Banks with more than one event since 1984: **35**.

### B2. Linking failures to financials
Events since 1984: **3,275** (0 without CERT). Linked to at least one earlier financial report: **3,253** (99.3% of events with CERT). Last report at most 4 quarters before the event (so a positive label exists): **3,253**.

Gap between the last financial report and the event (quarters):
| RESTYPE | gap | len |
|---|---|---|
| ASSISTANCE | 1 quarter(s) | 401 |
| ASSISTANCE | 2 quarter(s) | 10 |
| ASSISTANCE | no report before event | 1 |
| FAILURE | 1 quarter(s) | 2531 |
| FAILURE | 2 quarter(s) | 310 |
| FAILURE | 3 quarter(s) | 1 |
| FAILURE | no report before event | 21 |

**Point-in-time note:** 1,732 events happen within 60 days after the last report date. Call Reports are filed about 30 days after quarter end and published later, so at the real decision date such a report was not yet available. These cases are flagged in the panel.

## C. Institutions table and exits

### C1. Why banks stop reporting: exit code (CHANGEC1) vs the failures table
Instead of assuming what each code means, each code is cross-checked against the failures table. Only banks in the failures table are labelled as failures; every other exit (mainly mergers) stays in the panel with y = 0 until it exits, which avoids survivorship bias.
| CHANGEC1 | exited_banks | in_failures_table | share_in_failures |
|---|---|---|---|
| 223.00 | 14183 | 120 | 0.0085 |
| 211.00 | 2393 | 2393 | 1.00 |
| 221.00 | 808 | 3 | 0.0037 |
| 217.00 | 647 | 189 | 0.2921 |
| 240.00 | 504 | 3 | 0.0060 |
| 213.00 | 337 | 316 | 0.9377 |
|  | 194 | 0 | 0.0000 |
| 230.00 | 191 | 181 | 0.9476 |
| 224.00 | 184 | 1 | 0.0054 |
| 222.00 | 173 | 0 | 0.0000 |
| 235.00 | 109 | 25 | 0.2294 |
| 216.00 | 23 | 0 | 0.0000 |
| 215.00 | 3 | 3 | 1.00 |
| 225.00 | 1 | 0 | 0.0000 |
| 470.00 | 1 | 0 | 0.0000 |

Banks that stopped reporting before 2026Q2: **19,751**, of which in the failures table: **3,234**. CERTs in financials but not in institutions: **232**. ACTIVE = 1 but stopped reporting: **2**. ACTIVE = 0 but still reporting in 2026Q2: **58**.
