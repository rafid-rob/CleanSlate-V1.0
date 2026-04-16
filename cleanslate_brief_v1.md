# CleanSlate v1.0 — Guided Data Cleaning Wizard

**Version:** 1.0 Local (runs entirely on your machine)
**Stack:** Python + Streamlit
**Scope:** Understand → Diagnose → Decide → Clean → Confirm
**Covers:** Missing values, data types, duplicates, disguised nulls, zero-as-missing
**Does NOT cover (this version):** Outlier detection, transformations, feature engineering

---

## Core Philosophy

CleanSlate is a partner, not an autopilot.

1. It never modifies data without user approval.
2. It always shows before it acts.
3. It always explains before it asks.
4. Every decision is recorded in an auditable log.
5. The original uploaded file is never touched.
6. Every action is reversible.

The sequence is always: **UNDERSTAND → DIAGNOSE → DECIDE → CLEAN → CONFIRM**

---

## File Structure

```
cleanslate/
├── app.py                  # main entry point + routing
├── utils/
│   ├── __init__.py         # empty
│   ├── scanner.py          # detection logic (read-only)
│   ├── cleaner.py          # cleaning operations (write)
│   ├── audit.py            # audit log + snapshot management
│   └── state.py            # session state initialisation
├── requirements.txt
└── README.md
```

### requirements.txt
```
streamlit>=1.32.0
pandas>=2.0.0
numpy>=1.24.0
openpyxl>=3.1.0
xlrd>=2.0.1
chardet>=5.2.0
```

### README.md
```
# CleanSlate — Local Version

## Setup
pip install -r requirements.txt

## Run
streamlit run app.py

## Notes
- All data stays on your machine. Nothing is sent to any server.
- Supports CSV, XLSX, XLS.
- Undo is available for the last 10 actions (disabled automatically for files over 200MB).
```

---

## Session State Architecture

All session state is initialised in a single `init_session_state()` function in `utils/state.py`, called once at the top of `app.py` before any routing logic runs. This prevents KeyErrors on first load.

### Keys

| Key | Type | Purpose |
|---|---|---|
| `stage` | str | Current phase. Values: `'upload'`, `'portrait'`, `'diagnose'`, `'nulls'`, `'zeros'`, `'missing'`, `'duplicates'`, `'done'` |
| `original_df` | DataFrame | Raw upload. **NEVER modified.** |
| `working_df` | DataFrame | The copy being cleaned. All mutations happen here. |
| `filename` | str | Original filename |
| `file_size_mb` | float | File size in MB (used to disable undo for large files) |
| `undo_enabled` | bool | False if `file_size_mb > 200`. |
| `column_contracts` | dict | `{col_name: {'detected_type': str, 'intended_type': str, 'confirmed': bool, 'notes': str}}` |
| `audit_log` | list[dict] | See audit schema below |
| `history` | list[DataFrame] | Snapshots for undo. Max 10. |
| `current_col_idx` | int | Progress tracker for Phase 5 column-by-column flow |
| `missing_value_cols` | list[str] | Ordered list of columns to process in Phase 5 |
| `disguised_nulls` | dict | `{col_name: [suspicious_values]}` |
| `zero_cols` | list[str] | Numeric columns with zeros (excluding boolean-like) |
| `skipped_cols` | list[str] | Columns the user chose to leave for now in Phase 5 |

### Audit Log Schema (fixed vocabulary)

Every entry has exactly these fields:

```python
{
    'timestamp': str,          # ISO format
    'phase': str,              # 'diagnose' | 'disguised_nulls' | 'zeros' | 'missing' | 'duplicates'
    'column': str,             # column name or '*' for whole-dataset actions
    'issue': str,              # human-readable issue description
    'decision': str,           # human-readable decision
    'rows_affected': int,      # count of rows changed
    'method': str,             # controlled vocabulary — see below
    'details': dict            # method-specific details (e.g., {'value': 42.5, 'group_by': ['region']})
}
```

