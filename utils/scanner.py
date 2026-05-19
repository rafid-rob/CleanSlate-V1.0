import pandas as pd
import numpy as np

KNOWN_NULL_STRINGS = {
    '', ' ', '  ',
    'na', 'n/a', 'n.a.', 'n.a', '#n/a', '#na',
    'nan', 'none', 'null', 'nil',
    '?', '-', '--', '---',
    'missing', 'undefined', 'unknown', 'n/d', 'tbd',
}

ID_HINT_KEYWORDS = {
    'id', 'code', 'number', 'sku', 'postcode',
    'zip', 'phone', 'uuid', 'ref', 'identifier'
}


def is_likely_id_column(col_name: str) -> bool:
    name_lower = col_name.lower()
    return any(hint in name_lower.split('_') or hint in name_lower.split(' ')
               for hint in ID_HINT_KEYWORDS)


def _is_text_like(series: pd.Series) -> bool:
    """True for object, CategoricalDtype, and pandas StringDtype columns."""
    return (
        pd.api.types.is_object_dtype(series)
        or isinstance(series.dtype, pd.CategoricalDtype)
        or (hasattr(pd, 'StringDtype') and isinstance(series.dtype, pd.StringDtype))
    )


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

    if pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'

    # Date sniff for text-like columns
    if _is_text_like(series):
        sample = non_null.astype(str).head(50)
        try:
            parsed = pd.to_datetime(sample, errors='coerce')
            if len(sample) > 0 and parsed.notna().sum() / len(sample) >= 0.9:
                return 'datetime'
        except Exception:
            pass

    if pd.api.types.is_numeric_dtype(series):
        unique_count = series.nunique(dropna=True)
        if unique_count <= 15:
            return 'categorical_numeric'
        return 'continuous_numeric'

    if _is_text_like(series):
        str_non_null = non_null.astype(str)
        converted = pd.to_numeric(str_non_null, errors='coerce')
        numeric_rate = converted.notna().sum() / len(str_non_null) if len(str_non_null) > 0 else 0
        if numeric_rate > 0.8:
            if converted.nunique() <= 15:
                return 'categorical_numeric'
            return 'continuous_numeric'
        unique_count = str_non_null.nunique()
        if unique_count <= 20:
            return 'categorical_text'
        return 'free_text'

    return 'free_text'


def find_disguised_nulls(df: pd.DataFrame, extra_values: list = None) -> dict:
    """
    Tier 1: checks every text-like column against KNOWN_NULL_STRINGS
    plus any user-supplied extra_values.
    """
    check_against = set(KNOWN_NULL_STRINGS)
    if extra_values:
        check_against.update(v.strip().lower() for v in extra_values if v.strip())

    results = {}
    for col in df.columns:
        series = df[col]
        if not _is_text_like(series):
            continue
        # astype(object) flattens CategoricalDtype safely before dropna
        values = series.astype(object).dropna().unique()
        found = [val for val in values if str(val).strip().lower() in check_against]
        if found:
            results[col] = found
    return results


def find_type_mismatch_nulls(df: pd.DataFrame) -> dict:
    """
    Tier 2: in columns that are >50% numeric, surface any non-numeric
    string values not already in KNOWN_NULL_STRINGS (Tier 1 handles those)
    and not zero-like (Step 4 handles those).
    """
    results = {}
    for col in df.columns:
        series = df[col]
        if not _is_text_like(series):
            continue
        non_null = series.astype(object).dropna()
        if len(non_null) == 0:
            continue
        numeric_rate = pd.to_numeric(non_null, errors='coerce').notna().sum() / len(non_null)
        if numeric_rate < 0.5:
            continue
        mismatches = []
        for val in non_null.unique():
            normalised = str(val).strip().lower()
            if normalised in KNOWN_NULL_STRINGS:
                continue
            try:
                if float(normalised) == 0:
                    continue
            except (ValueError, TypeError):
                pass
            if pd.isna(pd.to_numeric(str(val), errors='coerce')):
                mismatches.append(val)
        if mismatches:
            results[col] = mismatches
    return results


def find_zero_columns(df: pd.DataFrame) -> list:
    zero_cols = []
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            numeric = series
        else:
            numeric = pd.to_numeric(series, errors='coerce')
            if numeric.notna().sum() < series.notna().sum() * 0.5:
                continue
        unique_vals = set(numeric.dropna().unique())
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
            notes.append(f"ℹ️ **{col}** appears {direction}-skewed (mean {mean:.2f} vs median {median:.2f}). Median may be more reliable for imputation.")
        if mean != 0 and std / abs(mean) > 1.0:
            notes.append(f"ℹ️ **{col}** has high relative variability.")
        if (df[col] == 0).any():
            zero_count = (df[col] == 0).sum()
            notes.append(f"⚠️ **{col}** contains {zero_count} zero values — may need review in Step 4.")
    return notes


def get_high_missingness_rows(df: pd.DataFrame, threshold: float = 0.3) -> pd.Index:
    row_missing_pct = df.isna().sum(axis=1) / len(df.columns)
    return df.index[row_missing_pct >= threshold]


def get_fully_empty_columns(df: pd.DataFrame) -> list:
    return [col for col in df.columns if df[col].isna().all()]
