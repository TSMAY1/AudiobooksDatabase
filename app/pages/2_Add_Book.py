import streamlit as st
from db import execute_procedure

st.title("➕ Add Book")

if "is_standalone" not in st.session_state:
    st.session_state.is_standalone = True

if "series_name_input" not in st.session_state:
    st.session_state.series_name_input = "Standalone"


def handle_standalone_toggle():
    if st.session_state.is_standalone:
        st.session_state.series_name_input = "Standalone"
    else:
        if st.session_state.series_name_input == "Standalone":
            st.session_state.series_name_input = ""


st.checkbox(
    "This is a standalone book",
    key="is_standalone",
    on_change=handle_standalone_toggle
)

st.divider()

with st.form("add_book_form"):
    title = st.text_input("Title")
    authors = st.text_input("Authors (comma-separated)")

    series_name = st.text_input(
        "Series Name",
        key="series_name_input",
        disabled=st.session_state.is_standalone
    )

    book_number = None
    if st.session_state.is_standalone:
        st.caption("Standalone books use the series name 'Standalone' and no book number.")
    else:
        book_number = st.number_input(
            "Book Number",
            min_value=0.5,
            step=0.5,
            value=1.0
        )

    length_type = st.text_input("Length Type")
    demographic = st.text_input("Demographic")
    full_cast = st.checkbox("Full Cast")
    notes = st.text_area("Notes")
    main_genres = st.text_input("Main Genres (comma-separated)")
    secondary_genres = st.text_input("Secondary Genres (comma-separated)")

    submitted = st.form_submit_button("Add Book")

if submitted:
    try:
        final_series_name = (
            "Standalone"
            if st.session_state.is_standalone
            else st.session_state.series_name_input.strip()
        )

        execute_procedure(
            "AddBook",
            [
                title.strip(),
                authors.strip(),
                final_series_name,
                book_number,
                length_type.strip() if length_type.strip() else None,
                demographic.strip() if demographic.strip() else None,
                int(full_cast),
                notes.strip() if notes.strip() else None,
                main_genres.strip() if main_genres.strip() else None,
                secondary_genres.strip() if secondary_genres.strip() else None,
            ],
        )

        st.success("Book added successfully.")

    except Exception as e:
        st.error(f"Error: {e}")