**Controlled vocabulary for `method`:**

- `type_confirmation` — column contract set
- `replace_disguised_nulls` — suspicious strings → NaN
- `zero_as_missing` — zeros replaced with NaN
- `zero_kept_valid` — user confirmed zeros are valid
- `drop_rows_high_missingness` — row-wise drop (≥30% missing)
- `drop_rows_column_missing` — rows dropped due to single column NaN
- `impute_mean` — fill with column mean
- `impute_median` — fill with column median
- `impute_mode` — fill with column mode
- `impute_group_median` — fill with median within group
- `impute_group_median_fallback` — rows where group median failed; global median used
- `impute_custom_value` — user-specified constant
- `impute_marker_unknown` — filled with 'Unknown' marker
- `impute_most_recent_date` / `impute_oldest_date` / `impute_median_date`
- `drop_empty_column` — column was 100% missing
- `skip_column` — user chose "leave for now"
- `remove_duplicates_keep_first` / `remove_duplicates_keep_last`
- `keep_duplicates`

---

## Helper Functions

### `utils/scanner.py` (read-only detection)

```python
import pandas as pd
import numpy as np

# Lowercased for case-insensitive matching
KNOWN_NULL_STRINGS = {
    '', ' ', '  ', 'na', 'n/a', 'n.a.', 'n.a',
    'nan', 'none', 'null', '?', '-', '--', '---',
    'missing', 'nil', 'undefined', 'unknown'
}

ID_HINT_KEYWORDS = {
    'id', 'code', 'number', 'sku', 'postcode',
    'zip', 'phone', 'uuid', 'ref', 'identifier'
}


def is_likely_id_column(col_name: str) -> bool:
    """Column names that suggest identifiers should not be auto-detected as dates/numerics."""
    name_lower = col_name.lower()
    return any(hint in name_lower.split('_') or hint in name_lower.split(' ')
               for hint in ID_HINT_KEYWORDS)


def detect_column_type(series: pd.Series, col_name: str = '') -> str:
    """
    Returns one of:
      'continuous_numeric', 'categorical_numeric', 'categorical_text',
      'free_text', 'datetime', 'boolean', 'identifier', 'empty'
    """
    non_null = series.dropna()

    # Handle fully empty columns
    if len(non_null) == 0:
        return 'empty'

    # ID hint from column name takes precedence
    if is_likely_id_column(col_name):
        return 'identifier'

    # Boolean check (case-insensitive)
    str_vals = non_null.astype(str).str.strip().str.lower()
    boolean_set = {'true', 'false', 'yes', 'no', '0', '1', 'y', 'n', 't', 'f'}
    if set(str_vals.unique()).issubset(boolean_set) and series.nunique(dropna=True) <= 2:
        return 'boolean'

    # Datetime check — conservative, only for object columns
    if series.dtype == 'object':
        sample = non_null.head(50)
        try:
            parsed = pd.to_datetime(sample, errors='coerce')
            parse_rate = parsed.notna().sum() / len(sample)
            # Require 90% parse rate AND column not named like an ID
            if parse_rate >= 0.9:
                return 'datetime'
        except (ValueError, TypeError):
            pass

    # Native datetime dtype
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'

    # Numeric handling
    if pd.api.types.is_numeric_dtype(series):
        unique_count = series.nunique(dropna=True)
        if unique_count <= 15:
            return 'categorical_numeric'
        return 'continuous_numeric'

    # Object: try numeric coercion
    if series.dtype == 'object':
        converted = pd.to_numeric(non_null, errors='coerce')
        numeric_rate = converted.notna().sum() / len(non_null)
        if numeric_rate > 0.8:
            if converted.nunique() <= 15:
                return 'categorical_numeric'
            return 'continuous_numeric'

        unique_count = non_null.nunique()
        if unique_count <= 20:
            return 'categorical_text'
        return 'free_text'

    return 'continuous_numeric'


def find_disguised_nulls(df: pd.DataFrame) -> dict:
    """Returns {col_name: [suspicious_values_as_seen_in_data]}."""
    results = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            found = []
            for val in df[col].dropna().unique():
                normalised = str(val).strip().lower()
                if normalised in KNOWN_NULL_STRINGS:
                    found.append(val)  # preserve original casing for display
            if found:
                results[col] = found
    return results


def find_zero_columns(df: pd.DataFrame) -> list:
    """
    Numeric columns containing zeros, EXCLUDING columns that look like
    boolean/flag (only values are 0 and 1) — asking 'is zero valid?' there is nonsensical.
    """
    zero_cols = []
    for col in df.select_dtypes(include=['number']).columns:
        unique_vals = set(df[col].dropna().unique())
        if 0 in unique_vals or 0.0 in unique_vals:
            # Skip binary/flag columns
            if unique_vals.issubset({0, 1, 0.0, 1.0}):
                continue
            zero_cols.append(col)
    return zero_cols


def describe_numeric_plainly(df: pd.DataFrame) -> list:
    """Returns a list of plain-English notes about numeric columns."""
    notes = []
    for col in df.select_dtypes(include=['number']).columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue

        # Skip tiny-value edge cases for skew detection
        if s.nunique() < 3:
            continue

        mean = s.mean()
        median = s.median()
        std = s.std()

        # Skew detection — mean vs median ratio is more robust than percentile thresholds
        if median != 0 and abs(mean - median) / abs(median) > 0.5:
            direction = 'right' if mean > median else 'left'
            notes.append(f"ℹ️ **{col}** appears {direction}-skewed (mean {mean:.2f} vs median {median:.2f}). "
                         f"Median may be more reliable for imputation.")

        # Coefficient of variation for high variability
        if mean != 0 and std / abs(mean) > 1.0:
            notes.append(f"ℹ️ **{col}** has high relative variability.")

        # Zero presence
        if (df[col] == 0).any():
            zero_count = (df[col] == 0).sum()
            notes.append(f"⚠️ **{col}** contains {zero_count} zero values — may need review in Phase 4.")

    return notes


def get_high_missingness_rows(df: pd.DataFrame, threshold: float = 0.3) -> pd.Index:
    """
    Returns index of rows where ≥ threshold of columns are missing.
    Called AFTER disguised nulls and zero decisions are applied.
    """
    row_missing_pct = df.isna().sum(axis=1) / len(df.columns)
    return df.index[row_missing_pct >= threshold]


def get_fully_empty_columns(df: pd.DataFrame) -> list:
    """Columns that are 100% NaN."""
    return [col for col in df.columns if df[col].isna().all()]
```

