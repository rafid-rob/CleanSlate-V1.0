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
