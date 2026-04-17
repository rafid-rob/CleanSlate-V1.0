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

def test_drop_rows_by_index():
    df = pd.DataFrame({'a': [1, 2, 3, 4, 5]})
    new_df, affected, details = drop_rows_by_index(df, pd.Index([1, 3]))
    assert affected == 2
    assert len(new_df) == 3
    assert list(new_df['a']) == [1, 3, 5]

def test_drop_column():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4], 'c': [5, 6]})
    new_df, affected, details = drop_column(df, 'b')
    assert 'b' not in new_df.columns
    assert list(new_df.columns) == ['a', 'c']

def test_impute_mean():
    df = pd.DataFrame({'a': [10.0, np.nan, 20.0, np.nan, 30.0]})
    new_df, affected, details = impute_mean(df, 'a')
    assert affected == 2
    assert new_df['a'].isna().sum() == 0
    assert new_df['a'].iloc[1] == 20.0

def test_impute_median():
    df = pd.DataFrame({'a': [10.0, np.nan, 30.0, np.nan, 50.0]})
    new_df, affected, details = impute_median(df, 'a')
    assert affected == 2
    assert new_df['a'].iloc[1] == 30.0

def test_impute_mode():
    df = pd.DataFrame({'a': ['cat', 'dog', 'cat', np.nan, 'cat']})
    new_df, affected, details = impute_mode(df, 'a')
    assert affected == 1
    assert new_df['a'].iloc[3] == 'cat'

def test_impute_group_median_basic():
    df = pd.DataFrame({
        'region': ['A', 'A', 'A', 'B', 'B', 'B'],
        'value': [10.0, np.nan, 20.0, 30.0, np.nan, 40.0],
    })
    new_df, affected, details = impute_group_median(df, 'value', ['region'])
    assert affected == 2
    assert new_df['value'].isna().sum() == 0
    assert new_df['value'].iloc[1] == 15.0
    assert new_df['value'].iloc[4] == 35.0
    assert details['group_fills'] == 2
    assert details['fallback_fills'] == 0

def test_impute_group_median_with_nan_in_group_col():
    df = pd.DataFrame({
        'region': ['A', 'A', np.nan, np.nan],
        'value': [10.0, np.nan, 20.0, np.nan],
    })
    new_df, affected, details = impute_group_median(df, 'value', ['region'])
    assert new_df['value'].isna().sum() == 0
    assert new_df['value'].iloc[1] == 10.0
    assert new_df['value'].iloc[3] == 20.0

def test_impute_group_median_fallback():
    df = pd.DataFrame({
        'region': ['A', 'A', 'B', 'B'],
        'value': [10.0, 20.0, np.nan, np.nan],
    })
    new_df, affected, details = impute_group_median(df, 'value', ['region'])
    assert new_df['value'].isna().sum() == 0
    assert new_df['value'].iloc[2] == 15.0
    assert new_df['value'].iloc[3] == 15.0
    assert details['fallback_fills'] == 2

def test_impute_custom():
    df = pd.DataFrame({'a': [1.0, np.nan, 3.0]})
    new_df, affected, details = impute_custom(df, 'a', 99)
    assert affected == 1
    assert new_df['a'].iloc[1] == 99

def test_impute_marker():
    df = pd.DataFrame({'a': ['hello', np.nan, 'world']})
    new_df, affected, details = impute_marker(df, 'a', 'Unknown')
    assert affected == 1
    assert new_df['a'].iloc[1] == 'Unknown'

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

def test_apply_type_conversion_to_numeric():
    df = pd.DataFrame({'a': ['1.5', '2.3', '3.7', 'bad']})
    new_df, affected, details = apply_type_conversion(df, 'a', 'Continuous Number')
    assert pd.api.types.is_numeric_dtype(new_df['a'])
    assert new_df['a'].isna().sum() == 1
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
