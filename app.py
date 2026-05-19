import streamlit as st
import pandas as pd
from utils.state import init_session_state
from utils.audit import estimate_df_memory_mb

st.set_page_config(page_title="CleanSlate", page_icon="🧹", layout="wide")

init_session_state()


def inject_css():
    st.markdown("""
    <style>
    /* ── Entry: every step fades up on load ─────────────────────────────── */
    @keyframes cs-fadeUp {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0);    }
    }
    .block-container {
        animation: cs-fadeUp 280ms cubic-bezier(0.23, 1, 0.32, 1) both;
    }

    /* ── Buttons: lift on hover, press scale ─────────────────────────────── */
    .stButton > button {
        transition: transform 150ms cubic-bezier(0.23, 1, 0.32, 1),
                    box-shadow 150ms cubic-bezier(0.23, 1, 0.32, 1);
    }
    @media (hover: hover) and (pointer: fine) {
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.10);
        }
    }
    .stButton > button:active {
        transform: scale(0.97);
        box-shadow: none;
    }

    /* ── Metrics: staggered fade-in ──────────────────────────────────────── */
    @keyframes cs-fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0);   }
    }
    [data-testid="metric-container"] {
        animation: cs-fadeIn 240ms cubic-bezier(0.23, 1, 0.32, 1) both;
    }
    div[data-testid="column"]:nth-child(1) [data-testid="metric-container"] { animation-delay:   0ms; }
    div[data-testid="column"]:nth-child(2) [data-testid="metric-container"] { animation-delay:  60ms; }
    div[data-testid="column"]:nth-child(3) [data-testid="metric-container"] { animation-delay: 120ms; }
    div[data-testid="column"]:nth-child(4) [data-testid="metric-container"] { animation-delay: 180ms; }

    /* ── Alerts/banners: slide down ──────────────────────────────────────── */
    @keyframes cs-slideDown {
        from { opacity: 0; transform: translateY(-6px); }
        to   { opacity: 1; transform: translateY(0);    }
    }
    .stAlert {
        animation: cs-slideDown 200ms cubic-bezier(0.23, 1, 0.32, 1) both;
    }

    /* ── DataFrames: soft fade in ────────────────────────────────────────── */
    .stDataFrame {
        animation: cs-fadeIn 220ms cubic-bezier(0.23, 1, 0.32, 1) both;
    }

    /* ── Expanders: smooth header transition ─────────────────────────────── */
    details > summary {
        transition: background-color 150ms ease;
    }

    /* ── Unique-value chips ───────────────────────────────────────────────── */
    .cs-chips-row { line-height: 2.2; margin-bottom: 6px; }
    .cs-col-name  {
        font-size: 0.80rem; font-weight: 600; color: #4a5568;
        margin-bottom: 2px; margin-top: 10px;
    }
    .cs-chip {
        display: inline-block;
        background: rgba(49, 130, 206, 0.07);
        border: 1px solid rgba(49, 130, 206, 0.18);
        border-radius: 5px;
        padding: 1px 7px;
        font-size: 0.76rem;
        margin: 2px 3px 2px 0;
        color: #2b6cb0;
        font-family: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
        animation: cs-fadeIn 200ms cubic-bezier(0.23, 1, 0.32, 1) both;
    }
    .cs-more {
        font-size: 0.76rem; color: #a0aec0; font-style: italic; margin-left: 4px;
    }
    </style>
    """, unsafe_allow_html=True)


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
            return pd.read_csv(uploaded_file, encoding=enc, keep_default_na=False, na_values=[''])
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
    st.subheader("First 5 Rows")
    st.caption("A quick look at what your data contains.")
    st.dataframe(df.head(5), use_container_width=True)

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

    styled = summary_df.style.map(color_null_pct, subset=['Null %'])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Section D — Unique values per column
    st.subheader("Unique Values per Column")
    st.caption("Up to 8 shown inline; click to expand the rest.")
    for col in df.columns:
        unique_vals = df[col].dropna().unique()
        n = len(unique_vals)
        first_8 = unique_vals[:8]
        chips_8 = "".join(
            f'<span class="cs-chip">{str(v)[:40]}</span>' for v in first_8
        )
        if n > 8:
            remaining = n - 8
            label = f"{col}  ·  {n:,} unique  — click to expand"
            with st.expander(label):
                all_vals = unique_vals[:300]
                chips_all = "".join(
                    f'<span class="cs-chip">{str(v)[:40]}</span>' for v in all_vals
                )
                suffix = (
                    f'<span class="cs-more">…and {n - 300:,} more not shown</span>'
                    if n > 300 else ""
                )
                st.markdown(
                    f'<div class="cs-chips-row">{chips_all}{suffix}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div class="cs-col-name">{col}</div>'
                f'<div class="cs-chips-row">{chips_8}</div>',
                unsafe_allow_html=True,
            )

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
        from utils.scanner import find_zero_columns

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

        # Pre-compute zero columns for Step 4
        st.session_state.zero_cols = find_zero_columns(df)

        st.session_state.stage = 'nulls'
        st.rerun()


