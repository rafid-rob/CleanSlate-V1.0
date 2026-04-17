import streamlit as st
from utils.state import init_session_state

st.set_page_config(page_title="CleanSlate", page_icon="🧹", layout="wide")

init_session_state()


def show_upload():
    st.title("CleanSlate")
    st.caption("Understand your data. Clean it together.")
    st.info("Upload phase — to be implemented.")


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
