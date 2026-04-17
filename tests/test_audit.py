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
    assert state['history'][0] is not df
    pd.testing.assert_frame_equal(state['history'][0], df)


@patch('utils.audit.st')
def test_save_snapshot_max_5(mock_st):
    from utils.audit import save_snapshot
    ss, state = _make_session_state()
    mock_st.session_state = ss
    state['undo_enabled'] = True
    state['history'] = []

    for i in range(7):
        save_snapshot(pd.DataFrame({'a': [i]}))

    assert len(state['history']) == 5
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
