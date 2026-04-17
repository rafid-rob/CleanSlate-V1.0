# CleanSlate v1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit data cleaning wizard with 7-step guided flow, audit logging, undo, and reproducibility recipe.

**Architecture:** Phase-by-phase build (Approach A). Utility modules built just-in-time as each phase needs them. TDD for all utility modules; Streamlit UI tested manually in the browser.

**Tech Stack:** Python 3.10+, Streamlit >= 1.32.0, pandas >= 2.0.0, numpy >= 1.24.0, openpyxl >= 3.1.0, xlrd >= 2.0.1, chardet >= 5.2.0, pytest

**Spec:** `docs/superpowers/specs/2026-04-17-cleanslate-v1-design.md`
**Original brief:** `cleanslate_brief_v1.md`
**Test data:** `Test Data_Aurora Gems.csv`

---

## Task 1: Project Scaffolding + State + Audit

**Files:**
- Create: `requirements.txt`
- Create: `utils/__init__.py`
- Create: `utils/state.py`
- Create: `utils/audit.py`
- Create: `tests/__init__.py`
- Create: `tests/test_audit.py`
- Create: `app.py` (minimal skeleton)

- [ ] **Step 1: Create `requirements.txt`**

```
streamlit>=1.32.0
pandas>=2.0.0
numpy>=1.24.0
openpyxl>=3.1.0
xlrd>=2.0.1
chardet>=5.2.0
pytest>=7.0.0
```

- [ ] **Step 2: Create `utils/__init__.py` and `tests/__init__.py`**

Both are empty files.

- [ ] **Step 3: Create `utils/state.py`**

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

- [ ] **Step 4: Write failing tests for `audit.py`**

Create `tests/test_audit.py`:

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch


def _make_session_state():
    """Create a dict-like mock of st.session_state."""
    state = {}

    class SessionState:
        def __getattr__(self, key):
            return state[key]

        def __setattr__(self, key, value):
            state[key] = value

        def __contains__(self, key):
            return key in state

        def get(self, key, default=None):
            return state.get(key, default)

    return SessionState(), state


@patch('utils.audit.st')
def test_estimate_df_memory_mb(mock_st):
    from utils.audit import estimate_df_memory_mb
    df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
    result = estimate_df_memory_mb(df)
    assert isinstance(result, float)
    assert result > 0


@patch('utils.audit.st')
def test_save_snapshot_appends_copy(mock_st):
    from utils.audit import save_snapshot
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = True
    state['history'] = []

    df = pd.DataFrame({'a': [1, 2, 3]})
    save_snapshot(df)

    assert len(state['history']) == 1
    # Verify it's a copy, not same object
    assert state['history'][0] is not df
    pd.testing.assert_frame_equal(state['history'][0], df)


@patch('utils.audit.st')
def test_save_snapshot_max_5(mock_st):
    from utils.audit import save_snapshot
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = True
    state['history'] = []

    df = pd.DataFrame({'a': [1]})
    for i in range(7):
        save_snapshot(pd.DataFrame({'a': [i]}))

    assert len(state['history']) == 5
    # Oldest should have been popped — first remaining is index 2
    assert state['history'][0].iloc[0, 0] == 2


@patch('utils.audit.st')
def test_save_snapshot_skips_when_disabled(mock_st):
    from utils.audit import save_snapshot
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = False
    state['history'] = []

    save_snapshot(pd.DataFrame({'a': [1]}))
    assert len(state['history']) == 0


@patch('utils.audit.st')
def test_undo_restores_last_snapshot(mock_st):
    from utils.audit import undo
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = True

    original = pd.DataFrame({'a': [10, 20]})
    state['history'] = [original.copy()]
    state['working_df'] = pd.DataFrame({'a': [99, 99]})
    state['audit_log'] = [{'method': 'test_action'}]

    result = undo()

    assert result is True
    pd.testing.assert_frame_equal(state['working_df'], original)
    assert len(state['history']) == 0
    assert len(state['audit_log']) == 0


@patch('utils.audit.st')
def test_undo_returns_false_when_empty(mock_st):
    from utils.audit import undo
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = True
    state['history'] = []

    assert undo() is False


@patch('utils.audit.st')
def test_undo_returns_false_when_disabled(mock_st):
    from utils.audit import undo
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = False
    state['history'] = [pd.DataFrame({'a': [1]})]

    assert undo() is False


@patch('utils.audit.st')
def test_log_action_appends_entry(mock_st):
    from utils.audit import log_action
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['audit_log'] = []

    log_action(
        phase='diagnose',
        column='price',
        issue='Column has disguised nulls',
        decision='Replace with NaN',
        rows_affected=5,
        method='replace_disguised_nulls',
        details={'values': ['na', '?']}
    )

    assert len(state['audit_log']) == 1
    entry = state['audit_log'][0]
    assert entry['phase'] == 'diagnose'
    assert entry['column'] == 'price'
    assert entry['rows_affected'] == 5
    assert entry['method'] == 'replace_disguised_nulls'
    assert 'timestamp' in entry
    assert entry['details'] == {'values': ['na', '?']}
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_audit.py -v`
Expected: FAIL — `utils.audit` does not exist yet.

- [ ] **Step 6: Create `utils/audit.py`**

```python
import streamlit as st
import pandas as pd
from datetime import datetime

MAX_HISTORY = 5
UNDO_SIZE_LIMIT_MB = 200


def estimate_df_memory_mb(df: pd.DataFrame) -> float:
    return df.memory_usage(deep=True).sum() / (1024 ** 2)


def save_snapshot(df: pd.DataFrame):
    """Save df copy to history for undo. Skips if undo is disabled."""
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

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_audit.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 8: Create minimal `app.py` skeleton with routing**

```python
import streamlit as st
from utils.state import init_session_state

st.set_page_config(page_title="CleanSlate", page_icon="🧹", layout="wide")

init_session_state()


def show_upload():
    st.title("CleanSlate")
    st.caption("Understand your data. Clean it together.")
    st.info("Upload phase — to be implemented.")


def show_portrait():
    st.info("Data Portrait — to be implemented.")


def show_diagnose():
    st.info("Column Contracts — to be implemented.")


def show_nulls():
    st.info("Disguised Nulls — to be implemented.")


def show_zeros():
    st.info("Zero Values — to be implemented.")


def show_missing_bulk():
    st.info("Missing Values: Bulk — to be implemented.")


def show_missing_columns():
    st.info("Missing Values: Column-by-Column — to be implemented.")


def show_type_conversion():
    st.info("Type Conversion — to be implemented.")


def show_duplicates():
    st.info("Duplicates — to be implemented.")


def show_completion():
    st.info("Completion — to be implemented.")


# Routing
routes = {
    'upload': show_upload,
    'portrait': show_portrait,
    'diagnose': show_diagnose,
    'nulls': show_nulls,
    'zeros': show_zeros,
    'missing_bulk': show_missing_bulk,
    'missing_columns': show_missing_columns,
    'type_convert': show_type_conversion,
    'duplicates': show_duplicates,
    'done': show_completion,
}

routes[st.session_state.stage]()
```

- [ ] **Step 9: Verify the app runs**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && streamlit run app.py --server.headless true &` then check it loads at `http://localhost:8501`. Kill the process after verification.

- [ ] **Step 10: Commit**

```bash
git add requirements.txt utils/ tests/ app.py
git commit -m "feat: project scaffolding with state, audit, and routing skeleton"
```

---

## Task 2: Scanner Module (Detection Logic)

**Files:**
- Create: `utils/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing tests for `scanner.py`**

Create `tests/test_scanner.py`:

```python
import pandas as pd
import numpy as np
import pytest
from utils.scanner import (
    is_likely_id_column,
    detect_column_type,
    find_disguised_nulls,
    find_zero_columns,
    describe_numeric_plainly,
    get_high_missingness_rows,
    get_fully_empty_columns,
    KNOWN_NULL_STRINGS,
)


# --- is_likely_id_column ---

def test_id_column_with_underscore():
    assert is_likely_id_column('customer_id') is True

def test_id_column_with_space():
    assert is_likely_id_column('order number') is True

def test_id_column_postcode():
    assert is_likely_id_column('postcode') is True

def test_non_id_column():
    assert is_likely_id_column('price') is False

def test_non_id_column_age():
    assert is_likely_id_column('age') is False


# --- detect_column_type ---

def test_detect_empty_column():
    s = pd.Series([None, None, None])
    assert detect_column_type(s) == 'empty'

def test_detect_identifier_by_name():
    s = pd.Series([101, 102, 103])
    assert detect_column_type(s, 'customer_id') == 'identifier'

def test_detect_boolean():
    s = pd.Series(['Yes', 'No', 'Yes', 'No'])
    assert detect_column_type(s) == 'boolean'

def test_detect_boolean_01():
    s = pd.Series([0, 1, 1, 0])
    assert detect_column_type(s) == 'boolean'

def test_detect_continuous_numeric():
    s = pd.Series(range(100))
    assert detect_column_type(s) == 'continuous_numeric'

def test_detect_categorical_numeric():
    s = pd.Series([1, 2, 3, 1, 2, 3, 1, 2])
    assert detect_column_type(s) == 'categorical_numeric'

def test_detect_categorical_text():
    s = pd.Series(['A', 'B', 'C', 'A', 'B', 'C'])
    assert detect_column_type(s) == 'categorical_text'

def test_detect_free_text():
    s = pd.Series([f"sentence number {i}" for i in range(50)])
    assert detect_column_type(s) == 'free_text'

def test_detect_datetime_object():
    s = pd.Series(['2023-01-01', '2023-02-01', '2023-03-01'] * 20)
    assert detect_column_type(s) == 'datetime'

def test_detect_datetime_native():
    s = pd.to_datetime(pd.Series(['2023-01-01', '2023-02-01', '2023-03-01']))
    assert detect_column_type(s) == 'datetime'

def test_detect_numeric_from_object_strings():
    # Strings that are really numbers
    s = pd.Series(['1.5', '2.3', '3.7', '4.1', '5.9'] * 20)
    result = detect_column_type(s)
    assert result in ('continuous_numeric', 'categorical_numeric')


# --- find_disguised_nulls ---

def test_find_disguised_nulls_basic():
    df = pd.DataFrame({
        'a': ['hello', 'na', 'world', '?', 'good'],
        'b': [1, 2, 3, 4, 5],
    })
    result = find_disguised_nulls(df)
    assert 'a' in result
    assert 'na' in result['a']
    assert '?' in result['a']
    assert 'b' not in result  # numeric column skipped

def test_find_disguised_nulls_case_insensitive():
    df = pd.DataFrame({'a': ['N/A', 'None', 'valid']})
    result = find_disguised_nulls(df)
    assert 'a' in result
    assert 'N/A' in result['a']  # preserves original casing
    assert 'None' in result['a']

def test_find_disguised_nulls_spaces():
    df = pd.DataFrame({'a': ['hello', ' ', '  ', 'world']})
    result = find_disguised_nulls(df)
    assert 'a' in result
    assert ' ' in result['a']
    assert '  ' in result['a']

def test_find_disguised_nulls_clean():
    df = pd.DataFrame({'a': ['hello', 'world', 'foo']})
    result = find_disguised_nulls(df)
    assert result == {}


# --- find_zero_columns ---

def test_find_zero_columns_basic():
    df = pd.DataFrame({
        'price': [10, 0, 20, 30],
        'flag': [0, 1, 1, 0],  # boolean-like, should be excluded
        'count': [5, 6, 7, 8],
    })
    result = find_zero_columns(df)
    assert 'price' in result
    assert 'flag' not in result
    assert 'count' not in result

