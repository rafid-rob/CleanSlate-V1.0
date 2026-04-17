# CleanSlate v1.0 — Design Spec

**Date:** 2026-04-17
**Stack:** Python + Streamlit
**Scope:** Local data cleaning wizard with 7-step guided flow
**Source brief:** `cleanslate_brief_v1.md`

This spec captures the validated design for CleanSlate v1.0, incorporating all changes agreed during brainstorming. Where this spec diverges from the original brief, this spec takes precedence.

---

## Core Philosophy

CleanSlate is a partner, not an autopilot.

1. Never modifies data without user approval.
2. Always shows before it acts.
3. Always explains before it asks.
4. Every decision is recorded in an auditable log.
5. The original uploaded file is never touched.
6. Every action is reversible (files under 200MB).

Sequence: **UNDERSTAND → DIAGNOSE → DECIDE → CLEAN → CONFIRM**

---

## Changes From Original Brief

| Area | Original Brief | This Spec | Why |
|------|---------------|-----------|-----|
| Phase 2 | Drops empty columns, applies type conversions | Contracts only — no mutations | Fixing missing values first often makes type conversion automatic |
| Phase 5 | Single phase | Split into 5.1 (bulk cleanup) and 5.2 (column-by-column) | Clearer separation of concerns |
| Phase 5.1 row threshold | Hardcoded at 30% | User inputs the percentage | Different datasets need different thresholds |
| Phase 5E detour | Jump to duplicates mid-Phase 5, return after | Info note only: "You have X duplicates — handled in Step 8" | Avoids complex state management for minimal benefit |
| Phase 6 (new) | Type conversion was part of Phase 2 | Separate phase after missing values resolved | Columns often auto-resolve after cleaning |
| Phase numbering | Steps 1–5 shown to user | Steps 1–7 shown to user (upload is landing page, not a step) | More phases now |
| Undo history | Max 10 snapshots | Max 5 snapshots | Memory safety: 5 × 150MB = 750MB vs 1.5GB |
| Date parsing | No format inference | Infer format from sample, apply to full column | Performance: O(n) vs O(n × formats) |
| Group median | No NaN handling in grouping columns | Fill NaN in group-by cols with sentinel before groupby | Prevents silent row exclusion by pandas |
| Reproducibility recipe | Listed as optional | Required for v1.0 | Key differentiator; builds trust |
| `recipe.py` | Not in original file structure | New module in utils/ | Recipe generation is complex enough for its own file |

---

## File Structure

```
cleanslate/
├── app.py                  # Entry point + routing + all phase UI functions
├── utils/
│   ├── __init__.py         # Empty
│   ├── scanner.py          # Detection logic (read-only, never mutates data)
│   ├── cleaner.py          # All mutation functions (returns new_df, never logs)
│   ├── audit.py            # Snapshot management + audit logging
│   ├── state.py            # Session state init + reset
│   └── recipe.py           # Generates reproducibility pandas code from audit log
├── tests/
│   ├── test_scanner.py
│   ├── test_cleaner.py
│   ├── test_audit.py
│   └── test_recipe.py
├── requirements.txt
└── README.md
```

### Module Responsibilities

**`app.py`** — Entry point. Calls `init_session_state()`, then routes to the current phase function. Owns the transaction boundary: calls `save_snapshot()` → `cleaner.function()` → `log_action()` → shows preview. All phase UI functions live here.

**`scanner.py`** — Pure read-only detection. Never mutates data. Functions: `detect_column_type()`, `find_disguised_nulls()`, `find_zero_columns()`, `describe_numeric_plainly()`, `get_high_missingness_rows()`, `get_fully_empty_columns()`, `is_likely_id_column()`.

**`cleaner.py`** — All mutation functions. Every function accepts `df` + parameters, returns `(new_df, rows_affected, details_dict)`. Never calls `save_snapshot()` or `log_action()` — the phase handler in `app.py` controls that.