### `utils/audit.py` (snapshots + logging)

```python
import streamlit as st
import pandas as pd
from datetime import datetime
import sys

MAX_HISTORY = 10
UNDO_SIZE_LIMIT_MB = 200


def estimate_df_memory_mb(df: pd.DataFrame) -> float:
    return df.memory_usage(deep=True).sum() / (1024 ** 2)


def save_snapshot(df: pd.DataFrame):
    """Save df copy to history for undo. Skips if undo is disabled for this session."""
    if not st.session_state.get('undo_enabled', True):
        return
    if 'history' not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append(df.copy())
    if len(st.session_state.history) > MAX_HISTORY:
        st.session_state.history.pop(0)


def undo() -> bool:
    """Restore last snapshot. Returns True if successful."""
    if not st.session_state.get('undo_enabled', True):
        return False
    if st.session_state.get('history'):
        st.session_state.working_df = st.session_state.history.pop()
        # Also pop the last audit log entry so the log reflects reality
        if st.session_state.audit_log:
            st.session_state.audit_log.pop()
        return True
    return False


def log_action(phase: str, column: str, issue: str, decision: str,
               rows_affected: int, method: str, details: dict = None):
    """Append an entry to the audit log using the controlled vocabulary."""
    st.session_state.audit_log.append({
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'phase': phase,
        'column': column,
        'issue': issue,
        'decision': decision,
        'rows_affected': int(rows_affected),
        'method': method,
        'details': details or {}
    })
```