def test_find_zero_columns_no_zeros():
    df = pd.DataFrame({'a': [1, 2, 3]})
    assert find_zero_columns(df) == []


# --- describe_numeric_plainly ---

def test_describe_numeric_skewed():
    # Right-skewed data
    s = pd.Series([1, 1, 1, 1, 1, 1, 1, 1, 100, 200])
    df = pd.DataFrame({'income': s})
    notes = describe_numeric_plainly(df)
    skew_notes = [n for n in notes if 'skewed' in n]
    assert len(skew_notes) > 0

def test_describe_numeric_zeros_noted():
    df = pd.DataFrame({'val': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]})
    notes = describe_numeric_plainly(df)
    zero_notes = [n for n in notes if 'zero' in n.lower()]
    assert len(zero_notes) > 0


# --- get_high_missingness_rows ---

def test_high_missingness_default_threshold():
    df = pd.DataFrame({
        'a': [1, None, None, 4],
        'b': [None, None, None, 8],
        'c': [None, None, None, 12],
    })
    # Row 1: 2/3 missing = 67%. Row 2: 3/3 = 100%. Row 0: 1/3 = 33%.
    result = get_high_missingness_rows(df, 0.3)
    assert 0 in result
    assert 1 in result
    assert 2 in result
    assert 3 not in result

def test_high_missingness_custom_threshold():
    df = pd.DataFrame({
        'a': [1, None, None],
        'b': [2, None, None],
        'c': [3, 4, None],
    })
    # Row 1: 1/3 = 33%. Row 2: 2/3 = 67%.
    # With threshold 0.5, only row 2 qualifies
    result = get_high_missingness_rows(df, 0.5)
    assert 2 in result
    assert 1 not in result


# --- get_fully_empty_columns ---

def test_fully_empty_columns():
    df = pd.DataFrame({
        'a': [1, 2, 3],
        'b': [None, None, None],
        'c': [None, None, None],
    })
    result = get_fully_empty_columns(df)
    assert 'b' in result
    assert 'c' in result
    assert 'a' not in result

def test_no_empty_columns():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    assert get_fully_empty_columns(df) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_scanner.py -v`
Expected: FAIL — `utils.scanner` does not exist yet.

- [ ] **Step 3: Create `utils/scanner.py`**

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

    if len(non_null) == 0:
        return 'empty'

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
            if parse_rate >= 0.9:
                return 'datetime'
        except (ValueError, TypeError):
            pass

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
                    found.append(val)
            if found:
                results[col] = found
    return results


def find_zero_columns(df: pd.DataFrame) -> list:
    """
    Numeric columns containing zeros, EXCLUDING columns that look like
    boolean/flag (only values are 0 and 1).
    """
    zero_cols = []
    for col in df.select_dtypes(include=['number']).columns:
        unique_vals = set(df[col].dropna().unique())
        if 0 in unique_vals or 0.0 in unique_vals:
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
        if s.nunique() < 3:
            continue

        mean = s.mean()
        median = s.median()
        std = s.std()

        if median != 0 and abs(mean - median) / abs(median) > 0.5:
            direction = 'right' if mean > median else 'left'
            notes.append(
                f"\u2139\ufe0f **{col}** appears {direction}-skewed "
                f"(mean {mean:.2f} vs median {median:.2f}). "
                f"Median may be more reliable for imputation."
            )

        if mean != 0 and std / abs(mean) > 1.0:
            notes.append(f"\u2139\ufe0f **{col}** has high relative variability.")

        if (df[col] == 0).any():
            zero_count = (df[col] == 0).sum()
            notes.append(
                f"\u26a0\ufe0f **{col}** contains {zero_count} zero values "
                f"\u2014 may need review in Step 4."
            )

    return notes


def get_high_missingness_rows(df: pd.DataFrame, threshold: float = 0.3) -> pd.Index:
    """Returns index of rows where >= threshold fraction of columns are missing."""
    row_missing_pct = df.isna().sum(axis=1) / len(df.columns)
    return df.index[row_missing_pct >= threshold]


def get_fully_empty_columns(df: pd.DataFrame) -> list:
    """Columns that are 100% NaN."""
    return [col for col in df.columns if df[col].isna().all()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_scanner.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add utils/scanner.py tests/test_scanner.py
git commit -m "feat: scanner module with detection logic and tests"
```

---

## Task 3: Cleaner Module (All Mutation Functions)

**Files:**
- Create: `utils/cleaner.py`
- Create: `tests/test_cleaner.py`

- [ ] **Step 1: Write failing tests for `cleaner.py`**

Create `tests/test_cleaner.py`:

```python
import pandas as pd
import numpy as np
import pytest
from utils.cleaner import (
    replace_disguised_nulls_in_column,
    replace_zeros_with_nan,
    drop_rows_by_index,
    drop_column,
    impute_mean,
    impute_median,
    impute_mode,
    impute_group_median,
    impute_custom,
    impute_marker,
    impute_date,
    apply_type_conversion,
    remove_duplicates,
)


# --- replace_disguised_nulls_in_column ---

def test_replace_disguised_nulls():
    df = pd.DataFrame({'a': ['hello', 'na', 'N/A', 'world', '?']})
    new_df, affected, details = replace_disguised_nulls_in_column(df, 'a', ['na', 'N/A', '?'])
    assert affected == 3
    assert new_df['a'].isna().sum() == 3
    assert new_df['a'].iloc[0] == 'hello'
    assert new_df['a'].iloc[3] == 'world'

def test_replace_disguised_nulls_no_match():
    df = pd.DataFrame({'a': ['hello', 'world']})
    new_df, affected, details = replace_disguised_nulls_in_column(df, 'a', ['na'])
    assert affected == 0


# --- replace_zeros_with_nan ---

def test_replace_zeros():
    df = pd.DataFrame({'a': [0, 1, 2, 0, 3]})
    new_df, affected, details = replace_zeros_with_nan(df, 'a')
    assert affected == 2
    assert new_df['a'].isna().sum() == 2
    assert new_df['a'].iloc[1] == 1

def test_replace_zeros_no_zeros():
    df = pd.DataFrame({'a': [1, 2, 3]})
    new_df, affected, details = replace_zeros_with_nan(df, 'a')
    assert affected == 0


# --- drop_rows_by_index ---

def test_drop_rows_by_index():
    df = pd.DataFrame({'a': [1, 2, 3, 4, 5]})
    new_df, affected, details = drop_rows_by_index(df, pd.Index([1, 3]))
    assert affected == 2
    assert len(new_df) == 3
    assert list(new_df['a']) == [1, 3, 5]


# --- drop_column ---

def test_drop_column():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4], 'c': [5, 6]})
    new_df, affected, details = drop_column(df, 'b')
    assert 'b' not in new_df.columns
    assert list(new_df.columns) == ['a', 'c']


# --- impute_mean ---

def test_impute_mean():
    df = pd.DataFrame({'a': [10.0, np.nan, 20.0, np.nan, 30.0]})
    new_df, affected, details = impute_mean(df, 'a')
    assert affected == 2
    assert new_df['a'].isna().sum() == 0
    assert new_df['a'].iloc[1] == 20.0  # mean of 10, 20, 30


# --- impute_median ---

def test_impute_median():
    df = pd.DataFrame({'a': [10.0, np.nan, 30.0, np.nan, 50.0]})
    new_df, affected, details = impute_median(df, 'a')
    assert affected == 2
    assert new_df['a'].iloc[1] == 30.0  # median of 10, 30, 50


# --- impute_mode ---

def test_impute_mode():
    df = pd.DataFrame({'a': ['cat', 'dog', 'cat', np.nan, 'cat']})
    new_df, affected, details = impute_mode(df, 'a')
    assert affected == 1
    assert new_df['a'].iloc[3] == 'cat'


# --- impute_group_median ---

def test_impute_group_median_basic():
    df = pd.DataFrame({
        'region': ['A', 'A', 'A', 'B', 'B', 'B'],
        'value': [10.0, np.nan, 20.0, 30.0, np.nan, 40.0],
    })
    new_df, affected, details = impute_group_median(df, 'value', ['region'])
    assert affected == 2
    assert new_df['value'].isna().sum() == 0
    # Group A median: 15.0, Group B median: 35.0
    assert new_df['value'].iloc[1] == 15.0
    assert new_df['value'].iloc[4] == 35.0
    assert details['group_fills'] == 2
    assert details['fallback_fills'] == 0

def test_impute_group_median_with_nan_in_group_col():
    """NaN in grouping column should form its own group via sentinel, not be silently dropped."""
    df = pd.DataFrame({
        'region': ['A', 'A', np.nan, np.nan],
        'value': [10.0, np.nan, 20.0, np.nan],
    })
    new_df, affected, details = impute_group_median(df, 'value', ['region'])
    assert new_df['value'].isna().sum() == 0
    # Row 1: group A median = 10.0
    assert new_df['value'].iloc[1] == 10.0
    # Row 3: group '__MISSING__' median = 20.0
    assert new_df['value'].iloc[3] == 20.0

def test_impute_group_median_fallback():
    """Groups with zero non-null values should fall back to global median."""
    df = pd.DataFrame({
        'region': ['A', 'A', 'B', 'B'],
        'value': [10.0, 20.0, np.nan, np.nan],
    })
    new_df, affected, details = impute_group_median(df, 'value', ['region'])
    assert new_df['value'].isna().sum() == 0
    # Group B has no non-null values, fallback to global median (15.0)
    assert new_df['value'].iloc[2] == 15.0
    assert new_df['value'].iloc[3] == 15.0
    assert details['fallback_fills'] == 2


# --- impute_custom ---

def test_impute_custom():
    df = pd.DataFrame({'a': [1.0, np.nan, 3.0]})
    new_df, affected, details = impute_custom(df, 'a', 99)
    assert affected == 1
    assert new_df['a'].iloc[1] == 99


# --- impute_marker ---

def test_impute_marker():
    df = pd.DataFrame({'a': ['hello', np.nan, 'world']})
    new_df, affected, details = impute_marker(df, 'a', 'Unknown')
    assert affected == 1
    assert new_df['a'].iloc[1] == 'Unknown'


# --- impute_date ---

def test_impute_date_most_recent():
    df = pd.DataFrame({'d': pd.to_datetime(['2023-01-01', None, '2023-06-15', '2023-12-31'])})
    new_df, affected, details = impute_date(df, 'd', 'most_recent')
    assert affected == 1
    assert new_df['d'].iloc[1] == pd.Timestamp('2023-12-31')

def test_impute_date_oldest():
    df = pd.DataFrame({'d': pd.to_datetime(['2023-01-01', None, '2023-12-31'])})
    new_df, affected, details = impute_date(df, 'd', 'oldest')
    assert affected == 1
    assert new_df['d'].iloc[1] == pd.Timestamp('2023-01-01')

def test_impute_date_median():
    df = pd.DataFrame({'d': pd.to_datetime(['2023-01-01', None, '2023-06-01', '2023-12-31'])})
    new_df, affected, details = impute_date(df, 'd', 'median')
    assert affected == 1
    # Median of 3 dates


# --- apply_type_conversion ---

def test_apply_type_conversion_to_numeric():
    df = pd.DataFrame({'a': ['1.5', '2.3', '3.7', 'bad']})
    new_df, affected, details = apply_type_conversion(df, 'a', 'Continuous Number')
    assert pd.api.types.is_numeric_dtype(new_df['a'])
    assert new_df['a'].isna().sum() == 1  # 'bad' becomes NaN
    assert details['coercion_losses'] == 1

def test_apply_type_conversion_to_datetime():
    df = pd.DataFrame({'a': ['2023-01-01', '2023-02-15', '2023-03-20']})
    new_df, affected, details = apply_type_conversion(df, 'a', 'Date / Time')
    assert pd.api.types.is_datetime64_any_dtype(new_df['a'])

def test_apply_type_conversion_to_category():
    df = pd.DataFrame({'a': ['cat', 'dog', 'cat', 'bird']})
    new_df, affected, details = apply_type_conversion(df, 'a', 'Category')
    assert new_df['a'].dtype.name == 'category'

def test_apply_type_conversion_to_boolean():
    df = pd.DataFrame({'a': ['True', 'False', 'True']})
    new_df, affected, details = apply_type_conversion(df, 'a', 'Boolean')
    assert new_df['a'].dtype == bool

def test_apply_type_conversion_to_string():
    df = pd.DataFrame({'a': [1, 2, 3]})
    new_df, affected, details = apply_type_conversion(df, 'a', 'Text')
    assert new_df['a'].dtype == 'object'

def test_apply_type_conversion_id():
    df = pd.DataFrame({'a': [1, 2, 3]})
    new_df, affected, details = apply_type_conversion(df, 'a', 'ID / Identifier')
    assert new_df['a'].dtype == 'object'


# --- remove_duplicates ---

def test_remove_duplicates_keep_first():
    df = pd.DataFrame({'a': [1, 2, 1, 3, 2], 'b': [10, 20, 10, 30, 20]})
    new_df, affected, details = remove_duplicates(df, keep='first')
    assert affected == 2
    assert len(new_df) == 3

def test_remove_duplicates_keep_last():
    df = pd.DataFrame({'a': [1, 2, 1, 3, 2], 'b': [10, 20, 10, 30, 20]})
    new_df, affected, details = remove_duplicates(df, keep='last')
    assert affected == 2
    assert len(new_df) == 3

def test_remove_duplicates_no_dupes():
    df = pd.DataFrame({'a': [1, 2, 3]})
    new_df, affected, details = remove_duplicates(df)
    assert affected == 0
    assert len(new_df) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_cleaner.py -v`
