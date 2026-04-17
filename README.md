# CleanSlate — Local Data Cleaning Wizard

A guided, transparent data cleaning tool built with Python and Streamlit.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Notes

- All data stays on your machine. Nothing is sent to any server.
- Supports CSV, XLSX, XLS.
- Undo is available for the last 5 actions (disabled automatically for files over 200MB).
- Every cleaning decision is logged in an auditable trail.
- A reproducibility recipe (pandas code) is generated at the end.

## 7-Step Cleaning Flow

1. **Data Portrait** — understand your data before touching it
2. **Column Types** — confirm what each column should be
3. **Hidden Nulls** — detect disguised missing values ("na", "?", spaces)
4. **Zero Values** — decide if zeros are valid or mean missing
5. **Missing Values** — bulk cleanup then column-by-column imputation
6. **Type Conversion** — apply confirmed types after cleaning
7. **Duplicates** — review and remove duplicate rows

## Tests

```bash
python -m pytest tests/ -v
```