### `utils/state.py` (single source of truth for initialisation)

```python
import streamlit as st

DEFAULTS = {
    'stage': 'upload',
    'original_df': None,
    'working_df': None,
    'filename': None,
    'file_size_mb': 0.0,
    'undo_enabled': True,
    'column_contracts': {},
    'audit_log': [],
    'history': [],
    'current_col_idx': 0,
    'missing_value_cols': [],
    'disguised_nulls': {},
    'zero_cols': [],
    'skipped_cols': [],
}


def init_session_state():
    for key, default in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_session_state():
    """Clear everything — used by 'Clean another file'."""
    for key in list(DEFAULTS.keys()):
        st.session_state[key] = DEFAULTS[key] if not isinstance(DEFAULTS[key], (list, dict)) \
            else type(DEFAULTS[key])()
    st.session_state.stage = 'upload'
```

### `utils/cleaner.py` (all mutations go through here)

Every function in `cleaner.py` follows the same pattern:
1. Accept `df` and parameters.
2. Return `(new_df, rows_affected, details_dict)`.
3. Never call `save_snapshot` or `log_action` directly — those are called by the phase handler in `app.py` so the phase controls the transaction boundary.

Key functions to implement:
- `replace_disguised_nulls_in_column(df, col, suspicious_values)`
- `replace_zeros_with_nan(df, col)`
- `drop_rows_by_index(df, index)`
- `impute_mean(df, col)`, `impute_median(df, col)`, `impute_mode(df, col)`
- `impute_group_median(df, col, group_by_cols)` — **must return count of rows filled via group median vs fallback to global median, and log both separately**
- `impute_custom(df, col, value)`
- `impute_marker(df, col, marker='Unknown')`
- `impute_date(df, col, strategy)` where strategy ∈ `{'most_recent', 'oldest', 'median', 'custom'}`
- `apply_type_conversion(df, col, target_type)` — converts column to intended type, returns count of non-conforming values that became NaN
- `remove_duplicates(df, keep='first')`

---

## File Loading (robust encoding handling)

```python
def load_file(uploaded_file):
    """
    Loads CSV or Excel robustly.
    Encoding chain for CSV: utf-8-sig → utf-8 → cp1252 → latin-1
    (utf-8-sig first catches BOM-prefixed files from Excel exports.)
    """
    name = uploaded_file.name.lower()
    if name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(uploaded_file)

    # CSV path
    encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']
    last_error = None
    for enc in encodings:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
    raise ValueError(f"Could not decode CSV with any of {encodings}. Last error: {last_error}")
```

---

## PHASE 0 — Upload

**Layout:** centred, minimal.

**Display:**
- App name: **CleanSlate**
- Tagline: *"Understand your data. Clean it together."*
- File uploader accepting `csv`, `xlsx`, `xls`
- Help text: *"Your file stays on your machine. Nothing is sent anywhere."*

**On upload:**
1. Load file using `load_file()` above.
2. Store in session state:
   - `original_df = df` (never modified from here on)
   - `working_df = df.copy()`
   - `filename = uploaded_file.name`
   - `file_size_mb = estimate_df_memory_mb(df)`
   - `undo_enabled = file_size_mb <= 200`
   - `audit_log = []`, `history = []`
3. If `undo_enabled` is False, show a one-time info banner: *"Your file is large (over 200MB). Undo history is disabled to preserve memory. All actions are still logged."*
4. Move to `stage = 'portrait'`.

---

## PHASE 1 — Data Portrait

**Heading:** 📊 Your Data Portrait
**Subheading:** *"Before we touch anything, let's understand what you're working with."*