Expected: FAIL — `utils.cleaner` does not exist yet.

- [ ] **Step 3: Create `utils/cleaner.py`**

```python
import pandas as pd
import numpy as np


def replace_disguised_nulls_in_column(df: pd.DataFrame, col: str,
                                       suspicious_values: list) -> tuple:
    """Replace suspicious values with NaN in a single column."""
    new_df = df.copy()
    mask = new_df[col].isin(suspicious_values)
    affected = int(mask.sum())
    new_df.loc[mask, col] = np.nan
    return new_df, affected, {'values_replaced': suspicious_values}


def replace_zeros_with_nan(df: pd.DataFrame, col: str) -> tuple:
    """Replace zeros with NaN in a single column."""
    new_df = df.copy()
    mask = new_df[col] == 0
    affected = int(mask.sum())
    new_df.loc[mask, col] = np.nan
    return new_df, affected, {}


def drop_rows_by_index(df: pd.DataFrame, index: pd.Index) -> tuple:
    """Drop rows by index."""
    new_df = df.drop(index=index).reset_index(drop=True)
    affected = len(index)
    return new_df, affected, {}


def drop_column(df: pd.DataFrame, col: str) -> tuple:
    """Drop a single column."""
    new_df = df.drop(columns=[col])
    affected = len(df)
    return new_df, affected, {'column_dropped': col}


def impute_mean(df: pd.DataFrame, col: str) -> tuple:
    """Fill NaN with column mean."""
    new_df = df.copy()
    mean_val = new_df[col].mean()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(mean_val)
    return new_df, affected, {'value': round(float(mean_val), 4)}


def impute_median(df: pd.DataFrame, col: str) -> tuple:
    """Fill NaN with column median."""
    new_df = df.copy()
    median_val = new_df[col].median()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(median_val)
    return new_df, affected, {'value': round(float(median_val), 4)}


def impute_mode(df: pd.DataFrame, col: str) -> tuple:
    """Fill NaN with column mode (most frequent value)."""
    new_df = df.copy()
    mode_val = new_df[col].mode().iloc[0]
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(mode_val)
    return new_df, affected, {'value': str(mode_val)}


def impute_group_median(df: pd.DataFrame, col: str,
                         group_by_cols: list) -> tuple:
    """
    Fill NaN with group median. NaN in grouping columns is handled by
    temporarily filling with '__MISSING__' sentinel. Groups with zero
    non-null values in the target column fall back to global median.
    """
    new_df = df.copy()
    missing_before = new_df[col].isna().sum()

    # Fill NaN in grouping columns with sentinel
    temp_group_cols = []
    for gc in group_by_cols:
        temp_col = f'__temp_group_{gc}'
        new_df[temp_col] = new_df[gc].fillna('__MISSING__').astype(str)
        temp_group_cols.append(temp_col)

    # Compute group medians
    group_medians = new_df.groupby(temp_group_cols)[col].transform('median')
    global_median = new_df[col].median()

    # Fill with group median first
    mask = new_df[col].isna()
    new_df.loc[mask, col] = group_medians[mask]

    # Count group fills
    still_missing = new_df[col].isna().sum()
    group_fills = int(missing_before - still_missing)

    # Fallback to global median for remaining NaN
    fallback_mask = new_df[col].isna()
    fallback_fills = int(fallback_mask.sum())
    new_df[col] = new_df[col].fillna(global_median)

    # Clean up temp columns
    new_df.drop(columns=temp_group_cols, inplace=True)

    # Count small groups (fewer than 3 non-null values)
    group_sizes = df.groupby(
        [df[gc].fillna('__MISSING__').astype(str) for gc in group_by_cols]
    )[col].apply(lambda x: x.notna().sum())
    small_groups = int((group_sizes < 3).sum())

    affected = group_fills + fallback_fills
    details = {
        'group_by': group_by_cols,
        'group_fills': group_fills,
        'fallback_fills': fallback_fills,
        'small_groups': small_groups,
        'global_median': round(float(global_median), 4),
    }
    return new_df, affected, details


def impute_custom(df: pd.DataFrame, col: str, value) -> tuple:
    """Fill NaN with a user-specified constant."""
    new_df = df.copy()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(value)
    return new_df, affected, {'value': value}


def impute_marker(df: pd.DataFrame, col: str, marker: str = 'Unknown') -> tuple:
    """Fill NaN with a marker string."""
    new_df = df.copy()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(marker)
    return new_df, affected, {'marker': marker}


def impute_date(df: pd.DataFrame, col: str, strategy: str,
                custom_date=None) -> tuple:
    """
    Fill NaN in a datetime column.
    strategy: 'most_recent', 'oldest', 'median', 'custom'
    """
    new_df = df.copy()
    mask = new_df[col].isna()
    affected = int(mask.sum())

    non_null_dates = new_df[col].dropna()

    if strategy == 'most_recent':
        fill_val = non_null_dates.max()
    elif strategy == 'oldest':
        fill_val = non_null_dates.min()
    elif strategy == 'median':
        # Convert to numeric for median, then back to timestamp
        numeric_dates = non_null_dates.astype(np.int64)
        median_ns = int(numeric_dates.median())
        fill_val = pd.Timestamp(median_ns)
    elif strategy == 'custom':
        fill_val = pd.Timestamp(custom_date)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    new_df.loc[mask, col] = fill_val
    return new_df, affected, {'strategy': strategy, 'fill_value': str(fill_val)}


def apply_type_conversion(df: pd.DataFrame, col: str,
                           target_type: str) -> tuple:
    """
    Convert column to intended type. Returns (new_df, rows_affected, details).
    For dates: infers format from first 100 non-null values for performance.
    """
    new_df = df.copy()
    original_non_null = new_df[col].notna().sum()

    if target_type == 'Continuous Number':
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
    elif target_type == 'Category':
        new_df[col] = new_df[col].astype('category')
    elif target_type == 'Date / Time':
        # Infer format from sample for performance
        sample = new_df[col].dropna().head(100)
        inferred_format = _infer_date_format(sample)
        if inferred_format:
            new_df[col] = pd.to_datetime(new_df[col], format=inferred_format, errors='coerce')
        else:
            new_df[col] = pd.to_datetime(new_df[col], errors='coerce')
    elif target_type == 'Boolean':
        bool_map = {
            'true': True, 'false': False,
            'yes': True, 'no': False,
            '1': True, '0': False,
            'y': True, 'n': False,
            't': True, 'f': False,
            1: True, 0: False,
        }
        new_df[col] = new_df[col].map(
            lambda x: bool_map.get(str(x).strip().lower(), x) if pd.notna(x) else x
        ).astype(bool)
    elif target_type in ('Text', 'ID / Identifier'):
        new_df[col] = new_df[col].astype(str).replace('nan', np.nan)
    else:
        return new_df, 0, {'target_type': target_type, 'coercion_losses': 0}

    new_non_null = new_df[col].notna().sum()
    coercion_losses = int(original_non_null - new_non_null)
    affected = len(new_df)
    return new_df, affected, {
        'target_type': target_type,
        'coercion_losses': coercion_losses,
    }


def _infer_date_format(sample: pd.Series) -> str | None:
    """Try common date formats on a sample and return the first that works for >= 90%."""
    common_formats = [
        '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
        '%Y-%m-%d %H:%M:%S', '%d-%m-%Y', '%m-%d-%Y',
        '%Y/%m/%d', '%d.%m.%Y', '%m.%d.%Y',
    ]
    for fmt in common_formats:
        try:
            parsed = pd.to_datetime(sample, format=fmt, errors='coerce')
            if parsed.notna().sum() / len(sample) >= 0.9:
                return fmt
        except (ValueError, TypeError):
            continue
    return None


def remove_duplicates(df: pd.DataFrame, keep: str = 'first') -> tuple:
    """Remove duplicate rows."""
    dup_count = int(df.duplicated(keep=keep).sum())
    new_df = df.drop_duplicates(keep=keep).reset_index(drop=True)
    return new_df, dup_count, {'keep': keep}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_cleaner.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/ -v`
Expected: All tests across all modules PASS.

- [ ] **Step 6: Commit**

```bash
git add utils/cleaner.py tests/test_cleaner.py
git commit -m "feat: cleaner module with all mutation functions and tests"
```

---

## Task 4: Recipe Module (Reproducibility Code Generation)

**Files:**
- Create: `utils/recipe.py`
- Create: `tests/test_recipe.py`

- [ ] **Step 1: Write failing tests for `recipe.py`**

Create `tests/test_recipe.py`:

```python
import pytest
from utils.recipe import generate_recipe


def test_recipe_empty_log():
    code = generate_recipe([], 'data.csv')
    assert 'import pandas as pd' in code
    assert 'data.csv' in code


def test_recipe_disguised_nulls():
    log = [{
        'timestamp': '2026-04-17T10:00:00',
        'phase': 'disguised_nulls',
        'column': 'color',
        'issue': 'Disguised nulls found',
        'decision': 'Replace with NaN',
        'rows_affected': 5,
        'method': 'replace_disguised_nulls',
        'details': {'values_replaced': ['na', '?']},
    }]
    code = generate_recipe(log, 'data.csv')
    assert "color" in code
    assert "replace" in code.lower() or "isin" in code.lower()


def test_recipe_zero_as_missing():
    log = [{
        'timestamp': '2026-04-17T10:00:00',
        'phase': 'zeros',
        'column': 'y',
        'issue': 'Zeros treated as missing',
        'decision': 'Replace zeros with NaN',
        'rows_affected': 8,
        'method': 'zero_as_missing',
        'details': {},
    }]
    code = generate_recipe(log, 'data.csv')
    assert "y" in code
    assert "0" in code


def test_recipe_drop_empty_column():
    log = [{
        'timestamp': '2026-04-17T10:00:00',
        'phase': 'missing',
        'column': 'empty_col',
        'issue': 'Column 100% empty',
        'decision': 'Drop column',
        'rows_affected': 100,
        'method': 'drop_empty_column',
        'details': {'column_dropped': 'empty_col'},
    }]
    code = generate_recipe(log, 'data.csv')
    assert "drop" in code.lower()
    assert "empty_col" in code


def test_recipe_impute_mean():
    log = [{
        'timestamp': '2026-04-17T10:00:00',
        'phase': 'missing',
        'column': 'price',
        'issue': 'Missing values',
        'decision': 'Fill with mean',
        'rows_affected': 3,
        'method': 'impute_mean',
        'details': {'value': 42.5},
    }]
    code = generate_recipe(log, 'data.csv')
    assert "price" in code
    assert "fillna" in code or "42.5" in code


def test_recipe_impute_group_median():
    log = [
        {
            'timestamp': '2026-04-17T10:00:00',
            'phase': 'missing',
            'column': 'value',
            'issue': 'Missing values',
            'decision': 'Fill with group median',
            'rows_affected': 5,
            'method': 'impute_group_median',
            'details': {'group_by': ['region'], 'group_fills': 4, 'fallback_fills': 1, 'global_median': 15.0},
        },
        {
            'timestamp': '2026-04-17T10:00:01',
            'phase': 'missing',
            'column': 'value',
            'issue': 'Group median fallback',
            'decision': 'Fill remaining with global median',
            'rows_affected': 1,
            'method': 'impute_group_median_fallback',
            'details': {'global_median': 15.0},
        },
    ]
    code = generate_recipe(log, 'data.csv')
    assert "region" in code
    assert "groupby" in code.lower() or "transform" in code.lower()


def test_recipe_remove_duplicates():
    log = [{
        'timestamp': '2026-04-17T10:00:00',
        'phase': 'duplicates',
        'column': '*',
        'issue': 'Duplicate rows',
        'decision': 'Remove duplicates, keep first',
        'rows_affected': 10,
        'method': 'remove_duplicates_keep_first',
        'details': {'keep': 'first'},
    }]
    code = generate_recipe(log, 'data.csv')
    assert "drop_duplicates" in code
    assert "first" in code


def test_recipe_type_conversion():
    log = [{
        'timestamp': '2026-04-17T10:00:00',
        'phase': 'type_convert',
        'column': 'price',
        'issue': 'Type conversion',
        'decision': 'Convert to numeric',
        'rows_affected': 100,
        'method': 'type_conversion',
        'details': {'target_type': 'Continuous Number', 'coercion_losses': 2},
    }]
    code = generate_recipe(log, 'data.csv')
    assert "price" in code
    assert "numeric" in code.lower() or "to_numeric" in code


def test_recipe_skip_and_keep_actions():
    """Actions like skip_column, zero_kept_valid, keep_duplicates should appear as comments only."""
    log = [
        {
            'timestamp': '2026-04-17T10:00:00',
            'phase': 'zeros', 'column': 'x', 'issue': '', 'decision': 'Kept as valid',
            'rows_affected': 0, 'method': 'zero_kept_valid', 'details': {},
        },
        {
            'timestamp': '2026-04-17T10:01:00',
            'phase': 'missing', 'column': 'y', 'issue': '', 'decision': 'Skipped',
            'rows_affected': 0, 'method': 'skip_column', 'details': {},
        },
    ]
    code = generate_recipe(log, 'data.csv')
    assert "#" in code  # Should appear as comments
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_recipe.py -v`
Expected: FAIL — `utils.recipe` does not exist yet.

- [ ] **Step 3: Create `utils/recipe.py`**

```python
def generate_recipe(audit_log: list, original_filename: str) -> str:
    """
    Generate a runnable Python script from the audit log that reproduces
    every cleaning step using pandas.
    """
    lines = [
        "import pandas as pd",
        "import numpy as np",
        "",
        f"# Reproducibility recipe generated by CleanSlate",
        f"# Original file: {original_filename}",
        "",
        f"df = pd.read_csv('{original_filename}')",
        "",
    ]

    # Methods that don't change data — emit as comments
    no_op_methods = {
        'type_confirmation', 'zero_kept_valid', 'skip_column',
        'keep_duplicates', 'type_conversion_skipped',
    }

    for entry in audit_log:
        method = entry['method']
        col = entry['column']
        details = entry.get('details', {})

        lines.append(f"# {entry.get('decision', method)} — {col}")

        if method in no_op_methods:
            lines.append(f"# (No data change)")
            lines.append("")
            continue

        if method == 'replace_disguised_nulls':
            values = details.get('values_replaced', [])
            lines.append(f"df['{col}'] = df['{col}'].replace({values}, np.nan)")

        elif method == 'zero_as_missing':
            lines.append(f"df.loc[df['{col}'] == 0, '{col}'] = np.nan")

        elif method == 'drop_empty_column':
            lines.append(f"df = df.drop(columns=['{col}'])")

        elif method == 'drop_rows_high_missingness':
            threshold = details.get('threshold', 0.3)
            lines.append(f"row_missing_pct = df.isna().sum(axis=1) / len(df.columns)")
            lines.append(f"df = df[row_missing_pct < {threshold}].reset_index(drop=True)")

        elif method == 'drop_rows_column_missing':
            lines.append(f"df = df.dropna(subset=['{col}']).reset_index(drop=True)")

        elif method == 'impute_mean':
            val = details.get('value')
            lines.append(f"df['{col}'] = df['{col}'].fillna({val})")

        elif method == 'impute_median':
            val = details.get('value')
            lines.append(f"df['{col}'] = df['{col}'].fillna({val})")

        elif method == 'impute_mode':
            val = details.get('value')
            lines.append(f"df['{col}'] = df['{col}'].fillna('{val}')")

        elif method == 'impute_group_median':
            group_cols = details.get('group_by', [])
            global_med = details.get('global_median')
            group_str = str(group_cols)
            lines.append(f"_group_med = df.groupby({group_str})['{col}'].transform('median')")
            lines.append(f"df['{col}'] = df['{col}'].fillna(_group_med)")
            lines.append(f"df['{col}'] = df['{col}'].fillna({global_med})  # fallback")

        elif method == 'impute_group_median_fallback':
            global_med = details.get('global_median')
            lines.append(f"df['{col}'] = df['{col}'].fillna({global_med})")

        elif method == 'impute_custom_value':
            val = details.get('value')
            if isinstance(val, str):
                lines.append(f"df['{col}'] = df['{col}'].fillna('{val}')")
            else:
                lines.append(f"df['{col}'] = df['{col}'].fillna({val})")

        elif method == 'impute_marker_unknown':
            marker = details.get('marker', 'Unknown')
            lines.append(f"df['{col}'] = df['{col}'].fillna('{marker}')")

        elif method in ('impute_most_recent_date', 'impute_oldest_date', 'impute_median_date'):
            fill_val = details.get('fill_value', '')
            lines.append(f"df['{col}'] = df['{col}'].fillna(pd.Timestamp('{fill_val}'))")

        elif method == 'type_conversion':
            target = details.get('target_type', '')
            if target == 'Continuous Number':
                lines.append(f"df['{col}'] = pd.to_numeric(df['{col}'], errors='coerce')")
            elif target == 'Date / Time':
                lines.append(f"df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce')")
            elif target == 'Category':
                lines.append(f"df['{col}'] = df['{col}'].astype('category')")
            elif target == 'Boolean':
                lines.append(f"df['{col}'] = df['{col}'].map({{'true': True, 'false': False, 'yes': True, 'no': False, '1': True, '0': False}}).astype(bool)")
            elif target in ('Text', 'ID / Identifier'):
                lines.append(f"df['{col}'] = df['{col}'].astype(str)")

        elif method == 'remove_duplicates_keep_first':
            lines.append(f"df = df.drop_duplicates(keep='first').reset_index(drop=True)")

        elif method == 'remove_duplicates_keep_last':
            lines.append(f"df = df.drop_duplicates(keep='last').reset_index(drop=True)")

        else:
            lines.append(f"# Unknown method: {method}")

        lines.append("")

    lines.append(f"# Save cleaned data")
    lines.append(f"df.to_csv('clean_{original_filename}', index=False)")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/test_recipe.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add utils/recipe.py tests/test_recipe.py
git commit -m "feat: recipe module for reproducibility code generation"
```

---

## Task 5: Phase 0 — Upload + File Loading

**Files:**
- Modify: `app.py` — implement `show_upload()` and `load_file()`

- [ ] **Step 1: Implement `load_file()` and `show_upload()` in `app.py`**

Add `load_file()` at the top of `app.py` (after imports):

```python
import pandas as pd
from utils.audit import estimate_df_memory_mb

def load_file(uploaded_file):
    """
    Loads CSV or Excel robustly.
    Encoding chain for CSV: utf-8-sig -> utf-8 -> cp1252 -> latin-1
    """
    name = uploaded_file.name.lower()
    if name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(uploaded_file)

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

Replace the `show_upload()` stub:

```python
def show_upload():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("CleanSlate")
        st.caption("Understand your data. Clean it together.")
        uploaded = st.file_uploader(
            "Upload your data file",
            type=['csv', 'xlsx', 'xls'],
            help="Your file stays on your machine. Nothing is sent anywhere."
        )
        if uploaded is not None:
            try:
                df = load_file(uploaded)
                st.session_state.original_df = df
                st.session_state.working_df = df.copy()
                st.session_state.filename = uploaded.name
                st.session_state.file_size_mb = estimate_df_memory_mb(df)
                st.session_state.undo_enabled = st.session_state.file_size_mb <= 200
                st.session_state.audit_log = []
                st.session_state.history = []
                if not st.session_state.undo_enabled:
                    st.info(
                        "Your file is large (over 200MB). Undo history is disabled "
                        "to preserve memory. All actions are still logged."
                    )
                st.session_state.stage = 'portrait'
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load file: {e}")
```

- [ ] **Step 2: Test manually in browser**

Run: `streamlit run app.py`
- Upload `Test Data_Aurora Gems.csv` — should load and advance to portrait stage (which shows the stub message).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 0 upload with robust CSV/Excel loading"
```

---

## Task 6: Sidebar

**Files:**
- Modify: `app.py` — add `render_sidebar()` function, call it after upload

- [ ] **Step 1: Add `render_sidebar()` to `app.py`**

Add this function and call it from the routing section (only when stage != 'upload'):

