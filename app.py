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


def render_sidebar():
    """Sidebar with progress tracker, live stats, and mini audit log."""
    with st.sidebar:
        st.title("CleanSlate 🧹")

        # Progress tracker
        stages_display = [
            ('portrait', 'Data Portrait', 1),
            ('diagnose', 'Column Types', 2),
            ('nulls', 'Hidden Nulls', 3),
            ('zeros', 'Zero Values', 4),
            ('missing_bulk', 'Missing Values', 5),
            ('missing_columns', 'Missing Values', 5),
            ('type_convert', 'Type Conversion', 6),
            ('duplicates', 'Duplicates', 7),
            ('done', 'Done', 8),
        ]

        stage_order = {
            'upload': 0, 'portrait': 1, 'diagnose': 2, 'nulls': 3,
            'zeros': 4, 'missing_bulk': 5, 'missing_columns': 5,
            'type_convert': 6, 'duplicates': 7, 'done': 8,
        }

        current_order = stage_order.get(st.session_state.stage, 0)

        # Deduplicate display (missing_bulk and missing_columns both show as step 5)
        seen_steps = set()
        for stage_key, label, step_num in stages_display:
            if step_num in seen_steps:
                continue
            seen_steps.add(step_num)

            step_order = step_num
            if step_order < current_order:
                st.markdown(f"✅ Step {step_num}: {label}")
            elif step_order == current_order:
                st.markdown(f"👉 **Step {step_num}: {label}**")
            else:
                st.markdown(f"○ Step {step_num}: {label}")

        st.divider()

        # Live stats
        if st.session_state.working_df is not None:
            df = st.session_state.working_df
            st.markdown(f"📁 **File:** {st.session_state.filename}")
            st.markdown(f"📏 **Rows:** {len(df):,}")
            missing = int(df.isna().sum().sum())
            st.markdown(f"❓ **Missing cells:** {missing:,}")
            if st.session_state.undo_enabled:
                st.markdown("↩️ Undo: ✅ Enabled")
            else:
                st.markdown("↩️ Undo: ⚠️ Disabled (large file)")

        st.divider()

        # Mini audit log
        log = st.session_state.audit_log
        st.markdown(f"📋 **Audit Log:** {len(log)} actions")
        if log:
            for entry in log[-3:]:
                st.caption(f"• {entry['method']} → {entry['column']}")

        # Download partial audit log
        if log:
            import io
            audit_df = pd.DataFrame(log)
            csv_buf = io.StringIO()
            audit_df.to_csv(csv_buf, index=False)
            st.download_button(
                "⬇ Download audit log so far",
                csv_buf.getvalue(),
                file_name=f"partial_auditlog_{st.session_state.filename}.csv",
                mime="text/csv",
            )


# Routing
if st.session_state.stage != 'upload':
    render_sidebar()

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