### Section A — The Basics
Row of metric cards:
- 📁 File name
- 📏 Row count (formatted with commas)
- 📋 Column count
- 💾 Memory size (KB or MB)

### Section B — First Look
Subheading: "First 4 Rows"
Caption: *"A quick look at what your data contains."*
Display: `st.dataframe(df.head(4), use_container_width=True)`

### Section C — Column Summary Table
Columns:
- Column Name
- Detected Type (from `detect_column_type`)
- Non-Null Count
- Null Count
- Null %
- Unique Values
- Sample Values (first 3 unique non-null)

Colour coding for Null %:
- 0% → green
- 0–5% → yellow
- >5% → red

### Section D — Statistical Summary
Display: `st.dataframe(df.describe(include='number').round(2).T, use_container_width=True)`

Below the table, render notes from `describe_numeric_plainly(df)`.

### Section E — Categorical Value Counts
For each column detected as categorical (text or numeric), inside an `st.expander`:
- Column name
- Unique count
- Top 5 values with their counts

### Section F — Health Snapshot
Traffic-light summary:
- Missing Values → ✅ None / ⚠️ X cells missing
- Data Types → ✅ All clear / ⚠️ X need review
- Zero Values → ✅ None / ⚠️ X columns have zeros (excluding binary flags)
- Duplicates → ✅ None / ⚠️ X duplicate rows
- Disguised Nulls → ✅ None / ⚠️ Found in X columns
- Fully Empty Columns → ✅ None / ⚠️ X columns are 100% empty

### Navigation
Single button: **"I've reviewed my data — start cleaning →"**
→ Move to `stage = 'diagnose'`

---

## PHASE 2 — Diagnose: Column Contracts

**Heading:** 🔍 Step 1 of 5: Confirm Your Column Types

**Caption:** *"Before fixing anything, let's agree on what each column is supposed to contain. This guides every cleaning decision that follows."*

Display a scrollable table. For each column, one row with:
- Column name
- Current stored dtype (from `df.dtypes`)
- Suggested intended type (from `detect_column_type`)
- Issues detected (disguised nulls present / zeros present / fully empty)
- Editable selectbox to confirm or change type

**Selectbox options:**
- `Continuous Number`
- `Category`
- `Date / Time`
- `Text`
- `Boolean`
- `ID / Identifier`
- `Drop this column` ← new option for fully empty or clearly useless columns

**Special handling for fully empty columns:**
Highlight the row and pre-select "Drop this column". User can override.

**Info note:** *"💡 Why does this matter? The type you confirm tells us which cleaning options make sense. You can't fill a date column with an average."*

**Button:** ✅ Confirm All Column Types →

**On confirmation:**
1. `save_snapshot()`
2. For each column marked for drop: drop from `working_df`, `log_action(method='drop_empty_column')`
3. For each column with changed type: attempt type conversion, `log_action(method='type_confirmation', details={'from': ..., 'to': ..., 'coercion_losses': ...})`
4. Store final contracts in `st.session_state.column_contracts`
5. Move to `stage = 'nulls'`

---

## PHASE 3 — Disguised Null Values

**If no disguised nulls:** Show ✅ *"No hidden null values detected."* Auto-advance via "Next →" button to `stage = 'zeros'`.

**If disguised nulls found:**

**Heading:** 🔍 Step 2 of 5: Hidden Missing Values
**Caption:** *"We found values that look like missing data but aren't being read as null yet. We need to fix this before counting what's actually missing."*

Display table:
| Column | Suspicious Value | Count |

Show 3 example rows from the dataframe where these values appear.

**Single question:** *"Treat all of these as missing values (NaN)?"*

Buttons:
- [✅ Yes — treat all as missing] *(Recommended)*
- [❌ No — they are valid text]
- [🔍 Decide per column]

**If Yes:**
1. `save_snapshot()`
2. Replace suspicious values with NaN using case-insensitive matching against `KNOWN_NULL_STRINGS`
3. `log_action(method='replace_disguised_nulls')` per column affected
4. Show confirmation: *"Done. X values now correctly read as null."*