**`audit.py`** — Snapshot management (`save_snapshot()`, `undo()`) and audit logging (`log_action()`). `estimate_df_memory_mb()` lives here.

**`state.py`** — Single `init_session_state()` function and `reset_session_state()`. Called once at top of `app.py`.

**`recipe.py`** — Reads the audit log and generates valid, runnable pandas code that reproduces every cleaning step. Output is a string of Python code.

---

## Session State Architecture

All session state initialised in `init_session_state()` in `utils/state.py`.

### Keys

| Key | Type | Purpose |
|-----|------|---------|
| `stage` | str | Current phase. Values: `'upload'`, `'portrait'`, `'diagnose'`, `'nulls'`, `'zeros'`, `'missing_bulk'`, `'missing_columns'`, `'type_convert'`, `'duplicates'`, `'done'` |
| `original_df` | DataFrame | Raw upload. **NEVER modified.** |
| `working_df` | DataFrame | The copy being cleaned. All mutations happen here. |
| `filename` | str | Original filename |
| `file_size_mb` | float | File size in MB (used to disable undo for large files) |
| `undo_enabled` | bool | False if `file_size_mb > 200` |
| `column_contracts` | dict | `{col_name: {'detected_type': str, 'intended_type': str, 'confirmed': bool}}` |
| `audit_log` | list[dict] | See audit schema below |
| `history` | list[DataFrame] | Snapshots for undo. **Max 5.** |
| `current_col_idx` | int | Progress tracker for Phase 5.2 column-by-column flow |
| `missing_value_cols` | list[str] | Ordered list of columns to process in Phase 5.2 |
| `disguised_nulls` | dict | `{col_name: [suspicious_values]}` |
| `zero_cols` | list[str] | Numeric columns with zeros (excluding boolean-like) |
| `skipped_cols` | list[str] | Columns the user chose to leave for now in Phase 5.2 |

### Audit Log Schema

Every entry has exactly these fields:

```python
{
    'timestamp': str,          # ISO format
    'phase': str,              # phase identifier
    'column': str,             # column name or '*' for whole-dataset actions
    'issue': str,              # human-readable issue description
    'decision': str,           # human-readable decision
    'rows_affected': int,      # count of rows changed
    'method': str,             # controlled vocabulary — see below
    'details': dict            # method-specific details
}
```

### Controlled Vocabulary for `method`

**Phase 2 — Contracts:**
- `type_confirmation` — column contract set

**Phase 3 — Disguised Nulls:**
- `replace_disguised_nulls` — suspicious strings → NaN

**Phase 4 — Zeros:**
- `zero_as_missing` — zeros replaced with NaN
- `zero_kept_valid` — user confirmed zeros are valid

**Phase 5.1 — Bulk Cleanup:**
- `drop_empty_column` — column was 100% missing
- `drop_rows_high_missingness` — rows dropped by user-defined threshold

**Phase 5.2 — Column Imputation:**
- `impute_mean` — fill with column mean
- `impute_median` — fill with column median
- `impute_mode` — fill with column mode
- `impute_group_median` — fill with median within group
- `impute_group_median_fallback` — rows where group median failed; global median used
- `impute_custom_value` — user-specified constant
- `impute_marker_unknown` — filled with 'Unknown' marker
- `impute_most_recent_date` / `impute_oldest_date` / `impute_median_date`
- `drop_rows_column_missing` — rows dropped due to single column NaN
- `skip_column` — user chose "leave for now"

**Phase 6 — Type Conversion:**
- `type_conversion` — column converted to intended type
- `type_conversion_skipped` — conversion not needed or user skipped

**Phase 7 — Duplicates:**
- `remove_duplicates_keep_first` / `remove_duplicates_keep_last`
- `keep_duplicates`

---

## Helper Functions

### `utils/scanner.py` (read-only detection)

Exactly as specified in the original brief, with these constants:

