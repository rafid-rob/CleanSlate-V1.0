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
    df = st.session_state.working_df

    st.header("📊 Your Data Portrait")
    st.caption("Before we touch anything, let's understand what you're working with.")

    # Section A — The Basics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📁 File", st.session_state.filename)
    c2.metric("📏 Rows", f"{len(df):,}")
    c3.metric("📋 Columns", str(len(df.columns)))
    size_mb = st.session_state.file_size_mb
    size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{size_mb * 1024:.0f} KB"
    c4.metric("💾 Size", size_str)

    # Section B — First Look
    st.subheader("First 4 Rows")
    st.caption("A quick look at what your data contains.")
    st.dataframe(df.head(4), use_container_width=True)

    # Section C — Column Summary Table
    st.subheader("Column Summary")
    from utils.scanner import detect_column_type
    summary_rows = []
    for col in df.columns:
        detected = detect_column_type(df[col], col)
        non_null = int(df[col].notna().sum())
        null_count = int(df[col].isna().sum())
        null_pct = null_count / len(df) * 100 if len(df) > 0 else 0
        unique = int(df[col].nunique(dropna=True))
        samples = df[col].dropna().unique()[:3]
        sample_str = ", ".join(str(s) for s in samples)
        summary_rows.append({
            'Column': col,
            'Detected Type': detected,
            'Non-Null': f"{non_null:,}",
            'Nulls': f"{null_count:,}",
            'Null %': f"{null_pct:.1f}%",
            'Unique': f"{unique:,}",
            'Samples': sample_str,
        })

    summary_df = pd.DataFrame(summary_rows)

    def color_null_pct(val):
        pct = float(val.replace('%', ''))
        if pct == 0:
            return 'color: #2ecc71'
        elif pct <= 5:
            return 'color: #f5a623'
        else:
            return 'color: #e74c3c'

    styled = summary_df.style.applymap(color_null_pct, subset=['Null %'])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Section D — Statistical Summary
    numeric_df = df.describe(include='number')
    if not numeric_df.empty:
        st.subheader("Statistical Summary")
        st.dataframe(numeric_df.round(2).T, use_container_width=True)

        from utils.scanner import describe_numeric_plainly
        notes = describe_numeric_plainly(df)
        for note in notes:
            st.markdown(note)

    # Section E — Categorical Value Counts
    st.subheader("Categorical Value Counts")
    for col in df.columns:
        detected = detect_column_type(df[col], col)
        if detected in ('categorical_text', 'categorical_numeric'):
            with st.expander(f"{col} — {df[col].nunique(dropna=True)} unique values"):
                counts = df[col].value_counts().head(5)
                st.dataframe(counts.reset_index(), use_container_width=True, hide_index=True)

    # Section F — Health Snapshot
    st.subheader("Health Snapshot")
    from utils.scanner import find_disguised_nulls, find_zero_columns, get_fully_empty_columns

    total_missing = int(df.isna().sum().sum())
    if total_missing == 0:
        st.markdown("✅ **Missing Values:** None")
    else:
        st.markdown(f"⚠️ **Missing Values:** {total_missing:,} cells missing")

    disguised = find_disguised_nulls(df)
    if not disguised:
        st.markdown("✅ **Disguised Nulls:** None")
    else:
        st.markdown(f"⚠️ **Disguised Nulls:** Found in {len(disguised)} columns")

    zero_cols = find_zero_columns(df)
    if not zero_cols:
        st.markdown("✅ **Zero Values:** None in numeric columns")
    else:
        st.markdown(f"⚠️ **Zero Values:** {len(zero_cols)} columns have zeros")

    dup_count = int(df.duplicated().sum())
    if dup_count == 0:
        st.markdown("✅ **Duplicates:** None")
    else:
        st.markdown(f"⚠️ **Duplicates:** {dup_count:,} duplicate rows")

    empty_cols = get_fully_empty_columns(df)
    if not empty_cols:
        st.markdown("✅ **Fully Empty Columns:** None")
    else:
        st.markdown(f"⚠️ **Fully Empty Columns:** {len(empty_cols)} columns are 100% empty")

    # Navigation
    st.divider()
    if st.button("I've reviewed my data — start cleaning →", type="primary"):
        st.session_state.stage = 'diagnose'
        st.rerun()


def show_diagnose():
    df = st.session_state.working_df

    st.header("🔍 Step 2 of 7: Confirm Your Column Types")
    st.caption(
        "Before fixing anything, let's agree on what each column is supposed to contain. "
        "This guides every cleaning decision that follows."
    )
    st.info(
        "💡 Why does this matter? The type you confirm tells us which cleaning options "
        "make sense. You can't fill a date column with an average."
    )

    from utils.scanner import detect_column_type

    type_options = [
        'Continuous Number', 'Category', 'Date / Time',
        'Text', 'Boolean', 'ID / Identifier',
    ]

    # Map detected types to display options
    type_map = {
        'continuous_numeric': 'Continuous Number',
        'categorical_numeric': 'Category',
        'categorical_text': 'Category',
        'free_text': 'Text',
        'datetime': 'Date / Time',
        'boolean': 'Boolean',
        'identifier': 'ID / Identifier',
        'empty': 'Text',
    }

    selections = {}
    for col in df.columns:
        detected = detect_column_type(df[col], col)
        suggested = type_map.get(detected, 'Text')

        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{col}**")
            st.caption(f"Current dtype: `{df[col].dtype}`")
        with col2:
            st.caption(f"Suggested: {suggested}")
        with col3:
            default_idx = type_options.index(suggested) if suggested in type_options else 0
            selections[col] = st.selectbox(
                f"Type for {col}",
                type_options,
                index=default_idx,
                key=f"type_{col}",
                label_visibility="collapsed",
            )

    st.divider()

    if st.button("✅ Confirm All Column Types →", type="primary"):
        from utils.audit import log_action
        from utils.scanner import find_disguised_nulls, find_zero_columns

        # Store contracts (no mutations)
        contracts = {}
        for col in df.columns:
            detected = detect_column_type(df[col], col)
            contracts[col] = {
                'detected_type': type_map.get(detected, 'Text'),
                'intended_type': selections[col],
                'confirmed': True,
            }
            log_action(
                phase='diagnose',
                column=col,
                issue=f'Detected as {detected}',
                decision=f'Confirmed as {selections[col]}',
                rows_affected=0,
                method='type_confirmation',
                details={'from': type_map.get(detected, 'Text'), 'to': selections[col]},
            )

        st.session_state.column_contracts = contracts

        # Pre-compute for next phases
        st.session_state.disguised_nulls = find_disguised_nulls(df)
        st.session_state.zero_cols = find_zero_columns(df)

        st.session_state.stage = 'nulls'
        st.rerun()


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