**If Per Column:** Show one mini Yes/No card per affected column.

Move to `stage = 'zeros'`.

---

## PHASE 4 — Zero Values

**If no qualifying zero columns:** Show ✅ *"No zeros found in numeric columns (excluding boolean flags)."* Auto-advance to `stage = 'missing'`.

**If zeros found:**

**Heading:** 🔍 Step 3 of 5: Zero Values
**Caption:** *"Zeros can be legitimate or they can mean missing data recorded as zero. Only you know which."*

For each column in `zero_cols`, show ONE card at a time:

```
┌──────────────────────────────────────────────┐
│ Column: [name]                               │
│ Zeros found: X rows                          │
│ All non-zero values: [min] → [max]           │
│ Column mean (excluding zeros): [value]       │
│                                              │
│ The rows with zero:                          │
│ [show actual rows, max 10]                   │
│                                              │
│ Is zero a valid value here?                  │
│                                              │
│ [❌ No — treat zeros as missing] (Suggested) │
│ [✅ Yes — zero is a legitimate value]        │
└──────────────────────────────────────────────┘
```

Before action: `save_snapshot()`.
After action: `log_action(method='zero_as_missing' | 'zero_kept_valid')`.

After all columns processed: *"Zero check complete."* Move to `stage = 'missing'`.

---

## PHASE 5 — Missing Values (Core Cleaning Phase)

**Heading:** 🧹 Step 4 of 5: Missing Values

### 5A — Recompute Missingness (critical ordering)

At the start of this phase, **after Phases 3 and 4 have been applied**, recompute:
- `st.session_state.missing_value_cols` = columns with any NaN (ordered by % missing, ascending)
- `high_miss_rows` = `get_high_missingness_rows(working_df, 0.3)`
- `empty_cols_remaining` = fully empty columns that survived Phase 2

### 5B — Opening Summary
- Total rows
- Columns with missing values
- Total missing cells (count and %)

Horizontal bar per column showing % missing. Colour: green <1%, yellow 1–10%, red >10%.

### 5C — Fully Empty Columns
If any columns are 100% missing, show them first:

*"⚠️ These columns are entirely empty. Imputation is not possible."*
Per column: [Drop column] *(Recommended)* [Keep as-is]

### 5D — High-Missingness Rows
If `high_miss_rows` is non-empty:

*"⚠️ X rows have 30%+ of columns missing. Imputing these would be unreliable."*

Show the actual rows (NaN cells highlighted).

Options:
- [Drop these rows] *(Recommended)*
- [Keep them]

Log with `method='drop_rows_high_missingness'` if dropped.

### 5E — Deduplicate First? (optional detour)

Display an info banner:
*"💡 You have X duplicate rows. Imputing values for rows you're about to drop wastes effort. Handle duplicates now?"*

Buttons:
- [Yes, handle duplicates first →] (jump to Phase 6, return here after)
- [No, continue with missing values]

If the user accepts: run Phase 6, then return to this point with recomputed state.

### 5F — Column-by-Column Decisions

Track progress with `st.session_state.current_col_idx`.

Show:
- *"Column X of Y with missing values"*
- `st.progress(current_col_idx / total)`

**Decision card per column:**

```
┌──────────────────────────────────────────────┐
│ Column: [name]                               │
│ Confirmed Type: [from Phase 2]               │
│ Missing: X rows (Y%)                         │
│                                              │
│ Stats relevant to type:                      │
│   Continuous Number → min, max, mean,        │
│                       median, std dev        │
│   Category → unique count, top 5 counts,     │
│              most common                     │
│   Date → earliest, latest, median            │
│                                              │
│ The missing rows (max 10 shown):             │
│ [actual rows from working_df]                │
│                                              │
│ What would you like to do?                   │
│ [OPTIONS — see below]                        │
└──────────────────────────────────────────────┘
```

#### Options by confirmed type