```python
KNOWN_NULL_STRINGS = {
    '', ' ', '  ', 'na', 'n/a', 'n.a.', 'n.a',
    'nan', 'none', 'null', '?', '-', '--', '---',
    'missing', 'nil', 'undefined', 'unknown'
}

ID_HINT_KEYWORDS = {
    'id', 'code', 'number', 'sku', 'postcode',
    'zip', 'phone', 'uuid', 'ref', 'identifier'
}
```

Functions:
- `is_likely_id_column(col_name)` — checks if column name suggests an identifier
- `detect_column_type(series, col_name)` — returns one of: `'continuous_numeric'`, `'categorical_numeric'`, `'categorical_text'`, `'free_text'`, `'datetime'`, `'boolean'`, `'identifier'`, `'empty'`
- `find_disguised_nulls(df)` — returns `{col: [suspicious_values]}`
- `find_zero_columns(df)` — numeric columns with zeros, excluding boolean-like
- `describe_numeric_plainly(df)` — plain-English notes about numeric columns
- `get_high_missingness_rows(df, threshold)` — rows where >= threshold fraction of columns are missing. Threshold is user-provided (not hardcoded).
- `get_fully_empty_columns(df)` — columns that are 100% NaN

All logic as specified in the brief.

### `utils/audit.py` (snapshots + logging)

As specified in the brief, with `MAX_HISTORY = 5` (changed from 10).

### `utils/state.py` (session state init)

As specified in the brief, with updated `DEFAULTS` to include the new stage values.

### `utils/cleaner.py` (all mutations)

Every function follows the pattern: accept `df` + parameters, return `(new_df, rows_affected, details_dict)`. Never calls `save_snapshot()` or `log_action()`.

Functions:
- `replace_disguised_nulls_in_column(df, col, suspicious_values)`
- `replace_zeros_with_nan(df, col)`
- `drop_rows_by_index(df, index)`
- `drop_column(df, col)`
- `impute_mean(df, col)`, `impute_median(df, col)`, `impute_mode(df, col)`
- `impute_group_median(df, col, group_by_cols)` — fills NaN in grouping columns with `'__MISSING__'` sentinel before groupby. Returns count of group fills vs fallback fills. Logs both separately.
- `impute_custom(df, col, value)`
- `impute_marker(df, col, marker='Unknown')`
- `impute_date(df, col, strategy)` where strategy ∈ `{'most_recent', 'oldest', 'median', 'custom'}`
- `apply_type_conversion(df, col, target_type)` — converts column to intended type. Infers date format from first 100 non-null values, then applies to full column. Returns count of non-conforming values that became NaN.
- `remove_duplicates(df, keep='first')`

### `utils/recipe.py` (reproducibility code generation)

- `generate_recipe(audit_log, original_filename)` — reads the audit log and generates a complete, runnable Python script using pandas that reproduces every cleaning step.

---

## File Loading

Robust encoding handling as specified in the brief:

```
Encoding chain for CSV: utf-8-sig → utf-8 → cp1252 → latin-1
```

`utf-8-sig` first to catch BOM-prefixed files from Excel exports.

---

## Phase Details

### Phase 0 — Upload (Landing Page)

**Layout:** Centred, minimal.

**Display:**
- App name: **CleanSlate**
- Tagline: *"Understand your data. Clean it together."*
- File uploader accepting `csv`, `xlsx`, `xls`
- Help text: *"Your file stays on your machine. Nothing is sent anywhere."*

**On upload:**
1. Load file using `load_file()`.
2. Store in session state: `original_df`, `working_df` (copy), `filename`, `file_size_mb`, `undo_enabled`.
3. If `undo_enabled` is False: info banner about large file.
4. Move to `stage = 'portrait'`.

---

### Phase 1 — Data Portrait (Step 1 of 7)

**Heading:** 📊 Your Data Portrait
**Subheading:** *"Before we touch anything, let's understand what you're working with."*