def show_nulls():
    df = st.session_state.working_df

    st.header("🔍 Step 3 of 7: Hidden Missing Values")
    st.caption(
        "We'll scan every column for values that look like missing data but aren't "
        "being read as null yet."
    )

    from utils.scanner import find_disguised_nulls, find_type_mismatch_nulls
    from utils.audit import save_snapshot, log_action
    from utils.cleaner import replace_disguised_nulls_in_column

    # ── Tier 3: Custom null values (user input) ───────────────────────────────
    st.subheader("Custom Null Values")
    st.caption("Are there values specific to your dataset that should be treated as missing? Enter them separated by commas.")
    custom_input = st.text_input(
        "Additional null values (comma-separated):",
        key="custom_null_input",
        placeholder="e.g. 999, N.A., not available",
    )
    extra_values = [v.strip() for v in custom_input.split(",") if v.strip()] if custom_input else []

    # ── Tier 1: Standard null patterns (+ user custom values) ─────────────────
    tier1 = find_disguised_nulls(df, extra_values=extra_values)

    # ── Tier 2: Type mismatch — strings in numeric columns ────────────────────
    tier2_raw = find_type_mismatch_nulls(df)
    # Exclude anything already caught by Tier 1
    tier2 = {}
    for col, vals in tier2_raw.items():
        already_caught = set(tier1.get(col, []))
        remaining = [v for v in vals if v not in already_caught]
        if remaining:
            tier2[col] = remaining

    has_findings = bool(tier1) or bool(tier2)

    if not has_findings:
        st.success("✅ No hidden null values detected.")
        if st.button("Next →", type="primary"):
            st.session_state.stage = 'zeros'
            st.rerun()
        return

    # ── Tier 1 display ────────────────────────────────────────────────────────
    if tier1:
        st.subheader("🔴 Standard Null Patterns Found")
        st.caption("These match a known list of null indicators (e.g. 'na', 'N/A', '?', 'none').")
        rows = []
        for col, values in tier1.items():
            for val in values:
                count = int((df[col] == val).sum())
                rows.append({'Column': col, 'Value': repr(val), 'Count': count})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Tier 2 display with checkboxes ────────────────────────────────────────
    tier2_confirmed = {}
    if tier2:
        st.subheader("🟡 Possible Suspects — Strings Inside Numeric Columns")
        st.caption(
            "These text values appear in columns that are mostly numeric. "
            "They may be disguised nulls — check the ones you want to treat as missing."
        )
        for col, values in tier2.items():
            st.markdown(f"**{col}**")
            confirmed_vals = []
            for val in values:
                count = int((df[col] == val).sum())
                pct = count / len(df) * 100
                checked = st.checkbox(
                    f"`{repr(val)}` — {count} occurrence{'s' if count != 1 else ''} ({pct:.1f}%)",
                    key=f"tier2_{col}_{repr(val)}",
                )
                if checked:
                    confirmed_vals.append(val)
            if confirmed_vals:
                tier2_confirmed[col] = confirmed_vals

    # ── Merge tiers into combined dict ────────────────────────────────────────
    combined = {}
    for col, vals in tier1.items():
        combined[col] = list(vals)
    for col, vals in tier2_confirmed.items():
        if col in combined:
            combined[col] = list(set(combined[col]) | set(vals))
        else:
            combined[col] = list(vals)

    if not combined:
        st.info("No values selected for replacement. Tick checkboxes above or continue.")
        if st.button("Skip this step →", key="skip_nulls", type="primary"):
            st.session_state.stage = 'zeros'
            st.rerun()
        return

    # ── Example rows ──────────────────────────────────────────────────────────
    st.subheader("Example rows with these values")
    all_masks = [df[col].isin(vals) for col, vals in combined.items()]
    combined_mask = all_masks[0]
    for m in all_masks[1:]:
        combined_mask = combined_mask | m
    st.dataframe(df[combined_mask].head(3), use_container_width=True)

    # ── Options ───────────────────────────────────────────────────────────────
    st.divider()
    choice = st.radio(
        "Treat all selected values as missing (NaN)?",
        [
            "✅ Yes — treat all as missing (Recommended)",
            "❌ No — they are valid text",
            "🔍 Decide per column",
        ],
        index=0,
    )

    if st.button("Apply", type="primary"):
        if choice.startswith("✅"):
            save_snapshot(df)
            total_affected = 0
            for col, values in combined.items():
                new_df, affected, details = replace_disguised_nulls_in_column(
                    st.session_state.working_df, col, values
                )
                st.session_state.working_df = new_df
                total_affected += affected
                log_action(
                    phase='disguised_nulls', column=col,
                    issue=f'Found disguised nulls: {values}',
                    decision='Replaced with NaN',
                    rows_affected=affected,
                    method='replace_disguised_nulls',
                    details={'values_replaced': values},
                )
            st.success(f"Done. {total_affected} values now correctly read as null.")
            st.session_state.stage = 'zeros'
            st.rerun()

        elif choice.startswith("❌"):
            st.session_state.stage = 'zeros'
            st.rerun()

        elif choice.startswith("🔍"):
            st.session_state._nulls_per_column = True
            st.rerun()

    # Per-column mode
    if st.session_state.get('_nulls_per_column'):
        save_snapshot(df)
        for col, values in combined.items():
            with st.container():
                st.markdown(f"**{col}** — found: {values}")
                st.radio(
                    f"Replace in {col}?",
                    ["Yes — treat as missing", "No — keep as valid"],
                    key=f"null_choice_{col}",
                )

        if st.button("Confirm all per-column choices", key="confirm_per_col"):
            for col, values in combined.items():
                col_choice = st.session_state.get(f"null_choice_{col}", "Yes — treat as missing")
                if col_choice.startswith("Yes"):
                    new_df, affected, details = replace_disguised_nulls_in_column(
                        st.session_state.working_df, col, values
                    )
                    st.session_state.working_df = new_df
                    log_action(
                        phase='disguised_nulls', column=col,
                        issue=f'Found disguised nulls: {values}',
                        decision='Replaced with NaN',
                        rows_affected=affected,
                        method='replace_disguised_nulls',
                        details={'values_replaced': values},
                    )
            st.session_state._nulls_per_column = False
            st.session_state.stage = 'zeros'
            st.rerun()


