# A Big-Data Pipeline for Bank Failure Early Warning (FDIC data)

Final individual report — **BFT65B Big Data Analytics in Finance**, National Economics University (NEU)
Author: **To Mai Phuong Anh** · Student ID: **11230930**

This repository builds a reproducible pipeline on public FDIC data (1984Q1–2026Q2):
acquisition and storage → automated data-quality audit → clean point-in-time bank-quarter panel →
Polars processing (benchmarked against pandas) and a PySpark reproduction → leak-free features →
time-ordered validation, cost-based alarm threshold and a single test evaluation, plus a Spark MLlib demo.

## Data at a glance

| Item | Value |
|---|---|
| Source | FDIC BankFind Suite API (`https://api.fdic.gov/banks`), no key needed |
| Download date | 22 November 2026 |
| Financials | 1,682,738 bank-quarters, 170 quarters (1984Q1–2026Q2), 24,064 banks |
| Failures / Institutions | 4,117 rows / 27,838 rows |
| Label | y = 1 if the bank fails in (q, q+4 quarters]; mergers are not failures; quarters up to 2025Q2 |
| Development period | 1984Q1–2006Q4 · 2,691 failure events |
| Gap (unused) | 2007Q1–2007Q4 |
| Test period (used once) | 2008Q1–2025Q2 · 558 failure events |

**No data files are committed** (`data/`, `data_raw/` are in `.gitignore`). Running step 1 downloads everything.

## Repository structure

```
src/                 Python scripts, run in order 01 -> 07
  01_download.py         resumable, self-verifying FDIC download (adapted from the course starter script)
  02_storage_bench.py    Part 1: completeness checks + CSV vs Parquet layouts benchmark
  03_quality_report.py   Part 2: automated data-quality report (13 checks, 2 heatmaps)
  04_build_panel.py      Part 2: clean point-in-time panel, exit types, failure labels
  05_polars_pipeline.py  Part 3: core transformations in Polars, benchmark vs pandas, query plans
  06_features.py         Part 4: CAMELS features, truncation test, dev-only preprocessing
  07_model.py            Part 5: time-ordered CV, model comparison, cost-based threshold, single test
  pipeline_def.py        shared split dates, feature list and preprocessing pipeline (Parts 4-5)
  inspect_tables.py      helper used once to inspect the raw table structure
notebooks/           Google Colab notebooks, saved WITH outputs
  part3_spark_colab.ipynb   Part 3: PySpark reproduction, result check vs Polars, execution plan, timing
  part5_mllib_colab.ipynb   Part 5: Spark MLlib logistic regression demo
output/tables/       all result tables (.csv / .md / .json / .txt) used in the report
output/figures/      all figures used in the report
report/              screenshots of the Colab results
requirements.txt     pinned package versions
```

## How to reproduce

Tested on Windows 11, Python 3.11.9, 8 logical cores, 7.8 GB RAM.

### 1. Set up the environment

```bash
git clone https://github.com/tmphuonganh59-lgtm/Bigdata_final_exam.git
cd Bigdata_final_exam
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the pipeline (from the project root, in this order)

On Windows, use `python -X utf8 ...` so that tables print correctly (on macOS/Linux, plain `python` is fine).

| Step | Command | Main outputs | Time (approx.) |
|---|---|---|---|
| 1 | `python -X utf8 src/01_download.py --start 1984-03-31 --end 2026-06-30` | `data_raw/fdic/` (170 quarterly files, failures, institutions, manifest) | ~1 hour (API) |
| 2 | `python -X utf8 src/02_storage_bench.py` | `output/tables/part1_*`, `data/processed/financials/` | 5–15 min |
| 3 | `python -X utf8 src/03_quality_report.py` | `output/tables/part2_quality_report.md`, heatmaps | 1–2 min |
| 4 | `python -X utf8 src/04_build_panel.py` | `data/processed/panel/`, `output/tables/part2_panel_report.md` | ~1 min |
| 5 | `python -X utf8 src/05_polars_pipeline.py` | `data/processed/features_core/`, `spark_input.parquet`, `output/tables/part3_*` | ~5 min |
| 6 | `python -X utf8 src/06_features.py` | `data/processed/model_table.parquet`, `preprocessor.joblib`, `output/tables/part4_*` | 1–3 min |
| 7 | `python -X utf8 src/07_model.py` | `output/tables/part5_*`, `mllib_input.parquet`, figures 7–8 | ~5 min |

The download is resumable: if it stops, run step 1 again and finished quarters are skipped.
Each script depends on the outputs of the previous ones.

### 3. Spark notebooks (Google Colab)

1. Upload `data/processed/spark_input.parquet` and `output/tables/part3_spark_reference_by_year.csv`
   (Part 3), and `data/processed/mllib_input.parquet` (Part 5) to a Google Drive folder.
2. Open the notebook in Colab, set `BASE` in the Drive cell to that folder, and run all cells.
   The first cell installs Java 17 and `pyspark==3.5.3`.

### Reproducibility notes

- Fixed seed: `random_state=42` for gradient boosting; all other steps are deterministic.
- Timings depend on the machine; the benchmark scripts record the machine in `output/tables/part1_machine.json`.
- Preprocessing parameters are learned on the development period only and saved in `output/tables/part4_preprocessor_params_dev.csv`.
- `07_model.py` was run twice: the first run had a row-ordering bug in the model-selection table.
  The selection rule (highest mean validation PR-AUC on dev) was unchanged and the fix used no test information (see report, Part 5).

## Key results

| Part | Result |
|---|---|
| 1 Storage | Parquet + zstd, partitioned by year: 35% of CSV size, 3–26× faster reads |
| 2 Quality | 13 automated checks; labels match published FDIC failure counts year by year |
| 3 Processing | Polars 1.9× faster than pandas; Spark results match Polars exactly; Spark 12× slower on one machine |
| 4 Features | 20 CAMELS features; truncation test: 19/19 features identical, leaky control detected |
| 5 Model | Test PR-AUC 0.59 (capital-rule baseline 0.28, random 0.005); 528 of 558 failures flagged; expected cost −85% |

## References

- FDIC BankFind Suite API and field definitions: https://api.fdic.gov/banks/docs/
- FDIC, *Bank Failures in Brief — Summary by Year* (used to validate the labels).
- Course starter script `fdic_download_starter.py`, BFT65B, NEU (adapted in `src/01_download.py`).
- Libraries: Polars, pandas, PyArrow, NumPy, scikit-learn, matplotlib, psutil, Apache Spark / PySpark 3.5.3; Google Colaboratory.
- News sources used in Part 6 (Vietnam): VietNamNet, *Four underperforming banks in Vietnam restructured through mandatory transfer*; VnExpress International, report on SCB under special control (October 2022).

## Use of AI tools

Claude (Anthropic) was used as an assistant to support Python code drafting, explain outputs and query plans, and provide language editing suggestions. The author independently developed the report outline, structure, and content, ran every script, verified every result, and is responsible for the final analysis and report.