**Section A — The Basics:** Metric cards for file name, row count, column count, memory size.

**Section B — First Look:** First 4 rows displayed.

**Section C — Column Summary Table:** Column name, detected type, non-null count, null count, null %, unique values, sample values (first 3). Colour coding: 0% green, 0–5% yellow, >5% red.

**Section D — Statistical Summary:** `df.describe(include='number')` transposed, plus plain-English notes from `describe_numeric_plainly()`.

**Section E — Categorical Value Counts:** Expanders per categorical column with unique count and top 5 values.

**Section F — Health Snapshot:** Traffic-light summary for missing values, data types, zeros, duplicates, disguised nulls, fully empty columns.

**Navigation:** "I've reviewed my data — start cleaning →" → `stage = 'diagnose'`

---

### Phase 2 — Column Contracts (Step 2 of 7)

**Heading:** 🔍 Step 2 of 7: Confirm Your Column Types

**Caption:** *"Before fixing anything, let's agree on what each column is supposed to contain. This guides every cleaning decision that follows."*

**Display:** Scrollable table. Per column:
- Column name
- Current stored dtype
- Suggested intended type (from `detect_column_type`)
- Editable selectbox to confirm or change

**Selectbox options:** `Continuous Number`, `Category`, `Date / Time`, `Text`, `Boolean`, `ID / Identifier`

**No "Drop this column" option here.** Dropping empty columns happens in Phase 5.1 where it belongs (it's a missing-values problem).

**Info note:** *"💡 Why does this matter? The type you confirm tells us which cleaning options make sense. You can't fill a date column with an average."*

**On confirmation:**
1. Store contracts in `column_contracts` (no mutations to data).
2. `log_action(method='type_confirmation')` for each column.
3. Run `find_disguised_nulls()` and store results.
4. Run `find_zero_columns()` and store results.
5. Move to `stage = 'nulls'`.

---

### Phase 3 — Disguised Nulls (Step 3 of 7)

**If no disguised nulls:** ✅ message, "Next →" button to `stage = 'zeros'`.

**If found:**

**Heading:** 🔍 Step 3 of 7: Hidden Missing Values
**Caption:** *"We found values that look like missing data but aren't being read as null yet."*

Display table: Column | Suspicious Value | Count. Plus 3 example rows.

**Options:**
- ✅ Yes — treat all as missing *(Recommended)*
- ❌ No — they are valid text
- 🔍 Decide per column

**On "Yes":** `save_snapshot()` → replace all → `log_action()` per column → confirmation message.

**On "Per Column":** One mini card per affected column.

Move to `stage = 'zeros'`.

---

### Phase 4 — Zero Values (Step 4 of 7)

**If no qualifying zero columns:** ✅ message, advance to `stage = 'missing_bulk'`.

**If found:**

**Heading:** 🔍 Step 4 of 7: Zero Values
**Caption:** *"Zeros can be legitimate or they can mean missing data recorded as zero."*

One card at a time per column showing: column name, zero count, non-zero range (min → max), mean excluding zeros, actual rows with zeros (max 10).

**Options:**
- ❌ No — treat zeros as missing *(Suggested)*
- ✅ Yes — zero is a legitimate value

`save_snapshot()` before action, `log_action()` after.

After all columns: move to `stage = 'missing_bulk'`.

---

### Phase 5.1 — Missing Values: Bulk Cleanup (Step 5 of 7, part 1)

**Heading:** 🧹 Step 5 of 7: Missing Values

At the start, recompute missingness (after Phases 3 and 4 have been applied).

**Opening Summary:**
- Total rows
- Columns with missing values
- Total missing cells (count and %)
- Horizontal bar per column showing % missing (green <1%, yellow 1–10%, red >10%)

**Fully Empty Columns:** If any columns are 100% missing:
*"⚠️ These columns are entirely empty. Imputation is not possible."*
Per column: [Drop column] *(Recommended)* | [Keep as-is]

**High-Missingness Rows:** User inputs a percentage threshold via a number input (default suggested: 30%). Show how many rows would be affected at that threshold. Show those rows with NaN cells highlighted.

Options:
- [Drop these rows] *(Recommended)*
- [Keep them]

**Duplicate info note:** *"💡 You have X duplicate rows. These will be handled in Step 8."*

After bulk cleanup: recompute `missing_value_cols`, move to `stage = 'missing_columns'`.

---

### Phase 5.2 — Missing Values: Column-by-Column (Step 5 of 7, part 2)

Track progress with `current_col_idx`. Show "Column X of Y with missing values" + progress bar.

**Decision card per column** showing: column name, confirmed type (from Phase 2), missing count and %, type-relevant stats, actual missing rows (max 10).

#### Options by confirmed type

**Continuous Number:**
- A) Drop these rows → show row count impact
- B) Fill with mean → show value; warn if skewed
- C) Fill with median → show value
- D) Fill with group median → multi-select grouping columns; guardrails for small groups; NaN in grouping columns handled with sentinel; logs group fills and fallback fills separately
- E) Fill with custom value → numeric input
- F) Leave for now → logged as `skip_column`