def show_zeros():
    df = st.session_state.working_df
    zero_cols = st.session_state.zero_cols

    st.header("🔍 Step 4 of 7: Zero Values")

    if not zero_cols:
        st.success("✅ No zeros found in numeric columns (excluding boolean flags).")
        if st.button("Next →", type="primary"):
            st.session_state.stage = 'missing_bulk'
            st.rerun()
        return

    st.caption("Zeros can be legitimate or they can mean missing data recorded as zero. Only you know which.")

    # Initialize tracking
    if '_zero_col_idx' not in st.session_state:
        st.session_state._zero_col_idx = 0

    idx = st.session_state._zero_col_idx

    if idx >= len(zero_cols):
        st.success("Zero check complete.")
        if st.button("Continue to Missing Values →", type="primary"):
            del st.session_state._zero_col_idx
            st.session_state.stage = 'missing_bulk'
            st.rerun()
        return

    col = zero_cols[idx]
    numeric_col = pd.to_numeric(df[col], errors='coerce')
    zero_mask = numeric_col == 0
    zero_count = int(zero_mask.sum())
    non_zero = numeric_col[numeric_col != 0].dropna()

    st.subheader(f"Column: {col}")
    st.markdown(f"**Zeros found:** {zero_count} rows")
    if len(non_zero) > 0:
        st.markdown(f"**Non-zero range:** {non_zero.min():.2f} → {non_zero.max():.2f}")
        st.markdown(f"**Mean (excluding zeros):** {non_zero.mean():.2f}")

    st.markdown("**Rows with zero:**")
    st.dataframe(df[zero_mask].head(10), use_container_width=True)

    st.divider()
    st.markdown("**Is zero a valid value here?**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ No — treat zeros as missing", key=f"zero_missing_{col}"):
            from utils.audit import save_snapshot, log_action
            from utils.cleaner import replace_zeros_with_nan

            save_snapshot(df)
            new_df, affected, details = replace_zeros_with_nan(df, col)
            st.session_state.working_df = new_df
            log_action(
                phase='zeros', column=col,
                issue=f'{zero_count} zeros found',
                decision='Replaced zeros with NaN',
                rows_affected=affected,
                method='zero_as_missing',
                details={},
            )
            st.session_state._zero_col_idx += 1
            st.rerun()
    with c2:
        if st.button("✅ Yes — zero is legitimate", key=f"zero_valid_{col}"):
            from utils.audit import log_action

            log_action(
                phase='zeros', column=col,
                issue=f'{zero_count} zeros found',
                decision='Zeros confirmed as valid',
                rows_affected=0,
                method='zero_kept_valid',
                details={},
            )
            st.session_state._zero_col_idx += 1
            st.rerun()