```python
def render_sidebar():
    """Sidebar with progress tracker, live stats, and mini audit log."""
    with st.sidebar:
        st.title("CleanSlate 🧹")

        # Progress tracker
        stages_display = [
            ('portrait', 'Data Portrait', 1),
            ('diagnose', 'Column Types', 2),
            ('nulls', 'Hidden Nulls', 3),
            ('zeros', 'Zero Values', 4),
            ('missing_bulk', 'Missing Values', 5),
            ('missing_columns', 'Missing Values', 5),
            ('type_convert', 'Type Conversion', 6),
            ('duplicates', 'Duplicates', 7),
            ('done', 'Done', 8),
        ]

        stage_order = {
            'upload': 0, 'portrait': 1, 'diagnose': 2, 'nulls': 3,
            'zeros': 4, 'missing_bulk': 5, 'missing_columns': 5,
            'type_convert': 6, 'duplicates': 7, 'done': 8,
        }

        current_order = stage_order.get(st.session_state.stage, 0)

        # Deduplicate display (missing_bulk and missing_columns both show as step 5)
        seen_steps = set()
        for stage_key, label, step_num in stages_display:
            if step_num in seen_steps:
                continue
            seen_steps.add(step_num)

            step_order = step_num
            if step_order < current_order:
                st.markdown(f"✅ Step {step_num}: {label}")
            elif step_order == current_order:
                st.markdown(f"👉 **Step {step_num}: {label}**")
            else:
                st.markdown(f"○ Step {step_num}: {label}")

        st.divider()

        # Live stats
        if st.session_state.working_df is not None:
            df = st.session_state.working_df
            st.markdown(f"📁 **File:** {st.session_state.filename}")
            st.markdown(f"📏 **Rows:** {len(df):,}")
            missing = int(df.isna().sum().sum())
            st.markdown(f"❓ **Missing cells:** {missing:,}")
            if st.session_state.undo_enabled:
                st.markdown("↩️ Undo: ✅ Enabled")
            else:
                st.markdown("↩️ Undo: ⚠️ Disabled (large file)")

        st.divider()

        # Mini audit log
        log = st.session_state.audit_log
        st.markdown(f"📋 **Audit Log:** {len(log)} actions")
        if log:
            for entry in log[-3:]:
                st.caption(f"• {entry['method']} → {entry['column']}")

        # Download partial audit log
        if log:
            import io
            audit_df = pd.DataFrame(log)
            csv_buf = io.StringIO()
            audit_df.to_csv(csv_buf, index=False)
            st.download_button(
                "⬇ Download audit log so far",
                csv_buf.getvalue(),
                file_name=f"partial_auditlog_{st.session_state.filename}.csv",
                mime="text/csv",
            )
```

Update the routing section at the bottom of `app.py`:

```python
# Routing
if st.session_state.stage != 'upload':
    render_sidebar()

routes = {
    'upload': show_upload,
    'portrait': show_portrait,
    'diagnose': show_diagnose,
    'nulls': show_nulls,
    'zeros': show_zeros,
    'missing_bulk': show_missing_bulk,
    'missing_columns': show_missing_columns,
    'type_convert': show_type_conversion,
    'duplicates': show_duplicates,
    'done': show_completion,
}

routes[st.session_state.stage]()
```

- [ ] **Step 2: Test manually in browser**

Run: `streamlit run app.py`
- Upload a file — sidebar should appear with progress tracker, live stats, and empty audit log.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: sidebar with progress tracker, live stats, and mini audit log"
```

---

## Task 7: Phase 1 — Data Portrait

**Files:**
- Modify: `app.py` — implement `show_portrait()`

- [ ] **Step 1: Implement `show_portrait()`**

Replace the `show_portrait()` stub:

```python
def show_portrait():
    df = st.session_state.working_df

    st.header("📊 Your Data Portrait")
    st.caption("Before we touch anything, let's understand what you're working with.")

    # Section A — The Basics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📁 File", st.session_state.filename)
    c2.metric("📏 Rows", f"{len(df):,}")
    c3.metric("📋 Columns", str(len(df.columns)))
    size_mb = st.session_state.file_size_mb
    size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{size_mb * 1024:.0f} KB"
    c4.metric("💾 Size", size_str)

    # Section B — First Look
    st.subheader("First 4 Rows")
    st.caption("A quick look at what your data contains.")
    st.dataframe(df.head(4), use_container_width=True)

    # Section C — Column Summary Table
    st.subheader("Column Summary")
    from utils.scanner import detect_column_type
    summary_rows = []
    for col in df.columns:
        detected = detect_column_type(df[col], col)
        non_null = int(df[col].notna().sum())
        null_count = int(df[col].isna().sum())
        null_pct = null_count / len(df) * 100 if len(df) > 0 else 0
        unique = int(df[col].nunique(dropna=True))
        samples = df[col].dropna().unique()[:3]
        sample_str = ", ".join(str(s) for s in samples)
        summary_rows.append({
            'Column': col,
            'Detected Type': detected,
            'Non-Null': f"{non_null:,}",
            'Nulls': f"{null_count:,}",
            'Null %': f"{null_pct:.1f}%",
            'Unique': f"{unique:,}",
            'Samples': sample_str,
        })

    summary_df = pd.DataFrame(summary_rows)

    def color_null_pct(val):
        pct = float(val.replace('%', ''))
        if pct == 0:
            return 'color: #2ecc71'
        elif pct <= 5:
            return 'color: #f5a623'
        else:
            return 'color: #e74c3c'

    styled = summary_df.style.applymap(color_null_pct, subset=['Null %'])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Section D — Statistical Summary
    numeric_df = df.describe(include='number')
    if not numeric_df.empty:
        st.subheader("Statistical Summary")
        st.dataframe(numeric_df.round(2).T, use_container_width=True)

        from utils.scanner import describe_numeric_plainly
        notes = describe_numeric_plainly(df)
        for note in notes:
            st.markdown(note)

    # Section E — Categorical Value Counts
    st.subheader("Categorical Value Counts")
    for col in df.columns:
        detected = detect_column_type(df[col], col)
        if detected in ('categorical_text', 'categorical_numeric'):
            with st.expander(f"{col} — {df[col].nunique(dropna=True)} unique values"):
                counts = df[col].value_counts().head(5)
                st.dataframe(counts.reset_index(), use_container_width=True, hide_index=True)

    # Section F — Health Snapshot
    st.subheader("Health Snapshot")
    from utils.scanner import find_disguised_nulls, find_zero_columns, get_fully_empty_columns

    total_missing = int(df.isna().sum().sum())
    if total_missing == 0:
        st.markdown("✅ **Missing Values:** None")
    else:
        st.markdown(f"⚠️ **Missing Values:** {total_missing:,} cells missing")

    disguised = find_disguised_nulls(df)
    if not disguised:
        st.markdown("✅ **Disguised Nulls:** None")
    else:
        st.markdown(f"⚠️ **Disguised Nulls:** Found in {len(disguised)} columns")

    zero_cols = find_zero_columns(df)
    if not zero_cols:
        st.markdown("✅ **Zero Values:** None in numeric columns")
    else:
        st.markdown(f"⚠️ **Zero Values:** {len(zero_cols)} columns have zeros")

    dup_count = int(df.duplicated().sum())
    if dup_count == 0:
        st.markdown("✅ **Duplicates:** None")
    else:
        st.markdown(f"⚠️ **Duplicates:** {dup_count:,} duplicate rows")

    empty_cols = get_fully_empty_columns(df)
    if not empty_cols:
        st.markdown("✅ **Fully Empty Columns:** None")
    else:
        st.markdown(f"⚠️ **Fully Empty Columns:** {len(empty_cols)} columns are 100% empty")

    # Navigation
    st.divider()
    if st.button("I've reviewed my data — start cleaning →", type="primary"):
        st.session_state.stage = 'diagnose'
        st.rerun()
```

- [ ] **Step 2: Test manually in browser**

Run: `streamlit run app.py`
- Upload `Test Data_Aurora Gems.csv` — should see all 6 sections of the Data Portrait.
- Verify colour coding on null percentages.
- Verify health snapshot shows disguised nulls and duplicates.
- Click "start cleaning" — should advance to diagnose stage.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 1 data portrait with stats, column summary, and health snapshot"
```

---

## Task 8: Phase 2 — Column Contracts

**Files:**
- Modify: `app.py` — implement `show_diagnose()`

- [ ] **Step 1: Implement `show_diagnose()`**

Replace the stub:

```python
def show_diagnose():
    df = st.session_state.working_df

    st.header("🔍 Step 2 of 7: Confirm Your Column Types")
    st.caption(
        "Before fixing anything, let's agree on what each column is supposed to contain. "
        "This guides every cleaning decision that follows."
    )
    st.info(
        "💡 Why does this matter? The type you confirm tells us which cleaning options "
        "make sense. You can't fill a date column with an average."
    )

    from utils.scanner import detect_column_type

    type_options = [
        'Continuous Number', 'Category', 'Date / Time',
        'Text', 'Boolean', 'ID / Identifier',
    ]

    # Map detected types to display options
    type_map = {
        'continuous_numeric': 'Continuous Number',
        'categorical_numeric': 'Category',
        'categorical_text': 'Category',
        'free_text': 'Text',
        'datetime': 'Date / Time',
        'boolean': 'Boolean',
        'identifier': 'ID / Identifier',
        'empty': 'Text',
    }

    selections = {}
    for col in df.columns:
        detected = detect_column_type(df[col], col)
        suggested = type_map.get(detected, 'Text')

        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{col}**")
            st.caption(f"Current dtype: `{df[col].dtype}`")
        with col2:
            st.caption(f"Suggested: {suggested}")
        with col3:
            default_idx = type_options.index(suggested) if suggested in type_options else 0
            selections[col] = st.selectbox(
                f"Type for {col}",
                type_options,
                index=default_idx,
                key=f"type_{col}",
                label_visibility="collapsed",
            )

    st.divider()

    if st.button("✅ Confirm All Column Types →", type="primary"):
        from utils.audit import log_action
        from utils.scanner import find_disguised_nulls, find_zero_columns

        # Store contracts (no mutations)
        contracts = {}
        for col in df.columns:
            detected = detect_column_type(df[col], col)
            contracts[col] = {
                'detected_type': type_map.get(detected, 'Text'),
                'intended_type': selections[col],
                'confirmed': True,
            }
            log_action(
                phase='diagnose',
                column=col,
                issue=f'Detected as {detected}',
                decision=f'Confirmed as {selections[col]}',
                rows_affected=0,
                method='type_confirmation',
                details={'from': type_map.get(detected, 'Text'), 'to': selections[col]},
            )

        st.session_state.column_contracts = contracts

        # Pre-compute for next phases
        st.session_state.disguised_nulls = find_disguised_nulls(df)
        st.session_state.zero_cols = find_zero_columns(df)

        st.session_state.stage = 'nulls'
        st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Upload file → advance to portrait → advance to column contracts.
- Verify all columns shown with suggested types.
- Change a type, confirm — should advance to nulls phase.
- Check sidebar audit log shows type_confirmation entries.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 2 column contracts (no mutations, contracts only)"
```

---

## Task 9: Phase 3 — Disguised Nulls

**Files:**
- Modify: `app.py` — implement `show_nulls()`

- [ ] **Step 1: Implement `show_nulls()`**

Replace the stub:

