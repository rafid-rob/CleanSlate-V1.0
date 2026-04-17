import pandas as pd
import numpy as np


def replace_disguised_nulls_in_column(df: pd.DataFrame, col: str,
                                       suspicious_values: list) -> tuple:
    new_df = df.copy()
    mask = new_df[col].isin(suspicious_values)
    affected = int(mask.sum())
    new_df.loc[mask, col] = np.nan
    return new_df, affected, {'values_replaced': suspicious_values}


def replace_zeros_with_nan(df: pd.DataFrame, col: str) -> tuple:
    new_df = df.copy()
    # Handle both numeric zeros and string '0'/'0.0'
    numeric_col = pd.to_numeric(new_df[col], errors='coerce')
    mask = numeric_col == 0
    affected = int(mask.sum())
    new_df.loc[mask, col] = np.nan
    return new_df, affected, {}


def drop_rows_by_index(df: pd.DataFrame, index: pd.Index) -> tuple:
    new_df = df.drop(index=index).reset_index(drop=True)
    affected = len(index)
    return new_df, affected, {}


def drop_column(df: pd.DataFrame, col: str) -> tuple:
    new_df = df.drop(columns=[col])
    affected = len(df)
    return new_df, affected, {'column_dropped': col}


def impute_mean(df: pd.DataFrame, col: str) -> tuple:
    new_df = df.copy()
    new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
    mean_val = new_df[col].mean()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(mean_val)
    return new_df, affected, {'value': round(float(mean_val), 4)}


def impute_median(df: pd.DataFrame, col: str) -> tuple:
    new_df = df.copy()
    new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
    median_val = new_df[col].median()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(median_val)
    return new_df, affected, {'value': round(float(median_val), 4)}


def impute_mode(df: pd.DataFrame, col: str) -> tuple:
    new_df = df.copy()
    mode_val = new_df[col].mode().iloc[0]
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(mode_val)
    return new_df, affected, {'value': str(mode_val)}


def impute_group_median(df: pd.DataFrame, col: str,
                         group_by_cols: list) -> tuple:
    new_df = df.copy()
    new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
    missing_before = new_df[col].isna().sum()

    temp_group_cols = []
    for gc in group_by_cols:
        temp_col = f'__temp_group_{gc}'
        new_df[temp_col] = new_df[gc].fillna('__MISSING__').astype(str)
        temp_group_cols.append(temp_col)

    group_medians = new_df.groupby(temp_group_cols)[col].transform('median')
    global_median = new_df[col].median()

    mask = new_df[col].isna()
    new_df.loc[mask, col] = group_medians[mask]

    still_missing = new_df[col].isna().sum()
    group_fills = int(missing_before - still_missing)

    fallback_mask = new_df[col].isna()
    fallback_fills = int(fallback_mask.sum())
    new_df[col] = new_df[col].fillna(global_median)

    new_df.drop(columns=temp_group_cols, inplace=True)

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
    new_df = df.copy()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(value)
    return new_df, affected, {'value': value}


def impute_marker(df: pd.DataFrame, col: str, marker: str = 'Unknown') -> tuple:
    new_df = df.copy()
    mask = new_df[col].isna()
    affected = int(mask.sum())
    new_df[col] = new_df[col].fillna(marker)
    return new_df, affected, {'marker': marker}


def impute_date(df: pd.DataFrame, col: str, strategy: str,
                custom_date=None) -> tuple:
    new_df = df.copy()
    mask = new_df[col].isna()
    affected = int(mask.sum())

    non_null_dates = new_df[col].dropna()

    if strategy == 'most_recent':
        fill_val = non_null_dates.max()
    elif strategy == 'oldest':
        fill_val = non_null_dates.min()
    elif strategy == 'median':
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
    new_df = df.copy()
    original_non_null = new_df[col].notna().sum()

    if target_type == 'Continuous Number':
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
    elif target_type == 'Category':
        new_df[col] = new_df[col].astype('category')
    elif target_type == 'Date / Time':
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
    dup_count = int(df.duplicated(keep=keep).sum())
    new_df = df.drop_duplicates(keep=keep).reset_index(drop=True)
    return new_df, dup_count, {'keep': keep}
