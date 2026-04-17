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
    s = pd.Series(['1.5', '2.3', '3.7', '4.1', '5.9'] * 20)
    result = detect_column_type(s)
    assert result in ('continuous_numeric', 'categorical_numeric')

def test_find_disguised_nulls_basic():
    df = pd.DataFrame({'a': ['hello', 'na', 'world', '?', 'good'], 'b': [1, 2, 3, 4, 5]})
    result = find_disguised_nulls(df)
    assert 'a' in result
    assert 'na' in result['a']
    assert '?' in result['a']
    assert 'b' not in result

def test_find_disguised_nulls_case_insensitive():
    df = pd.DataFrame({'a': ['N/A', 'None', 'valid']})
    result = find_disguised_nulls(df)
    assert 'a' in result
    assert 'N/A' in result['a']
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

def test_find_zero_columns_basic():
    df = pd.DataFrame({'price': [10, 0, 20, 30], 'flag': [0, 1, 1, 0], 'count': [5, 6, 7, 8]})
    result = find_zero_columns(df)
    assert 'price' in result
    assert 'flag' not in result
    assert 'count' not in result

def test_find_zero_columns_no_zeros():
    df = pd.DataFrame({'a': [1, 2, 3]})
    assert find_zero_columns(df) == []

def test_describe_numeric_skewed():
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

def test_high_missingness_default_threshold():
    df = pd.DataFrame({'a': [1, None, None, 4], 'b': [None, None, None, 8], 'c': [None, None, None, 12]})
    result = get_high_missingness_rows(df, 0.3)
    assert 0 in result
    assert 1 in result
    assert 2 in result
    assert 3 not in result

def test_high_missingness_custom_threshold():
    df = pd.DataFrame({'a': [1, None, None], 'b': [2, None, None], 'c': [3, 4, None]})
    result = get_high_missingness_rows(df, 0.5)
    assert 2 in result
    assert 1 not in result

def test_fully_empty_columns():
    df = pd.DataFrame({'a': [1, 2, 3], 'b': [None, None, None], 'c': [None, None, None]})
    result = get_fully_empty_columns(df)
    assert 'b' in result
    assert 'c' in result
    assert 'a' not in result

def test_no_empty_columns():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    assert get_fully_empty_columns(df) == []