```python
def show_nulls():
    df = st.session_state.working_df
    disguised = st.session_state.disguised_nulls

    st.header("🔍 Step 3 of 7: Hidden Missing Values")

    if not disguised:
        st.success("✅ No hidden null values detected.")
        if st.button("Next →", type="primary"):
            st.session_state.stage = 'zeros'
            st.rerun()
        return

    st.caption(
        "We found values that look like missing data but aren't being read as null yet. "
        "We need to fix this before counting what's actually missing."
    )

    # Display table of suspicious values
    rows = []
    for col, values in disguised.items():
        for val in values:
            count = int((df[col] == val).sum())
            rows.append({'Column': col, 'Suspicious Value': repr(val), 'Count': count})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Show example rows
    st.subheader("Example rows with these values")
    all_suspicious = []
    for col, values in disguised.items():
        mask = df[col].isin(values)
        all_suspicious.append(mask)
    if all_suspicious:
        combined_mask = all_suspicious[0]
        for m in all_suspicious[1:]:
            combined_mask = combined_mask | m
        st.dataframe(df[combined_mask].head(3), use_container_width=True)

    # Options
    st.divider()
    choice = st.radio(
        "Treat all of these as missing values (NaN)?",
        ["✅ Yes — treat all as missing (Recommended)",
         "❌ No — they are valid text",
         "🔍 Decide per column"],
        index=0,
    )

    if st.button("Apply", type="primary"):
        from utils.audit import save_snapshot, log_action
        from utils.cleaner import replace_disguised_nulls_in_column

        if choice.startswith("✅"):
            save_snapshot(df)
            total_affected = 0
            for col, values in disguised.items():
                new_df, affected, details = replace_disguised_nulls_in_column(
                    st.session_state.working_df, col, values
                )
                st.session_state.working_df = new_df
                total_affected += affected
                log_action(
                    phase='disguised_nulls', column=col,
                    issue=f'Found disguised nulls: {values}',
                    decision='Replaced with NaN',
                    rows_affected=affected,
                    method='replace_disguised_nulls',
                    details={'values_replaced': values},
                )
            st.success(f"Done. {total_affected} values now correctly read as null.")
            st.session_state.stage = 'zeros'
            st.rerun()

        elif choice.startswith("❌"):
            st.session_state.stage = 'zeros'
            st.rerun()

        elif choice.startswith("🔍"):
            # Per-column mode
            st.session_state._nulls_per_column = True
            st.rerun()

    # Per-column mode
    if st.session_state.get('_nulls_per_column'):
        from utils.audit import save_snapshot, log_action
        from utils.cleaner import replace_disguised_nulls_in_column

        save_snapshot(df)
        for col, values in disguised.items():
            with st.container():
                st.markdown(f"**{col}** — found: {values}")
                col_choice = st.radio(
                    f"Replace in {col}?",
                    ["Yes — treat as missing", "No — keep as valid"],
                    key=f"null_choice_{col}",
                )

        if st.button("Confirm all per-column choices", key="confirm_per_col"):
            for col, values in disguised.items():
                col_choice = st.session_state.get(f"null_choice_{col}", "Yes — treat as missing")
                if col_choice.startswith("Yes"):
                    new_df, affected, details = replace_disguised_nulls_in_column(
                        st.session_state.working_df, col, values
                    )
                    st.session_state.working_df = new_df
                    log_action(
                        phase='disguised_nulls', column=col,
                        issue=f'Found disguised nulls: {values}',
                        decision='Replaced with NaN',
                        rows_affected=affected,
                        method='replace_disguised_nulls',
                        details={'values_replaced': values},
                    )
            st.session_state._nulls_per_column = False
            st.session_state.stage = 'zeros'
            st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Upload `Test Data_Aurora Gems.csv` → advance through to Phase 3.
- Verify disguised nulls are detected (`na`, ` `, etc. in cut, color, clarity).
- Test "Yes — treat all as missing" path.
- Verify sidebar audit log updates.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 3 disguised nulls detection and replacement"
```

---

## Task 10: Phase 4 — Zero Values

**Files:**
- Modify: `app.py` — implement `show_zeros()`

- [ ] **Step 1: Implement `show_zeros()`**

Replace the stub:

```python
def show_zeros():
    df = st.session_state.working_df
    zero_cols = st.session_state.zero_cols

    st.header("🔍 Step 4 of 7: Zero Values")

    if not zero_cols:
        st.success("✅ No zeros found in numeric columns (excluding boolean flags).")
        if st.button("Next →", type="primary"):
            st.session_state.stage = 'missing_bulk'
            st.rerun()
        return

    st.caption("Zeros can be legitimate or they can mean missing data recorded as zero. Only you know which.")

    # Initialize tracking
    if '_zero_col_idx' not in st.session_state:
        st.session_state._zero_col_idx = 0

    idx = st.session_state._zero_col_idx

    if idx >= len(zero_cols):
        st.success("Zero check complete.")
        if st.button("Continue to Missing Values →", type="primary"):
            del st.session_state._zero_col_idx
            st.session_state.stage = 'missing_bulk'
            st.rerun()
        return

    col = zero_cols[idx]
    zero_mask = df[col] == 0
    zero_count = int(zero_mask.sum())
    non_zero = df[col][df[col] != 0].dropna()

    st.subheader(f"Column: {col}")
    st.markdown(f"**Zeros found:** {zero_count} rows")
    if len(non_zero) > 0:
        st.markdown(f"**Non-zero range:** {non_zero.min():.2f} → {non_zero.max():.2f}")
        st.markdown(f"**Mean (excluding zeros):** {non_zero.mean():.2f}")

    st.markdown("**Rows with zero:**")
    st.dataframe(df[zero_mask].head(10), use_container_width=True)

    st.divider()
    st.markdown("**Is zero a valid value here?**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ No — treat zeros as missing", key=f"zero_missing_{col}"):
            from utils.audit import save_snapshot, log_action
            from utils.cleaner import replace_zeros_with_nan

            save_snapshot(df)
            new_df, affected, details = replace_zeros_with_nan(df, col)
            st.session_state.working_df = new_df
            log_action(
                phase='zeros', column=col,
                issue=f'{zero_count} zeros found',
                decision='Replaced zeros with NaN',
                rows_affected=affected,
                method='zero_as_missing',
                details={},
            )
            st.session_state._zero_col_idx += 1
            st.rerun()
    with c2:
        if st.button("✅ Yes — zero is legitimate", key=f"zero_valid_{col}"):
            from utils.audit import log_action

            log_action(
                phase='zeros', column=col,
                issue=f'{zero_count} zeros found',
                decision='Zeros confirmed as valid',
                rows_affected=0,
                method='zero_kept_valid',
                details={},
            )
            st.session_state._zero_col_idx += 1
            st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Upload `Test Data_Aurora Gems.csv` → advance through to Phase 4.
- Verify the `y` column (with 8 zeros) is shown.
- Test both "treat as missing" and "legitimate" paths.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 4 zero values review"
```

---

## Task 11: Phase 5.1 — Missing Values: Bulk Cleanup

**Files:**
- Modify: `app.py` — implement `show_missing_bulk()`

- [ ] **Step 1: Implement `show_missing_bulk()`**

Replace the stub:

```python
def show_missing_bulk():
    df = st.session_state.working_df

    st.header("🧹 Step 5 of 7: Missing Values")

    # Recompute missingness
    from utils.scanner import get_fully_empty_columns, get_high_missingness_rows

    total_missing = int(df.isna().sum().sum())
    total_cells = df.shape[0] * df.shape[1]
    cols_with_missing = [c for c in df.columns if df[c].isna().any()]

    # Opening summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rows", f"{len(df):,}")
    c2.metric("Columns with Missing", str(len(cols_with_missing)))
    c3.metric("Missing Cells", f"{total_missing:,} ({total_missing/total_cells*100:.1f}%)" if total_cells > 0 else "0")

    if total_missing == 0:
        st.success("🎉 No missing values found! Nothing to clean here.")
        if st.button("Continue →", type="primary"):
            st.session_state.stage = 'type_convert'
            st.rerun()
        return

    # Horizontal bars per column
    st.subheader("Missing values by column")
    for col in cols_with_missing:
        pct = df[col].isna().sum() / len(df) * 100
        if pct < 1:
            color = "green"
        elif pct <= 10:
            color = "orange"
        else:
            color = "red"
        st.markdown(f"**{col}**: {pct:.1f}% missing")
        st.progress(min(pct / 100, 1.0))

    # Fully empty columns
    empty_cols = get_fully_empty_columns(df)
    if empty_cols:
        st.divider()
        st.warning(f"⚠️ {len(empty_cols)} columns are entirely empty. Imputation is not possible.")
        from utils.audit import save_snapshot, log_action
        from utils.cleaner import drop_column

        for col in empty_cols:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{col}** — 100% empty")
            with c2:
                if st.button(f"Drop {col}", key=f"drop_empty_{col}"):
                    save_snapshot(df)
                    new_df, affected, details = drop_column(st.session_state.working_df, col)
                    st.session_state.working_df = new_df
                    log_action(
                        phase='missing', column=col,
                        issue='Column 100% empty',
                        decision='Dropped column',
                        rows_affected=affected,
                        method='drop_empty_column',
                        details=details,
                    )
                    st.rerun()

    # High-missingness rows
    st.divider()
    st.subheader("Row-level missingness")
    threshold = st.number_input(
        "Drop rows with more than X% of columns missing:",
        min_value=0, max_value=100, value=30, step=5,
        help="Rows where this percentage of column values are missing will be dropped."
    )
    threshold_frac = threshold / 100.0
    high_miss_rows = get_high_missingness_rows(df, threshold_frac)

    if len(high_miss_rows) > 0:
        st.warning(f"⚠️ {len(high_miss_rows)} rows have {threshold}%+ of columns missing.")
        st.dataframe(df.loc[high_miss_rows].head(20), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Drop these rows (Recommended)", type="primary", key="drop_high_miss"):
                from utils.audit import save_snapshot, log_action
                from utils.cleaner import drop_rows_by_index

                save_snapshot(df)
                new_df, affected, details = drop_rows_by_index(df, high_miss_rows)
                st.session_state.working_df = new_df
                log_action(
                    phase='missing', column='*',
                    issue=f'{len(high_miss_rows)} rows with {threshold}%+ missing',
                    decision='Dropped high-missingness rows',
                    rows_affected=affected,
                    method='drop_rows_high_missingness',
                    details={'threshold': threshold_frac},
                )
                st.rerun()
        with c2:
            if st.button("Keep them", key="keep_high_miss"):
                pass  # Do nothing, user continues
    else:
        st.success(f"✅ No rows have {threshold}%+ of columns missing.")

    # Duplicate info note
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        st.info(f"💡 You have {dup_count:,} duplicate rows. These will be handled in Step 7.")

    # Continue button
    st.divider()
    if st.button("Continue to column-by-column cleanup →", type="primary"):
        # Recompute columns with missing values
        working = st.session_state.working_df
        missing_cols = [c for c in working.columns if working[c].isna().any()]
        missing_cols.sort(key=lambda c: working[c].isna().sum())  # ascending
        st.session_state.missing_value_cols = missing_cols
        st.session_state.current_col_idx = 0
        st.session_state.stage = 'missing_columns'
        st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Upload file → advance through phases to 5.1.
- Verify opening summary with missing counts.
- Test the threshold input — change to different values and verify row counts change.
- Test dropping high-missingness rows.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 5.1 bulk cleanup — empty columns, high-missingness rows"
```

---

## Task 12: Phase 5.2 — Missing Values: Column-by-Column

**Files:**
- Modify: `app.py` — implement `show_missing_columns()`

- [ ] **Step 1: Implement `show_missing_columns()`**

Replace the stub. This is the largest single function — it shows type-aware options for each column:

```python
def show_missing_columns():
    df = st.session_state.working_df
    missing_cols = st.session_state.missing_value_cols
    idx = st.session_state.current_col_idx

    st.header("🧹 Step 5 of 7: Missing Values")

    # Recompute — some columns may no longer have missing after bulk cleanup
    missing_cols = [c for c in missing_cols if c in df.columns and df[c].isna().any()]
    st.session_state.missing_value_cols = missing_cols

    if idx >= len(missing_cols) or len(missing_cols) == 0:
        skipped = st.session_state.skipped_cols
        remaining = int(df.isna().sum().sum())
        if remaining == 0:
            st.success("🎉 All missing values resolved!")
        else:
            st.info(f"{remaining} missing values remain in {len(skipped)} intentionally skipped columns: {', '.join(skipped)}")
        if st.button("Proceed to Type Conversion →", type="primary"):
            st.session_state.stage = 'type_convert'
            st.rerun()
        return

    col = missing_cols[idx]
    total = len(missing_cols)
    contract = st.session_state.column_contracts.get(col, {})
    col_type = contract.get('intended_type', 'Text')

    st.progress((idx) / total)
    st.caption(f"Column {idx + 1} of {total} with missing values")

    missing_count = int(df[col].isna().sum())
    missing_pct = missing_count / len(df) * 100

    st.subheader(f"Column: {col}")
    st.markdown(f"**Confirmed Type:** {col_type}")
    st.markdown(f"**Missing:** {missing_count} rows ({missing_pct:.1f}%)")

    # Type-relevant stats
    non_null = df[col].dropna()
    if col_type == 'Continuous Number':
        numeric_vals = pd.to_numeric(non_null, errors='coerce').dropna()
        if len(numeric_vals) > 0:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Min", f"{numeric_vals.min():.2f}")
            c2.metric("Max", f"{numeric_vals.max():.2f}")
            c3.metric("Mean", f"{numeric_vals.mean():.2f}")
            c4.metric("Median", f"{numeric_vals.median():.2f}")
            c5.metric("Std Dev", f"{numeric_vals.std():.2f}")
    elif col_type == 'Category':
        st.markdown(f"**Unique values:** {non_null.nunique()}")
        counts = non_null.value_counts().head(5)
        st.dataframe(counts.reset_index(), use_container_width=True, hide_index=True)
    elif col_type == 'Date / Time':
        dates = pd.to_datetime(non_null, errors='coerce').dropna()
        if len(dates) > 0:
            c1, c2, c3 = st.columns(3)
            c1.metric("Earliest", str(dates.min().date()))
            c2.metric("Latest", str(dates.max().date()))
            c3.metric("Median", str(dates.median().date()) if len(dates) > 0 else "N/A")

    # Show missing rows
    st.markdown("**Rows with missing values (max 10):**")
    st.dataframe(df[df[col].isna()].head(10), use_container_width=True)

    # Options by type
    st.divider()
    st.markdown("**What would you like to do?**")

    from utils.audit import save_snapshot, log_action
    from utils.cleaner import (
        impute_mean, impute_median, impute_mode, impute_group_median,
        impute_custom, impute_marker, impute_date, drop_rows_by_index,
    )

    def _apply_and_advance(new_df, affected, method, decision, details=None):
        st.session_state.working_df = new_df
        log_action(
            phase='missing', column=col,
            issue=f'{missing_count} missing values',
            decision=decision,
            rows_affected=affected,
            method=method,
            details=details or {},
        )
        st.session_state._show_preview = {
            'col': col, 'before': missing_count, 'after': int(new_df[col].isna().sum()),
        }
        st.rerun()

    if col_type == 'Continuous Number':
        numeric_vals = pd.to_numeric(non_null, errors='coerce').dropna()
        mean_val = numeric_vals.mean() if len(numeric_vals) > 0 else 0
        median_val = numeric_vals.median() if len(numeric_vals) > 0 else 0

        # Skew warning
        if len(numeric_vals) > 0 and median_val != 0:
            if abs(mean_val - median_val) / abs(median_val) > 0.5:
                direction = 'right' if mean_val > median_val else 'left'
                st.warning(f"⚠️ This column is {direction}-skewed. Median may be more reliable.")

        option = st.radio("Choose:", [
            f"A) Drop these rows (dataset: {len(df):,} → {len(df) - missing_count:,} rows)",
            f"B) Fill with mean ({mean_val:.2f})",
            f"C) Fill with median ({median_val:.2f})",
            "D) Fill with group median",
            "E) Fill with custom value",
            "F) Leave for now",
        ], key=f"opt_{col}")

        # Group median config
        group_cols = []
        if option.startswith("D)"):
            other_cols = [c for c in df.columns if c != col]
            group_cols = st.multiselect("Group by which columns?", other_cols, key=f"group_{col}")
            if group_cols:
                # Guardrail: check for small groups
                group_sizes = df.groupby(
                    [df[gc].fillna('__MISSING__').astype(str) for gc in group_cols]
                )[col].apply(lambda x: x.notna().sum())
                small = int((group_sizes < 3).sum())
                if small > 0:
                    st.warning(f"⚠️ {small} groups have fewer than 3 observations. Those fills may be unreliable.")

        custom_val = None
        if option.startswith("E)"):
            custom_val = st.number_input("Enter value:", key=f"custom_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option.startswith("A)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows with missing values')
            elif option.startswith("B)"):
                new_df, affected, details = impute_mean(df, col)
                _apply_and_advance(new_df, affected, 'impute_mean', f'Filled with mean ({mean_val:.2f})', details)
            elif option.startswith("C)"):
                new_df, affected, details = impute_median(df, col)
                _apply_and_advance(new_df, affected, 'impute_median', f'Filled with median ({median_val:.2f})', details)
            elif option.startswith("D)") and group_cols:
                new_df, affected, details = impute_group_median(df, col, group_cols)
                _apply_and_advance(new_df, affected, 'impute_group_median', 'Filled with group median', details)
                if details.get('fallback_fills', 0) > 0:
                    log_action(
                        phase='missing', column=col,
                        issue='Group median fallback',
                        decision='Filled remaining with global median',
                        rows_affected=details['fallback_fills'],
                        method='impute_group_median_fallback',
                        details={'global_median': details['global_median']},
                    )
            elif option.startswith("E)") and custom_val is not None:
                new_df, affected, details = impute_custom(df, col, custom_val)
                _apply_and_advance(new_df, affected, 'impute_custom_value', f'Filled with {custom_val}', details)
            elif option.startswith("F)"):
                st.session_state.skipped_cols.append(col)
                log_action(
                    phase='missing', column=col,
                    issue=f'{missing_count} missing values',
                    decision='Left for now',
                    rows_affected=0, method='skip_column', details={},
                )
                st.session_state.current_col_idx += 1
                st.rerun()

    elif col_type in ('Category', 'Continuous Number' if False else 'Category'):
        mode_val = non_null.mode().iloc[0] if len(non_null) > 0 else 'N/A'
        mode_count = int((non_null == mode_val).sum()) if len(non_null) > 0 else 0

        option = st.radio("Choose:", [
            f"A) Fill with mode — most common: '{mode_val}' ({mode_count} times)",
            "B) Fill with custom category",
            f"C) Drop these rows (dataset: {len(df):,} → {len(df) - missing_count:,})",
            "D) Mark as 'Unknown'",
            "E) Leave for now",
        ], key=f"opt_{col}")

        custom_cat = None
        if option.startswith("B)"):
            custom_cat = st.text_input("Enter category:", key=f"custom_cat_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option.startswith("A)"):
                new_df, affected, details = impute_mode(df, col)
                _apply_and_advance(new_df, affected, 'impute_mode', f'Filled with mode ({mode_val})', details)
            elif option.startswith("B)") and custom_cat:
                new_df, affected, details = impute_custom(df, col, custom_cat)
                _apply_and_advance(new_df, affected, 'impute_custom_value', f'Filled with {custom_cat}', details)
            elif option.startswith("C)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option.startswith("D)"):
                new_df, affected, details = impute_marker(df, col, 'Unknown')
                _apply_and_advance(new_df, affected, 'impute_marker_unknown', 'Marked as Unknown', details)
            elif option.startswith("E)"):
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    elif col_type == 'Date / Time':
        dates = pd.to_datetime(non_null, errors='coerce').dropna()
        option = st.radio("Choose:", [
            "A) Drop these rows",
            f"B) Fill with most recent date ({dates.max().date() if len(dates) > 0 else 'N/A'})",
            f"C) Fill with oldest date ({dates.min().date() if len(dates) > 0 else 'N/A'})",
            "D) Fill with median date",
            "E) Custom date",
            "F) Leave for now",
        ], key=f"opt_{col}")

        custom_date = None
        if option.startswith("E)"):
            custom_date = st.date_input("Enter date:", key=f"custom_date_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            # Ensure column is datetime for imputation
            df_work = st.session_state.working_df.copy()
            df_work[col] = pd.to_datetime(df_work[col], errors='coerce')
            st.session_state.working_df = df_work

            if option.startswith("A)"):
                idx_to_drop = df_work[df_work[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df_work, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option.startswith("B)"):
                new_df, affected, details = impute_date(df_work, col, 'most_recent')
                _apply_and_advance(new_df, affected, 'impute_most_recent_date', 'Filled with most recent', details)
            elif option.startswith("C)"):
                new_df, affected, details = impute_date(df_work, col, 'oldest')
                _apply_and_advance(new_df, affected, 'impute_oldest_date', 'Filled with oldest', details)
            elif option.startswith("D)"):
                new_df, affected, details = impute_date(df_work, col, 'median')
                _apply_and_advance(new_df, affected, 'impute_median_date', 'Filled with median', details)
            elif option.startswith("E)") and custom_date:
                new_df, affected, details = impute_date(df_work, col, 'custom', custom_date=custom_date)
                _apply_and_advance(new_df, affected, 'impute_median_date', f'Filled with {custom_date}', details)
            elif option.startswith("F)"):
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    elif col_type in ('ID / Identifier', 'Boolean'):
        option = st.radio("Choose:", [
            f"A) Drop these rows",
            "B) Mark as 'Unknown'" if col_type == 'ID / Identifier' else None,
            "C) Leave for now",
        ], key=f"opt_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option and option.startswith("A)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option and option.startswith("B)"):
                new_df, affected, details = impute_marker(df, col, 'Unknown')
                _apply_and_advance(new_df, affected, 'impute_marker_unknown', 'Marked as Unknown', details)
            else:
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    else:  # Free Text
        option = st.radio("Choose:", [
            "A) Drop these rows",
            "B) Fill with empty string",
            "C) Mark as 'Unknown'",
            "D) Leave for now",
        ], key=f"opt_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option.startswith("A)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option.startswith("B)"):
                new_df, affected, details = impute_custom(df, col, '')
                _apply_and_advance(new_df, affected, 'impute_custom_value', 'Filled with empty string', details)
            elif option.startswith("C)"):
                new_df, affected, details = impute_marker(df, col, 'Unknown')
                _apply_and_advance(new_df, affected, 'impute_marker_unknown', 'Marked as Unknown', details)
            else:
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    # Preview after action (shown on rerun)
    preview = st.session_state.get('_show_preview')
    if preview and preview['col'] == col:
        st.divider()
        st.success(f"✅ Done. Before: {preview['before']} missing | After: {preview['after']} missing")
        st.markdown("**Sample of updated column:**")
        st.dataframe(st.session_state.working_df[[col]].head(5), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✓ Looks good — next column →", key="next_col"):
                st.session_state.current_col_idx += 1
                del st.session_state._show_preview
                st.rerun()
        with c2:
            if st.session_state.undo_enabled:
                if st.button("↩ Undo — let me reconsider", key="undo_col"):
                    from utils.audit import undo
                    undo()
                    del st.session_state._show_preview
                    st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Upload `Test Data_Aurora Gems.csv` → advance through all phases to 5.2.
- Test imputing a numeric column with mean.
- Test filling a categorical column with mode.
- Test the undo button.
- Verify progress bar advances.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 5.2 column-by-column imputation with type-aware options"
```

---

## Task 13: Phase 6 — Type Conversion