def show_missing_bulk():
    df = st.session_state.working_df

    st.header("🧹 Step 5 of 7: Missing Values")

    # Recompute missingness
    from utils.scanner import get_fully_empty_columns, get_high_missingness_rows

    total_missing = int(df.isna().sum().sum())
    total_cells = df.shape[0] * df.shape[1]
    cols_with_missing = [c for c in df.columns if df[c].isna().any()]

    # Opening summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rows", f"{len(df):,}")
    c2.metric("Columns with Missing", str(len(cols_with_missing)))
    c3.metric("Missing Cells", f"{total_missing:,} ({total_missing/total_cells*100:.1f}%)" if total_cells > 0 else "0")

    if total_missing == 0:
        st.success("🎉 No missing values found! Nothing to clean here.")
        if st.button("Continue →", type="primary"):
            st.session_state.stage = 'type_convert'
            st.rerun()
        return

    # Horizontal bars per column
    st.subheader("Missing values by column")
    for col in cols_with_missing:
        pct = df[col].isna().sum() / len(df) * 100
        if pct < 1:
            color = "green"
        elif pct <= 10:
            color = "orange"
        else:
            color = "red"
        st.markdown(f"**{col}**: {pct:.1f}% missing")
        st.progress(min(pct / 100, 1.0))

    # Fully empty columns
    empty_cols = get_fully_empty_columns(df)
    if empty_cols:
        st.divider()
        st.warning(f"⚠️ {len(empty_cols)} columns are entirely empty. Imputation is not possible.")
        from utils.audit import save_snapshot, log_action
        from utils.cleaner import drop_column

        for col in empty_cols:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{col}** — 100% empty")
            with c2:
                if st.button(f"Drop {col}", key=f"drop_empty_{col}"):
                    save_snapshot(df)
                    new_df, affected, details = drop_column(st.session_state.working_df, col)
                    st.session_state.working_df = new_df
                    log_action(
                        phase='missing', column=col,
                        issue='Column 100% empty',
                        decision='Dropped column',
                        rows_affected=affected,
                        method='drop_empty_column',
                        details=details,
                    )
                    st.rerun()

    # High-missingness rows
    st.divider()
    st.subheader("Row-level missingness")
    threshold = st.number_input(
        "Drop rows with more than X% of columns missing:",
        min_value=0, max_value=100, value=30, step=5,
        help="Rows where this percentage of column values are missing will be dropped."
    )
    threshold_frac = threshold / 100.0
    high_miss_rows = get_high_missingness_rows(df, threshold_frac)

    if len(high_miss_rows) > 0:
        st.warning(f"⚠️ {len(high_miss_rows)} rows have {threshold}%+ of columns missing.")
        st.dataframe(df.loc[high_miss_rows].head(20), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Drop these rows (Recommended)", type="primary", key="drop_high_miss"):
                from utils.audit import save_snapshot, log_action
                from utils.cleaner import drop_rows_by_index

                save_snapshot(df)
                new_df, affected, details = drop_rows_by_index(df, high_miss_rows)
                st.session_state.working_df = new_df
                log_action(
                    phase='missing', column='*',
                    issue=f'{len(high_miss_rows)} rows with {threshold}%+ missing',
                    decision='Dropped high-missingness rows',
                    rows_affected=affected,
                    method='drop_rows_high_missingness',
                    details={'threshold': threshold_frac},
                )
                st.rerun()
        with c2:
            if st.button("Keep them", key="keep_high_miss"):
                pass  # Do nothing, user continues
    else:
        st.success(f"✅ No rows have {threshold}%+ of columns missing.")

    # Duplicate info note
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        st.info(f"💡 You have {dup_count:,} duplicate rows. These will be handled in Step 7.")

    # Continue button
    st.divider()
    if st.button("Continue to column-by-column cleanup →", type="primary"):
        # Recompute columns with missing values
        working = st.session_state.working_df
        missing_cols = [c for c in working.columns if working[c].isna().any()]
        missing_cols.sort(key=lambda c: working[c].isna().sum())  # ascending
        st.session_state.missing_value_cols = missing_cols
        st.session_state.current_col_idx = 0
        st.session_state.stage = 'missing_columns'
        st.rerun()


def show_missing_columns():
    df = st.session_state.working_df
    missing_cols = st.session_state.missing_value_cols
    idx = st.session_state.current_col_idx

    st.header("🧹 Step 5 of 7: Missing Values")

    # Recompute — some columns may no longer have missing after bulk cleanup
    missing_cols = [c for c in missing_cols if c in df.columns and df[c].isna().any()]
    st.session_state.missing_value_cols = missing_cols

    if idx >= len(missing_cols) or len(missing_cols) == 0:
        skipped = st.session_state.skipped_cols
        remaining = int(df.isna().sum().sum())
        if remaining == 0:
            st.success("🎉 All missing values resolved!")
        else:
            st.info(f"{remaining} missing values remain in {len(skipped)} intentionally skipped columns: {', '.join(skipped)}")
        if st.button("Proceed to Type Conversion →", type="primary"):
            st.session_state.stage = 'type_convert'
            st.rerun()
        return

    col = missing_cols[idx]
    total = len(missing_cols)
    contract = st.session_state.column_contracts.get(col, {})
    col_type = contract.get('intended_type', 'Text')

    st.progress((idx) / total)
    st.caption(f"Column {idx + 1} of {total} with missing values")

    missing_count = int(df[col].isna().sum())
    missing_pct = missing_count / len(df) * 100

    st.subheader(f"Column: {col}")
    st.markdown(f"**Confirmed Type:** {col_type}")
    st.markdown(f"**Missing:** {missing_count} rows ({missing_pct:.1f}%)")

    # Type-relevant stats
    non_null = df[col].dropna()
    if col_type == 'Continuous Number':
        numeric_vals = pd.to_numeric(non_null, errors='coerce').dropna()
        if len(numeric_vals) > 0:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Min", f"{numeric_vals.min():.2f}")
            c2.metric("Max", f"{numeric_vals.max():.2f}")
            c3.metric("Mean", f"{numeric_vals.mean():.2f}")
            c4.metric("Median", f"{numeric_vals.median():.2f}")
            c5.metric("Std Dev", f"{numeric_vals.std():.2f}")
    elif col_type == 'Category':
        st.markdown(f"**Unique values:** {non_null.nunique()}")
        counts = non_null.value_counts().head(5)
        st.dataframe(counts.reset_index(), use_container_width=True, hide_index=True)
    elif col_type == 'Date / Time':
        dates = pd.to_datetime(non_null, errors='coerce').dropna()
        if len(dates) > 0:
            c1, c2, c3 = st.columns(3)
            c1.metric("Earliest", str(dates.min().date()))
            c2.metric("Latest", str(dates.max().date()))
            c3.metric("Median", str(dates.median().date()) if len(dates) > 0 else "N/A")

    # Show missing rows
    st.markdown("**Rows with missing values (max 10):**")
    st.dataframe(df[df[col].isna()].head(10), use_container_width=True)

    # Options by type
    st.divider()
    st.markdown("**What would you like to do?**")

    from utils.audit import save_snapshot, log_action
    from utils.cleaner import (
        impute_mean, impute_median, impute_mode, impute_group_median,
        impute_custom, impute_marker, impute_date, drop_rows_by_index,
    )

    def _apply_and_advance(new_df, affected, method, decision, details=None):
        st.session_state.working_df = new_df
        log_action(
            phase='missing', column=col,
            issue=f'{missing_count} missing values',
            decision=decision,
            rows_affected=affected,
            method=method,
            details=details or {},
        )
        st.session_state._show_preview = {
            'col': col, 'before': missing_count, 'after': int(new_df[col].isna().sum()),
        }
        st.rerun()

    if col_type == 'Continuous Number':
        numeric_vals = pd.to_numeric(non_null, errors='coerce').dropna()
        mean_val = numeric_vals.mean() if len(numeric_vals) > 0 else 0
        median_val = numeric_vals.median() if len(numeric_vals) > 0 else 0

        # Skew warning
        if len(numeric_vals) > 0 and median_val != 0:
            if abs(mean_val - median_val) / abs(median_val) > 0.5:
                direction = 'right' if mean_val > median_val else 'left'
                st.warning(f"⚠️ This column is {direction}-skewed. Median may be more reliable.")

        option = st.radio("Choose:", [
            f"A) Drop these rows (dataset: {len(df):,} → {len(df) - missing_count:,} rows)",
            f"B) Fill with mean ({mean_val:.2f})",
            f"C) Fill with median ({median_val:.2f})",
            "D) Fill with group median",
            "E) Fill with custom value",
            "F) Leave for now",
        ], key=f"opt_{col}")

        # Group median config
        group_cols = []
        if option.startswith("D)"):
            other_cols = [c for c in df.columns if c != col]
            group_cols = st.multiselect("Group by which columns?", other_cols, key=f"group_{col}")
            if group_cols:
                # Guardrail: check for small groups
                group_sizes = df.groupby(
                    [df[gc].fillna('__MISSING__').astype(str) for gc in group_cols]
                )[col].apply(lambda x: x.notna().sum())
                small = int((group_sizes < 3).sum())
                if small > 0:
                    st.warning(f"⚠️ {small} groups have fewer than 3 observations. Those fills may be unreliable.")

        custom_val = None
        if option.startswith("E)"):
            custom_val = st.number_input("Enter value:", key=f"custom_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option.startswith("A)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows with missing values')
            elif option.startswith("B)"):
                new_df, affected, details = impute_mean(df, col)
                _apply_and_advance(new_df, affected, 'impute_mean', f'Filled with mean ({mean_val:.2f})', details)
            elif option.startswith("C)"):
                new_df, affected, details = impute_median(df, col)
                _apply_and_advance(new_df, affected, 'impute_median', f'Filled with median ({median_val:.2f})', details)
            elif option.startswith("D)") and group_cols:
                new_df, affected, details = impute_group_median(df, col, group_cols)
                _apply_and_advance(new_df, affected, 'impute_group_median', 'Filled with group median', details)
                if details.get('fallback_fills', 0) > 0:
                    log_action(
                        phase='missing', column=col,
                        issue='Group median fallback',
                        decision='Filled remaining with global median',
                        rows_affected=details['fallback_fills'],
                        method='impute_group_median_fallback',
                        details={'global_median': details['global_median']},
                    )
            elif option.startswith("E)") and custom_val is not None:
                new_df, affected, details = impute_custom(df, col, custom_val)
                _apply_and_advance(new_df, affected, 'impute_custom_value', f'Filled with {custom_val}', details)
            elif option.startswith("F)"):
                st.session_state.skipped_cols.append(col)
                log_action(
                    phase='missing', column=col,
                    issue=f'{missing_count} missing values',
                    decision='Left for now',
                    rows_affected=0, method='skip_column', details={},
                )
                st.session_state.current_col_idx += 1
                st.rerun()

    elif col_type in ('Category', 'Continuous Number' if False else 'Category'):
        mode_val = non_null.mode().iloc[0] if len(non_null) > 0 else 'N/A'
        mode_count = int((non_null == mode_val).sum()) if len(non_null) > 0 else 0

        option = st.radio("Choose:", [
            f"A) Fill with mode — most common: '{mode_val}' ({mode_count} times)",
            "B) Fill with custom category",
            f"C) Drop these rows (dataset: {len(df):,} → {len(df) - missing_count:,})",
            "D) Mark as 'Unknown'",
            "E) Leave for now",
        ], key=f"opt_{col}")

        custom_cat = None
        if option.startswith("B)"):
            custom_cat = st.text_input("Enter category:", key=f"custom_cat_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option.startswith("A)"):
                new_df, affected, details = impute_mode(df, col)
                _apply_and_advance(new_df, affected, 'impute_mode', f'Filled with mode ({mode_val})', details)
            elif option.startswith("B)") and custom_cat:
                new_df, affected, details = impute_custom(df, col, custom_cat)
                _apply_and_advance(new_df, affected, 'impute_custom_value', f'Filled with {custom_cat}', details)
            elif option.startswith("C)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option.startswith("D)"):
                new_df, affected, details = impute_marker(df, col, 'Unknown')
                _apply_and_advance(new_df, affected, 'impute_marker_unknown', 'Marked as Unknown', details)
            elif option.startswith("E)"):
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    elif col_type == 'Date / Time':
        dates = pd.to_datetime(non_null, errors='coerce').dropna()
        option = st.radio("Choose:", [
            "A) Drop these rows",
            f"B) Fill with most recent date ({dates.max().date() if len(dates) > 0 else 'N/A'})",
            f"C) Fill with oldest date ({dates.min().date() if len(dates) > 0 else 'N/A'})",
            "D) Fill with median date",
            "E) Custom date",
            "F) Leave for now",
        ], key=f"opt_{col}")

        custom_date = None
        if option.startswith("E)"):
            custom_date = st.date_input("Enter date:", key=f"custom_date_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            # Ensure column is datetime for imputation
            df_work = st.session_state.working_df.copy()
            df_work[col] = pd.to_datetime(df_work[col], errors='coerce')
            st.session_state.working_df = df_work

            if option.startswith("A)"):
                idx_to_drop = df_work[df_work[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df_work, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option.startswith("B)"):
                new_df, affected, details = impute_date(df_work, col, 'most_recent')
                _apply_and_advance(new_df, affected, 'impute_most_recent_date', 'Filled with most recent', details)
            elif option.startswith("C)"):
                new_df, affected, details = impute_date(df_work, col, 'oldest')
                _apply_and_advance(new_df, affected, 'impute_oldest_date', 'Filled with oldest', details)
            elif option.startswith("D)"):
                new_df, affected, details = impute_date(df_work, col, 'median')
                _apply_and_advance(new_df, affected, 'impute_median_date', 'Filled with median', details)
            elif option.startswith("E)") and custom_date:
                new_df, affected, details = impute_date(df_work, col, 'custom', custom_date=custom_date)
                _apply_and_advance(new_df, affected, 'impute_median_date', f'Filled with {custom_date}', details)
            elif option.startswith("F)"):
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    elif col_type in ('ID / Identifier', 'Boolean'):
        option = st.radio("Choose:", [
            f"A) Drop these rows",
            "B) Mark as 'Unknown'" if col_type == 'ID / Identifier' else None,
            "C) Leave for now",
        ], key=f"opt_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option and option.startswith("A)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option and option.startswith("B)"):
                new_df, affected, details = impute_marker(df, col, 'Unknown')
                _apply_and_advance(new_df, affected, 'impute_marker_unknown', 'Marked as Unknown', details)
            else:
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    else:  # Free Text
        option = st.radio("Choose:", [
            "A) Drop these rows",
            "B) Fill with empty string",
            "C) Mark as 'Unknown'",
            "D) Leave for now",
        ], key=f"opt_{col}")

        if st.button("Apply", key=f"apply_{col}", type="primary"):
            save_snapshot(df)
            if option.startswith("A)"):
                idx_to_drop = df[df[col].isna()].index
                new_df, affected, details = drop_rows_by_index(df, idx_to_drop)
                _apply_and_advance(new_df, affected, 'drop_rows_column_missing', 'Dropped rows')
            elif option.startswith("B)"):
                new_df, affected, details = impute_custom(df, col, '')
                _apply_and_advance(new_df, affected, 'impute_custom_value', 'Filled with empty string', details)
            elif option.startswith("C)"):
                new_df, affected, details = impute_marker(df, col, 'Unknown')
                _apply_and_advance(new_df, affected, 'impute_marker_unknown', 'Marked as Unknown', details)
            else:
                st.session_state.skipped_cols.append(col)
                log_action(phase='missing', column=col, issue=f'{missing_count} missing',
                           decision='Left for now', rows_affected=0, method='skip_column', details={})
                st.session_state.current_col_idx += 1
                st.rerun()

    # Preview after action (shown on rerun)
    preview = st.session_state.get('_show_preview')
    if preview and preview['col'] == col:
        st.divider()
        st.success(f"✅ Done. Before: {preview['before']} missing | After: {preview['after']} missing")
        st.markdown("**Sample of updated column:**")
        st.dataframe(st.session_state.working_df[[col]].head(5), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✓ Looks good — next column →", key="next_col"):
                st.session_state.current_col_idx += 1
                del st.session_state._show_preview
                st.rerun()
        with c2:
            if st.session_state.undo_enabled:
                if st.button("↩ Undo — let me reconsider", key="undo_col"):
                    from utils.audit import undo
                    undo()
                    del st.session_state._show_preview
                    st.rerun()


def show_type_conversion():
    df = st.session_state.working_df
    contracts = st.session_state.column_contracts

    st.header("🔄 Step 6 of 7: Apply Data Types")
    st.caption("Now that missing values are handled, let's convert columns to their confirmed types.")

    from utils.cleaner import apply_type_conversion
    from utils.audit import save_snapshot, log_action

    type_to_dtype = {
        'Continuous Number': 'numeric',
        'Category': 'category',
        'Date / Time': 'datetime',
        'Boolean': 'bool',
        'Text': 'object',
        'ID / Identifier': 'object',
    }

    # Assess which columns need conversion
    conversion_status = []
    for col in df.columns:
        if col not in contracts:
            continue
        intended = contracts[col]['intended_type']
        current = str(df[col].dtype)
        target_dtype = type_to_dtype.get(intended, 'object')

        needs_conversion = True
        if intended in ('Text', 'ID / Identifier') and current == 'object':
            needs_conversion = False
        elif intended == 'Continuous Number' and pd.api.types.is_numeric_dtype(df[col]):
            needs_conversion = False
        elif intended == 'Category' and current == 'category':
            needs_conversion = False
        elif intended == 'Date / Time' and pd.api.types.is_datetime64_any_dtype(df[col]):
            needs_conversion = False
        elif intended == 'Boolean' and current == 'bool':
            needs_conversion = False

        # Check if conversion might lose data
        may_lose = False
        if needs_conversion and intended == 'Continuous Number':
            test = pd.to_numeric(df[col], errors='coerce')
            losses = int(df[col].notna().sum() - test.notna().sum())
            if losses > 0:
                may_lose = True

        status = '✅ Already correct' if not needs_conversion else ('⚠️ May lose data' if may_lose else '🔄 Needs conversion')
        conversion_status.append({
            'Column': col,
            'Current': current,
            'Intended': intended,
            'Status': status,
            'needs_conversion': needs_conversion,
        })

    status_df = pd.DataFrame(conversion_status)
    st.dataframe(status_df[['Column', 'Current', 'Intended', 'Status']], use_container_width=True, hide_index=True)

    needs_work = [r for r in conversion_status if r['needs_conversion']]

    if not needs_work:
        st.success("✅ All columns already match their confirmed types.")
        if st.button("Continue to Duplicates →", type="primary"):
            st.session_state.stage = 'duplicates'
            st.rerun()
        return

    st.divider()
    st.markdown(f"**{len(needs_work)} columns need conversion.**")

    option = st.radio("How would you like to proceed?", [
        "✅ Apply all conversions (Recommended)",
        "🔍 Review one by one",
    ])

    if option.startswith("✅"):
        if st.button("Apply All", type="primary"):
            save_snapshot(df)
            for item in needs_work:
                col = item['Column']
                intended = contracts[col]['intended_type']
                new_df, affected, details = apply_type_conversion(
                    st.session_state.working_df, col, intended
                )
                st.session_state.working_df = new_df
                log_action(
                    phase='type_convert', column=col,
                    issue=f'Convert from {item["Current"]} to {intended}',
                    decision=f'Converted to {intended}',
                    rows_affected=affected,
                    method='type_conversion',
                    details=details,
                )
                if details.get('coercion_losses', 0) > 0:
                    st.warning(f"⚠️ {col}: {details['coercion_losses']} values could not be converted and became NaN.")
            st.success("All conversions applied.")
            st.session_state.stage = 'duplicates'
            st.rerun()

    else:
        for item in needs_work:
            col = item['Column']
            intended = contracts[col]['intended_type']
            with st.expander(f"{col}: {item['Current']} → {intended}"):
                # Preview
                st.markdown("**First 5 values that would change:**")
                sample = df[col].dropna().head(5)
                st.dataframe(sample, use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"Apply", key=f"convert_{col}"):
                        save_snapshot(df)
                        new_df, affected, details = apply_type_conversion(
                            st.session_state.working_df, col, intended
                        )
                        st.session_state.working_df = new_df
                        log_action(
                            phase='type_convert', column=col,
                            issue=f'Convert to {intended}',
                            decision=f'Converted to {intended}',
                            rows_affected=affected,
                            method='type_conversion',
                            details=details,
                        )
                        st.rerun()
                with c2:
                    if st.button(f"Skip", key=f"skip_convert_{col}"):
                        log_action(
                            phase='type_convert', column=col,
                            issue=f'Convert to {intended}',
                            decision='Skipped',
                            rows_affected=0,
                            method='type_conversion_skipped',
                            details={},
                        )

        st.divider()
        if st.button("Continue to Duplicates →", type="primary"):
            st.session_state.stage = 'duplicates'
            st.rerun()


def show_duplicates():
    df = st.session_state.working_df

    st.header("🔍 Step 7 of 7: Duplicate Rows")

    dup_count = int(df.duplicated().sum())

    if dup_count == 0:
        st.success("✅ No duplicate rows found. Your data is clean.")
        if st.button("Finish →", type="primary"):
            st.session_state.stage = 'done'
            st.rerun()
        return

    st.markdown(f"We found **{dup_count:,}** rows that appear more than once.")

    # Show duplicates
    dup_mask = df.duplicated(keep=False)
    dup_rows = df[dup_mask].sort_values(by=list(df.columns))
    st.dataframe(dup_rows.head(20), use_container_width=True)

    st.divider()
    option = st.radio("What would you like to do?", [
        "Remove duplicates — keep first (Recommended)",
        "Remove duplicates — keep last",
        "Keep all — duplicates are intentional",
    ])

    if st.button("Apply", type="primary"):
        from utils.audit import save_snapshot, log_action
        from utils.cleaner import remove_duplicates

        if option.startswith("Remove") and "first" in option:
            save_snapshot(df)
            new_df, affected, details = remove_duplicates(df, keep='first')
            st.session_state.working_df = new_df
            log_action(
                phase='duplicates', column='*',
                issue=f'{dup_count} duplicate rows',
                decision='Removed duplicates, kept first',
                rows_affected=affected,
                method='remove_duplicates_keep_first',
                details=details,
            )
        elif option.startswith("Remove") and "last" in option:
            save_snapshot(df)
            new_df, affected, details = remove_duplicates(df, keep='last')
            st.session_state.working_df = new_df
            log_action(
                phase='duplicates', column='*',
                issue=f'{dup_count} duplicate rows',
                decision='Removed duplicates, kept last',
                rows_affected=affected,
                method='remove_duplicates_keep_last',
                details=details,
            )
        else:
            log_action(
                phase='duplicates', column='*',
                issue=f'{dup_count} duplicate rows',
                decision='Kept all duplicates',
                rows_affected=0,
                method='keep_duplicates',
                details={},
            )

        st.session_state.stage = 'done'
        st.rerun()


def show_completion():
    df = st.session_state.working_df
    original = st.session_state.original_df

    st.header("🎉 Your Data is Clean")

    # Before vs After
    st.subheader("Before vs After")

    orig_missing = int(original.isna().sum().sum())
    clean_missing = int(df.isna().sum().sum())
    orig_dupes = int(original.duplicated().sum())
    clean_dupes = int(df.duplicated().sum())

    # Count disguised nulls resolved from audit log
    disguised_resolved = sum(
        e['rows_affected'] for e in st.session_state.audit_log
        if e['method'] == 'replace_disguised_nulls'
    )

    comparison = pd.DataFrame({
        '': ['Rows', 'Columns', 'Missing cells', 'Duplicates', 'Disguised nulls resolved'],
        'Before': [f"{len(original):,}", str(len(original.columns)),
                    f"{orig_missing:,}", f"{orig_dupes:,}", "0"],
        'After': [f"{len(df):,}", str(len(df.columns)),
                   f"{clean_missing:,}", f"{clean_dupes:,}", f"{disguised_resolved:,}"],
        'Change': [
            f"{len(df) - len(original):,}",
            str(len(df.columns) - len(original.columns)),
            f"{clean_missing - orig_missing:,}",
            f"{clean_dupes - orig_dupes:,}",
            f"+{disguised_resolved:,}",
        ],
    })
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    # Full Audit Log
    st.subheader("Full Audit Log")
    log = st.session_state.audit_log
    if log:
        log_df = pd.DataFrame(log)
        st.dataframe(log_df, use_container_width=True, hide_index=True)

    # Downloads
    st.subheader("Download")
    import io

    c1, c2 = st.columns(2)
    with c1:
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        base_name = st.session_state.filename.rsplit('.', 1)[0]
        st.download_button(
            "⬇ Download Clean CSV",
            csv_buf.getvalue(),
            file_name=f"clean_{base_name}.csv",
            mime="text/csv",
            type="primary",
        )
    with c2:
        if log:
            log_buf = io.StringIO()
            pd.DataFrame(log).to_csv(log_buf, index=False)
            st.download_button(
                "⬇ Download Audit Log CSV",
                log_buf.getvalue(),
                file_name=f"auditlog_{base_name}.csv",
                mime="text/csv",
            )

    # Reproducibility Recipe
    st.subheader("Reproducibility Recipe")
    with st.expander("📋 View the cleaning recipe (pandas code)"):
        from utils.recipe import generate_recipe
        recipe_code = generate_recipe(log, st.session_state.filename)
        st.code(recipe_code, language='python')

    # Reset
    st.divider()
    if st.button("🔄 Clean another file"):
        from utils.state import reset_session_state
        reset_session_state()
        st.rerun()


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


inject_css()

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
