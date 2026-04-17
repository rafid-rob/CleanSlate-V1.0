import pandas as pd
import numpy as np

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
    name_lower = col_name.lower()
    return any(hint in name_lower.split('_') or hint in name_lower.split(' ')
               for hint in ID_HINT_KEYWORDS)


def detect_column_type(series: pd.Series, col_name: str = '') -> str:
    non_null = series.dropna()
    if len(non_null) == 0:
        return 'empty'
    if is_likely_id_column(col_name):
        return 'identifier'
    str_vals = non_null.astype(str).str.strip().str.lower()
    boolean_set = {'true', 'false', 'yes', 'no', '0', '1', 'y', 'n', 't', 'f'}
    if set(str_vals.unique()).issubset(boolean_set) and series.nunique(dropna=True) <= 2:
        return 'boolean'
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
    if pd.api.types.is_numeric_dtype(series):
        unique_count = series.nunique(dropna=True)
        if unique_count <= 15:
            return 'categorical_numeric'
        return 'continuous_numeric'
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
    zero_cols = []
    for col in df.select_dtypes(include=['number']).columns:
        unique_vals = set(df[col].dropna().unique())
        if 0 in unique_vals or 0.0 in unique_vals:
            if unique_vals.issubset({0, 1, 0.0, 1.0}):
                continue
            zero_cols.append(col)
    return zero_cols


def describe_numeric_plainly(df: pd.DataFrame) -> list:
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
            notes.append(f"\u2139\ufe0f **{col}** appears {direction}-skewed (mean {mean:.2f} vs median {median:.2f}). Median may be more reliable for imputation.")
        if mean != 0 and std / abs(mean) > 1.0:
            notes.append(f"\u2139\ufe0f **{col}** has high relative variability.")
        if (df[col] == 0).any():
            zero_count = (df[col] == 0).sum()
            notes.append(f"\u26a0\ufe0f **{col}** contains {zero_count} zero values \u2014 may need review in Step 4.")
    return notes


def get_high_missingness_rows(df: pd.DataFrame, threshold: float = 0.3) -> pd.Index:
    row_missing_pct = df.isna().sum(axis=1) / len(df.columns)
    return df.index[row_missing_pct >= threshold]


def get_fully_empty_columns(df: pd.DataFrame) -> list:
    return [col for col in df.columns if df[col].isna().all()]