**Files:**
- Modify: `app.py` — implement `show_type_conversion()`

- [ ] **Step 1: Implement `show_type_conversion()`**

Replace the stub:

```python
def show_type_conversion():
    df = st.session_state.working_df
    contracts = st.session_state.column_contracts

    st.header("🔄 Step 6 of 7: Apply Data Types")
    st.caption("Now that missing values are handled, let's convert columns to their confirmed types.")

    from utils.cleaner import apply_type_conversion
    from utils.audit import save_snapshot, log_action

    type_to_dtype = {
        'Continuous Number': 'numeric',
        'Category': 'category',
        'Date / Time': 'datetime',
        'Boolean': 'bool',
        'Text': 'object',
        'ID / Identifier': 'object',
    }

    # Assess which columns need conversion
    conversion_status = []
    for col in df.columns:
        if col not in contracts:
            continue
        intended = contracts[col]['intended_type']
        current = str(df[col].dtype)
        target_dtype = type_to_dtype.get(intended, 'object')

        needs_conversion = True
        if intended in ('Text', 'ID / Identifier') and current == 'object':
            needs_conversion = False
        elif intended == 'Continuous Number' and pd.api.types.is_numeric_dtype(df[col]):
            needs_conversion = False
        elif intended == 'Category' and current == 'category':
            needs_conversion = False
        elif intended == 'Date / Time' and pd.api.types.is_datetime64_any_dtype(df[col]):
            needs_conversion = False
        elif intended == 'Boolean' and current == 'bool':
            needs_conversion = False

        # Check if conversion might lose data
        may_lose = False
        if needs_conversion and intended == 'Continuous Number':
            test = pd.to_numeric(df[col], errors='coerce')
            losses = int(df[col].notna().sum() - test.notna().sum())
            if losses > 0:
                may_lose = True

        status = '✅ Already correct' if not needs_conversion else ('⚠️ May lose data' if may_lose else '🔄 Needs conversion')
        conversion_status.append({
            'Column': col,
            'Current': current,
            'Intended': intended,
            'Status': status,
            'needs_conversion': needs_conversion,
        })

    status_df = pd.DataFrame(conversion_status)
    st.dataframe(status_df[['Column', 'Current', 'Intended', 'Status']], use_container_width=True, hide_index=True)

    needs_work = [r for r in conversion_status if r['needs_conversion']]

    if not needs_work:
        st.success("✅ All columns already match their confirmed types.")
        if st.button("Continue to Duplicates →", type="primary"):
            st.session_state.stage = 'duplicates'
            st.rerun()
        return

    st.divider()
    st.markdown(f"**{len(needs_work)} columns need conversion.**")

    option = st.radio("How would you like to proceed?", [
        "✅ Apply all conversions (Recommended)",
        "🔍 Review one by one",
    ])

    if option.startswith("✅"):
        if st.button("Apply All", type="primary"):
            save_snapshot(df)
            for item in needs_work:
                col = item['Column']
                intended = contracts[col]['intended_type']
                new_df, affected, details = apply_type_conversion(
                    st.session_state.working_df, col, intended
                )
                st.session_state.working_df = new_df
                log_action(
                    phase='type_convert', column=col,
                    issue=f'Convert from {item["Current"]} to {intended}',
                    decision=f'Converted to {intended}',
                    rows_affected=affected,
                    method='type_conversion',
                    details=details,
                )
                if details.get('coercion_losses', 0) > 0:
                    st.warning(f"⚠️ {col}: {details['coercion_losses']} values could not be converted and became NaN.")
            st.success("All conversions applied.")
            st.session_state.stage = 'duplicates'
            st.rerun()

    else:
        for item in needs_work:
            col = item['Column']
            intended = contracts[col]['intended_type']
            with st.expander(f"{col}: {item['Current']} → {intended}"):
                # Preview
                st.markdown("**First 5 values that would change:**")
                sample = df[col].dropna().head(5)
                st.dataframe(sample, use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"Apply", key=f"convert_{col}"):
                        save_snapshot(df)
                        new_df, affected, details = apply_type_conversion(
                            st.session_state.working_df, col, intended
                        )
                        st.session_state.working_df = new_df
                        log_action(
                            phase='type_convert', column=col,
                            issue=f'Convert to {intended}',
                            decision=f'Converted to {intended}',
                            rows_affected=affected,
                            method='type_conversion',
                            details=details,
                        )
                        st.rerun()
                with c2:
                    if st.button(f"Skip", key=f"skip_convert_{col}"):
                        log_action(
                            phase='type_convert', column=col,
                            issue=f'Convert to {intended}',
                            decision='Skipped',
                            rows_affected=0,
                            method='type_conversion_skipped',
                            details={},
                        )

        st.divider()
        if st.button("Continue to Duplicates →", type="primary"):
            st.session_state.stage = 'duplicates'
            st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Advance through all phases to Phase 6.
- Verify columns that need conversion are identified.
- Test "Apply all" path.
- Verify audit log entries for type conversions.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 6 type conversion with format inference"
```

---

## Task 14: Phase 7 — Duplicates

**Files:**
- Modify: `app.py` — implement `show_duplicates()`

- [ ] **Step 1: Implement `show_duplicates()`**

Replace the stub:

```python
def show_duplicates():
    df = st.session_state.working_df

    st.header("🔍 Step 7 of 7: Duplicate Rows")

    dup_count = int(df.duplicated().sum())

    if dup_count == 0:
        st.success("✅ No duplicate rows found. Your data is clean.")
        if st.button("Finish →", type="primary"):
            st.session_state.stage = 'done'
            st.rerun()
        return

    st.markdown(f"We found **{dup_count:,}** rows that appear more than once.")

    # Show duplicates
    dup_mask = df.duplicated(keep=False)
    dup_rows = df[dup_mask].sort_values(by=list(df.columns))
    st.dataframe(dup_rows.head(20), use_container_width=True)

    st.divider()
    option = st.radio("What would you like to do?", [
        "Remove duplicates — keep first (Recommended)",
        "Remove duplicates — keep last",
        "Keep all — duplicates are intentional",
    ])

    if st.button("Apply", type="primary"):
        from utils.audit import save_snapshot, log_action
        from utils.cleaner import remove_duplicates

        if option.startswith("Remove") and "first" in option:
            save_snapshot(df)
            new_df, affected, details = remove_duplicates(df, keep='first')
            st.session_state.working_df = new_df
            log_action(
                phase='duplicates', column='*',
                issue=f'{dup_count} duplicate rows',
                decision='Removed duplicates, kept first',
                rows_affected=affected,
                method='remove_duplicates_keep_first',
                details=details,
            )
        elif option.startswith("Remove") and "last" in option:
            save_snapshot(df)
            new_df, affected, details = remove_duplicates(df, keep='last')
            st.session_state.working_df = new_df
            log_action(
                phase='duplicates', column='*',
                issue=f'{dup_count} duplicate rows',
                decision='Removed duplicates, kept last',
                rows_affected=affected,
                method='remove_duplicates_keep_last',
                details=details,
            )
        else:
            log_action(
                phase='duplicates', column='*',
                issue=f'{dup_count} duplicate rows',
                decision='Kept all duplicates',
                rows_affected=0,
                method='keep_duplicates',
                details={},
            )

        st.session_state.stage = 'done'
        st.rerun()
```

- [ ] **Step 2: Test manually in browser**

- Advance through all phases to Phase 7.
- Verify duplicate count matches (147 for the test data).
- Test "keep first" option.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 7 duplicate detection and removal"
```

---

## Task 15: Phase 8 — Completion

**Files:**
- Modify: `app.py` — implement `show_completion()`

- [ ] **Step 1: Implement `show_completion()`**

Replace the stub:

```python
def show_completion():
    df = st.session_state.working_df
    original = st.session_state.original_df

    st.header("🎉 Your Data is Clean")

    # Before vs After
    st.subheader("Before vs After")

    orig_missing = int(original.isna().sum().sum())
    clean_missing = int(df.isna().sum().sum())
    orig_dupes = int(original.duplicated().sum())
    clean_dupes = int(df.duplicated().sum())

    # Count disguised nulls resolved from audit log
    disguised_resolved = sum(
        e['rows_affected'] for e in st.session_state.audit_log
        if e['method'] == 'replace_disguised_nulls'
    )

    comparison = pd.DataFrame({
        '': ['Rows', 'Columns', 'Missing cells', 'Duplicates', 'Disguised nulls resolved'],
        'Before': [f"{len(original):,}", str(len(original.columns)),
                    f"{orig_missing:,}", f"{orig_dupes:,}", "0"],
        'After': [f"{len(df):,}", str(len(df.columns)),
                   f"{clean_missing:,}", f"{clean_dupes:,}", f"{disguised_resolved:,}"],
        'Change': [
            f"{len(df) - len(original):,}",
            str(len(df.columns) - len(original.columns)),
            f"{clean_missing - orig_missing:,}",
            f"{clean_dupes - orig_dupes:,}",
            f"+{disguised_resolved:,}",
        ],
    })
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    # Full Audit Log
    st.subheader("Full Audit Log")
    log = st.session_state.audit_log
    if log:
        log_df = pd.DataFrame(log)
        st.dataframe(log_df, use_container_width=True, hide_index=True)

    # Downloads
    st.subheader("Download")
    import io

    c1, c2 = st.columns(2)
    with c1:
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        base_name = st.session_state.filename.rsplit('.', 1)[0]
        st.download_button(
            "⬇ Download Clean CSV",
            csv_buf.getvalue(),
            file_name=f"clean_{base_name}.csv",
            mime="text/csv",
            type="primary",
        )
    with c2:
        if log:
            log_buf = io.StringIO()
            pd.DataFrame(log).to_csv(log_buf, index=False)
            st.download_button(
                "⬇ Download Audit Log CSV",
                log_buf.getvalue(),
                file_name=f"auditlog_{base_name}.csv",
                mime="text/csv",
            )

    # Reproducibility Recipe
    st.subheader("Reproducibility Recipe")
    with st.expander("📋 View the cleaning recipe (pandas code)"):
        from utils.recipe import generate_recipe
        recipe_code = generate_recipe(log, st.session_state.filename)
        st.code(recipe_code, language='python')

    # Reset
    st.divider()
    if st.button("🔄 Clean another file"):
        from utils.state import reset_session_state
        reset_session_state()
        st.rerun()
```

- [ ] **Step 2: Test manually in browser — full end-to-end**

Run the full flow with `Test Data_Aurora Gems.csv`:
1. Upload → Data Portrait → Confirm types → Fix disguised nulls → Review zeros → Bulk cleanup → Column-by-column imputation → Type conversion → Duplicates → Completion.
2. Verify before/after stats are correct.
3. Download clean CSV and audit log — open both and verify contents.
4. View reproducibility recipe — verify it generates valid-looking pandas code.
5. Click "Clean another file" — verify full reset.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Phase 8 completion with downloads, audit log, and reproducibility recipe"
```

---

## Task 16: Final Polish + README

**Files:**
- Create: `README.md`
- Modify: `app.py` — any final fixes from end-to-end testing

- [ ] **Step 1: Create `README.md`**

```markdown
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
```

- [ ] **Step 2: Run full test suite**

Run: `cd "/Users/rafid/Documents/Claude/Claude Code Projects/CleanSlate (Data Cleaning Tool Using Python) V1.0" && python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md app.py
git commit -m "feat: README and final polish"
```

- [ ] **Step 4: Run end-to-end test in browser one final time**

Upload `Test Data_Aurora Gems.csv` and walk through all 7 steps. Verify everything works.
