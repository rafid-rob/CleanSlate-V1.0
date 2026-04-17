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
