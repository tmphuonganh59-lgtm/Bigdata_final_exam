# Part 2 - Clean panel and labels

## Summary
```
{
  "rows_loaded": 1682738,
  "rows_in_panel": 1682738,
  "rows_with_label": 1665209,
  "positives_Y": 12495,
  "positive_rate": 0.007503562615863835,
  "positives_failure_only": 10903,
  "late_signal_positive_rows": 1730,
  "distinct_events_with_positive_rows": 3251,
  "banks": 24064
}
```

## Cleaning log
| rule | rows_affected |
|---|---|
| R1 drop rows with ASSET missing or <= 0 | 0 |
| R2 RBC1AAJ == 0 with EQ > 0 -> missing (1984-1989) | 64327 |
| R2 RBC1AAJ == 0 with EQ > 0 -> missing (1990-2019) | 30 |
| R2 RBC1AAJ == 0 with EQ > 0 -> missing (2020-2026) | 0 |
| R2 RBCRWAJ == 0 with EQ > 0 -> missing (1984-1989) | 406539 |
| R2 RBCRWAJ == 0 with EQ > 0 -> missing (1990-2019) | 77 |
| R2 RBCRWAJ == 0 with EQ > 0 -> missing (2020-2026) | 45370 |
| CHECK DEP > ASSET with EQ < 0 (insolvent, kept) | 6203 |
| CHECK DEP > ASSET with EQ >= 0 (inconsistent, kept and flagged) | 2 |
| R3 ASSET < 0 -> missing | 0 |
| R3 DEP < 0 -> missing | 0 |
| R3 DEPDOM < 0 -> missing | 0 |
| R3 LNLSGR < 0 -> missing | 33 |
| R3 LNLSNET < 0 -> missing | 51 |
| R3 LNATRES < 0 -> missing | 9 |
| R3 LNRE < 0 -> missing | 6 |
| R3 LNCI < 0 -> missing | 2 |
| R3 LNCON < 0 -> missing | 0 |
| R3 SC < 0 -> missing | 96 |
| R3 CHBAL < 0 -> missing | 2 |
| R3 P3ASSET < 0 -> missing | 0 |
| R3 P9ASSET < 0 -> missing | 0 |
| R3 NAASSET < 0 -> missing | 2 |
| R3 NCLNLS < 0 -> missing | 3 |
| R3 ORE < 0 -> missing | 645 |
| R3 BRO < 0 -> missing | 0 |
| R4 INTINC_QTR missing (Q2-Q4 without previous quarter) | 5278 |
| R4 EINTEXP_QTR missing (Q2-Q4 without previous quarter) | 4635 |
| R4 ELNATR_QTR missing (Q2-Q4 without previous quarter) | 5026 |
| R4 NTLNLS_QTR missing (Q2-Q4 without previous quarter) | 4778 |
| R4 NETINC_QTR missing (Q2-Q4 without previous quarter) | 0 |
| R4 NONII_QTR missing (Q2-Q4 without previous quarter) | 0 |
| R4 NONIX_QTR missing (Q2-Q4 without previous quarter) | 0 |
| R5 rows without the previous quarter (gap or first report), flagged HAS_PREV_Q | 24097 |

## Exit types (banks)
| EXIT_TYPE | banks |
|---|---|
| other_exit | 16946 |
| active | 4313 |
| failure | 2571 |
| assistance | 234 |

