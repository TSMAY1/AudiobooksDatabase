import streamlit as st

st.set_page_config(page_title="Audiobook Library", layout="wide")

st.title("📚 Audiobook Library")
st.markdown(
    """
    Welcome to your audiobook database interface.

    Use the sidebar to navigate:
    - Library
    - Add Book
    - Reading Status
    - Genres
    - Analytics
    """
)