**Category (text or numeric):**
- A) Fill with mode → show most common value
- B) Fill with custom category → text input
- C) Drop these rows
- D) Mark as 'Unknown'
- E) Leave for now

**Date:**
- A) Drop these rows
- B) Fill with most recent date
- C) Fill with oldest date
- D) Fill with median date
- E) Custom date input
- F) Leave for now

**Identifier / Boolean:**
- A) Drop these rows
- B) Mark as 'Unknown' / 'Missing' (identifier only)
- C) Leave for now

**Free Text:**
- A) Drop these rows
- B) Fill with empty string
- C) Mark as 'Unknown'
- D) Leave for now

#### After each decision:
1. `save_snapshot()`
2. Apply via `cleaner.py`
3. `log_action()`
4. Preview: sample of updated column, before/after missing count
5. [Looks good — next column →] | [Undo — let me reconsider]

After all columns: summary of resolved vs skipped. Move to `stage = 'type_convert'`.

---

### Phase 6 — Type Conversion (Step 6 of 7)

**Heading:** 🔄 Step 6 of 7: Apply Data Types

**Caption:** *"Now that missing values are handled, let's convert columns to their confirmed types."*

Display a table showing each column with:
- Column name
- Current dtype
- Intended type (from Phase 2 contract)
- Status: ✅ Already correct | 🔄 Needs conversion | ⚠️ Conversion may lose data

**For columns that need conversion:**
- Show a preview of what would change (first 5 affected values)
- If conversion would produce NaN (non-conforming values), warn with count

**Date conversion performance fix:** Infer format from first 100 non-null values, then apply explicit format to the full column.

**Options:**
- [✅ Apply all conversions] *(Recommended)*
- [🔍 Review one by one]
- Per-column: [Apply] | [Skip]

`save_snapshot()` before each conversion, `log_action(method='type_conversion')` after.

After all conversions: move to `stage = 'duplicates'`.

---

### Phase 7 — Duplicates (Step 7 of 7)

**Heading:** 🔍 Step 7 of 7: Duplicate Rows

If 0 duplicates: ✅ message → `stage = 'done'`.

If found: show count, display duplicate rows (max 20, sorted).

**Options:**
- Remove duplicates — keep first *(Recommended)*
- Remove duplicates — keep last
- Keep all — duplicates are intentional

`save_snapshot()` → apply → `log_action()` → preview → [Confirm] | [Undo]

Move to `stage = 'done'`.

---

### Phase 8 — Completion (Done)

**Heading:** 🎉 Your Data is Clean

**Before vs After Stats:**

