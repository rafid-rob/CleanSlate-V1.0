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
