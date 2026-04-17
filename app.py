import streamlit as st
import pandas as pd
from utils.state import init_session_state
from utils.audit import estimate_df_memory_mb

st.set_page_config(page_title="CleanSlate", page_icon="🧹", layout="wide")

init_session_state()


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