**CONTINUOUS NUMBER:**
- **A) Drop these rows** → show "Dataset goes from X → Y rows (Z% loss)"
- **B) Fill with mean** → show computed value; warn if skewed (use mean vs median deviation): *"⚠️ This column is right-skewed. Median may be more reliable."*
- **C) Fill with median** → show value
- **D) Fill with group median**
   - Multi-select: which columns to group by
   - **Guardrails (critical):**
     - Warn if any group has <3 non-null values: *"⚠️ Some groups have very few observations. Those fills may be unreliable."*
     - For groups with zero non-null values, fall back to **global median**
     - Log the two fill counts separately: `impute_group_median` (rows filled from group) and `impute_group_median_fallback` (rows filled from global median)
     - Include in `details`: `{'group_by': [...], 'group_fills': N, 'fallback_fills': M, 'small_groups': K}`
- **E) Fill with custom value** → numeric input
- **F) Leave for now** → logged as `skip_column`

**CATEGORY (text or numeric):**
- **A) Fill with mode (most common)** → show "Most common: '[value]' (X times)"
- **B) Fill with custom category** → text input
- **C) Drop these rows** → show impact
- **D) Mark as 'Unknown'** → *"Useful when 'not recorded' is meaningful."*
- **E) Leave for now**

**DATE:**
- **A) Drop these rows**
- **B) Fill with most recent date**
- **C) Fill with oldest date**
- **D) Fill with median date**
- **E) Custom date input**
- **F) Leave for now**

**IDENTIFIER / BOOLEAN:** Imputation is dangerous here — offer only:
- **A) Drop these rows**
- **B) Mark as 'Unknown' / 'Missing'** (identifier only)
- **C) Leave for now**

**FREE TEXT:**
- **A) Drop these rows**
- **B) Fill with empty string**
- **C) Mark as 'Unknown'**
- **D) Leave for now**

#### After each decision:

1. `save_snapshot()`
2. Apply action via `cleaner.py`
3. `log_action(...)`
4. Show preview:
   - *"✅ Done. Sample of updated column:"* [5 rows]
   - *"Before: X missing | After: Y missing"*
5. Two buttons:
   - [✓ Looks good — next column →]
   - [↩ Undo — let me reconsider] (disabled if `undo_enabled` is False)

Undo → `undo()`, re-display same decision card with original values.

#### After all columns:

- If zero remaining missing: 🎉 *"All missing values resolved!"*
- Else: *"Y values remain in Z columns (intentionally skipped):"* list columns in `skipped_cols`

**Button:** Proceed to Duplicates → `stage = 'duplicates'`

---

## PHASE 6 — Duplicates

**Heading:** 🔍 Step 5 of 5: Duplicate Rows

`duplicate_count = working_df.duplicated().sum()`

**If 0:**
✅ *"No duplicate rows found. Your data is clean."*
Button → `stage = 'done'`

**If duplicates found:**

*"We found X rows that appear more than once."*

Display duplicated rows sorted by their values, max 20 shown.

Options:
- [Remove duplicates — keep first] *(Recommended)*
- [Remove duplicates — keep last]
- [Keep all — duplicates are intentional]

Pattern:
1. `save_snapshot()`
2. Apply action
3. `log_action(method='remove_duplicates_keep_first' | 'remove_duplicates_keep_last' | 'keep_duplicates')`
4. Show confirmation + preview
5. [✓ Confirm] [↩ Undo]

Move to `stage = 'done'`.

---

## PHASE 7 — Completion

**Heading:** 🎉 Your Data is Clean

### Before vs After Stats

|  | Before | After | Change |
|---|---|---|---|
| Rows | … | … | … |
| Columns | … | … | … |
| Missing cells | … | … | … |
| Duplicates | … | … | … |
| Disguised nulls resolved | 0 | … | … |

### Full Audit Log

Display `audit_log` as a dataframe with columns:
`Timestamp | Phase | Column | Issue | Decision | Rows Affected | Method | Details`