|  | Before | After | Change |
|---|---|---|---|
| Rows | ... | ... | ... |
| Columns | ... | ... | ... |
| Missing cells | ... | ... | ... |
| Duplicates | ... | ... | ... |
| Disguised nulls resolved | 0 | ... | ... |

**Full Audit Log:** Displayed as a dataframe.

**Download Buttons (side by side):**
- ⬇ Download Clean CSV → `clean_[original_filename].csv`
- ⬇ Download Audit Log CSV → `auditlog_[original_filename].csv`

**Reproducibility Recipe:** Collapsed expander with auto-generated pandas code from the audit log.

**Reset:** 🔄 Clean another file → `reset_session_state()` → `stage = 'upload'`.

---

## Sidebar (visible after upload)

- App name: **CleanSlate 🧹**
- Progress tracker with checkmarks (Steps 1–7 + Done)
- Divider
- Current file: `[filename]`
- Rows remaining: live count
- Missing cells left: live count
- Undo status: ✅ Enabled / ⚠️ Disabled (large file)
- Divider
- Audit Log: X actions recorded
- Last 3 entries as mini list
- [Download partial audit log] — available at any phase

---

## Implementation Rules

1. **Never modify `original_df`.** Only `working_df`.
2. **Always call `save_snapshot()` BEFORE any mutation** of `working_df`.
3. **Every mutation must call `log_action()`** with a method from the controlled vocabulary.
4. **Use `st.rerun()` after every stage transition** and after major state changes within a phase.
5. **Phase 2 makes no mutations** — only stores contracts.
6. **Phase 5.1 row threshold is user-defined** — default suggested at 30%, but user can change.
7. **Group median handles NaN in grouping columns** — fill with `'__MISSING__'` sentinel before groupby.
8. **Date conversion infers format** from first 100 non-null values, then applies to full column.
9. **Undo history capped at 5 snapshots.** Disabled entirely for files over 200MB.
10. **All phase logic as functions in `app.py`.**
11. **Routing:**
    ```python
    routes = {
        'upload': show_upload, 'portrait': show_portrait,
        'diagnose': show_diagnose, 'nulls': show_nulls,
        'zeros': show_zeros, 'missing_bulk': show_missing_bulk,
        'missing_columns': show_missing_columns,
        'type_convert': show_type_conversion,
        'duplicates': show_duplicates, 'done': show_completion,
    }
    ```
12. **Local only.** No authentication, no database, no cloud.
13. **Never call `pd.to_datetime` without `errors='coerce'`.**

---

## Testing Checklist

- [ ] Upload a CSV with BOM — loads correctly
- [ ] Upload an Excel file — loads correctly
- [ ] Upload a file with a 100%-empty column — offered drop in Phase 5.1
- [ ] Upload a file with "N/A", "n/a", "  ", "?" — all detected as disguised nulls
- [ ] Upload a file with a boolean 0/1 flag column — NOT flagged in Phase 4
- [ ] Upload a file with a real zero-containing column — flagged in Phase 4
- [ ] Group median imputation with NaN in grouping column — sentinel fill works, no rows silently dropped
- [ ] Group median with high-cardinality group — small-group warning fires, fallback logs correctly
- [ ] Undo works across phases and decrements the audit log
- [ ] Large file (>200MB) — undo disabled banner shown, no memory explosion
- [ ] Column named "postcode" or "customer_id" — classified as identifier
- [ ] Phase 2 makes no data mutations — only stores contracts
- [ ] Phase 5.1 row threshold is user-configurable
- [ ] Phase 6 type conversion applied after missing values resolved
- [ ] Date conversion uses inferred format (not guessing per row)
- [ ] Reset button fully clears session state
- [ ] Audit log CSV + Clean CSV both downloadable at completion
- [ ] Reproducibility recipe generates valid pandas code
- [ ] Test with `Test Data_Aurora Gems.csv` — exercises all phases

---

**End of Spec — CleanSlate v1.0**