## Labels by year (quarters up to 2025Q2)
| YEAR | bank_quarters | banks | positives_Y | positives_failure_only | late_signal_rows | positive_rate | events_with_positive_rows | of_which_FAILURE |
|---|---|---|---|---|---|---|---|---|
| 1984 | 71760 | 18330 | 557 | 427 | 57 | 0.0078 | 84 | 62 |
| 1985 | 72091 | 18502 | 770 | 595 | 82 | 0.0107 | 180 | 139 |
| 1986 | 72182 | 18409 | 943 | 777 | 118 | 0.0131 | 204 | 162 |
| 1987 | 70398 | 18051 | 1421 | 834 | 113 | 0.0202 | 262 | 217 |
| 1988 | 67711 | 17468 | 2330 | 1873 | 281 | 0.0344 | 470 | 232 |
| 1989 | 65393 | 16803 | 1582 | 1579 | 254 | 0.0242 | 534 | 530 |
| 1990 | 62765 | 16308 | 1164 | 1158 | 153 | 0.0185 | 382 | 381 |
| 1991 | 59945 | 15466 | 787 | 777 | 134 | 0.0131 | 271 | 268 |
| 1992 | 57021 | 14587 | 386 | 380 | 82 | 0.0068 | 181 | 179 |
| 1993 | 54491 | 13926 | 85 | 85 | 16 | 0.0016 | 50 | 50 |
| 1994 | 51879 | 13292 | 46 | 46 | 8 | 0.0009 | 15 | 15 |
| 1995 | 49112 | 12558 | 22 | 22 | 4 | 0.0004 | 8 | 8 |
| 1996 | 46943 | 12083 | 8 | 8 | 2 | 0.0002 | 6 | 6 |
| 1997 | 44941 | 11632 | 10 | 10 | 1 | 0.0002 | 1 | 1 |
| 1998 | 43079 | 11106 | 20 | 20 | 1 | 0.0005 | 3 | 3 |
| 1999 | 41705 | 10725 | 28 | 28 | 1 | 0.0007 | 8 | 8 |
| 2000 | 40631 | 10447 | 21 | 21 | 2 | 0.0005 | 7 | 7 |
| 2001 | 39352 | 10054 | 37 | 37 | 5 | 0.0009 | 4 | 4 |
| 2002 | 38204 | 9712 | 18 | 18 | 2 | 0.0005 | 11 | 11 |
| 2003 | 37447 | 9526 | 19 | 19 | 3 | 0.0005 | 3 | 3 |
| 2004 | 36637 | 9333 | 1 | 1 | 0 | 0.0000 | 4 | 4 |
| 2005 | 35915 | 9190 | 0 | 0 | 0 | 0.0000 |  |  |
| 2006 | 35407 | 9047 | 6 | 6 | 0 | 0.0002 |  |  |
| 2007 | 34754 | 8892 | 53 | 48 | 1 | 0.0015 | 3 | 3 |
| 2008 | 34003 | 8649 | 402 | 355 | 44 | 0.0118 | 30 | 25 |
| 2009 | 32916 | 8359 | 670 | 670 | 105 | 0.0204 | 148 | 140 |
| 2010 | 31545 | 8035 | 457 | 457 | 114 | 0.0145 | 157 | 157 |
| 2011 | 30230 | 7666 | 269 | 269 | 65 | 0.0089 | 92 | 92 |
| 2012 | 29157 | 7394 | 129 | 129 | 27 | 0.0044 | 51 | 51 |
| 2013 | 27989 | 7105 | 79 | 79 | 19 | 0.0028 | 24 | 24 |
| 2014 | 26805 | 6812 | 46 | 46 | 13 | 0.0017 | 18 | 18 |
| 2015 | 25521 | 6497 | 23 | 23 | 4 | 0.0009 | 8 | 8 |
| 2016 | 24356 | 6193 | 29 | 29 | 5 | 0.0012 | 5 | 5 |
| 2017 | 23325 | 5928 | 9 | 9 | 4 | 0.0004 | 8 | 8 |
| 2018 | 22301 | 5679 | 6 | 6 | 0 | 0.0003 |  |  |
| 2019 | 21366 | 5441 | 19 | 19 | 4 | 0.0009 | 4 | 4 |
| 2020 | 20478 | 5188 | 7 | 7 | 3 | 0.0003 | 4 | 4 |
| 2021 | 19942 | 5052 | 0 | 0 | 0 | 0.0000 |  |  |
| 2022 | 19285 | 4875 | 14 | 14 | 0 | 0.0007 |  |  |
| 2023 | 18798 | 4749 | 9 | 9 | 2 | 0.0005 | 5 | 5 |
| 2024 | 18399 | 4647 | 9 | 9 | 1 | 0.0005 | 2 | 2 |
| 2025 | 9030 | 4538 | 4 | 4 | 0 | 0.0004 | 2 | 2 |