### Download Buttons (side by side)

- **⬇ Download Clean CSV** → `clean_[original_filename].csv`
- **⬇ Download Audit Log CSV** → `auditlog_[original_filename].csv`

Both use `st.download_button()`.

### Optional — Reproducibility Recipe

Collapsed expander: *"📋 View the cleaning recipe (pandas code)"*
Auto-generate pandas code from the audit log so an analyst can reproduce the cleaning deterministically. This is a **huge** trust multiplier and cements the difference between CleanSlate and a black-box tool.

### Reset

**🔄 Clean another file** → calls `reset_session_state()`, returns to `stage = 'upload'`.

---

## Sidebar (visible in all phases after upload)

- App name: **CleanSlate 🧹**
- Progress tracker (✓ when phase completed):
  - ○ Upload
  - ○ Data Portrait
  - ○ Column Types
  - ○ Hidden Nulls
  - ○ Zero Values
  - ○ Missing Values
  - ○ Duplicates
  - ○ Done
- Divider
- Current file: `[filename]`
- Rows remaining: `[live count from working_df]`
- Missing cells left: `[live count]`
- Undo status: ✅ Enabled / ⚠️ Disabled (large file)
- Divider
- *"Audit Log: X actions recorded"*
- Last 3 entries as a mini list
- *[Download partial audit log]* — available at any phase

---

## Implementation Rules

1. **Never modify `original_df`.** Only `working_df`.
2. **Always call `save_snapshot()` BEFORE any mutation** of `working_df`.
3. **Every mutation must call `log_action()`** with a method from the controlled vocabulary.
4. **Use `st.rerun()` after every stage transition** and after every major state change within a phase.
5. **All phase logic as functions in `app.py`:**
   ```python
   def show_upload(): ...
   def show_portrait(): ...
   def show_diagnose(): ...
   def show_nulls(): ...
   def show_zeros(): ...
   def show_missing(): ...
   def show_duplicates(): ...
   def show_completion(): ...
   ```
6. **Routing in `app.py` (after `init_session_state()`):**
   ```python
   stage = st.session_state.stage
   routes = {
       'upload': show_upload, 'portrait': show_portrait,
       'diagnose': show_diagnose, 'nulls': show_nulls,
       'zeros': show_zeros, 'missing': show_missing,
       'duplicates': show_duplicates, 'done': show_completion,
   }
   routes[stage]()
   ```
7. **Local test version only.** No authentication, no database, no cloud.
8. **Test dataset:** diamond dataset (`data.csv`) — has disguised nulls, zeros, sparse missing values.
9. **Never call `pd.to_datetime` without `errors='coerce'`** and without a conservative parse-rate threshold.
10. **Every user-facing mutation shows a preview before committing** — the preview pattern is: card → decision → `save_snapshot` → mutation → preview + confirm/undo.

---

## Testing Checklist Before Shipping

- [ ] Upload a CSV with BOM — loads correctly
- [ ] Upload an Excel file — loads correctly
- [ ] Upload a file with a 100%-empty column — offered drop in Phase 2
- [ ] Upload a file with "N/A", "n/a", "  ", "?" — all detected as disguised nulls
- [ ] Upload a file with a boolean 0/1 flag column — NOT flagged in Phase 4
- [ ] Upload a file with a real zero-containing column — flagged in Phase 4
- [ ] Group median imputation with a high-cardinality group column — small-group warning fires, fallback logs correctly
- [ ] Undo works across phases and decrements the audit log
- [ ] Large file (>200MB) — undo disabled banner shown, no memory explosion
- [ ] Column named "postcode" or "customer_id" — classified as identifier, not date or numeric
- [ ] Reset button fully clears session state
- [ ] Audit log CSV + Clean CSV both downloadable at completion
- [ ] Reproducibility recipe generates valid pandas code

---

**End of Brief — CleanSlate v1.0 Local**
