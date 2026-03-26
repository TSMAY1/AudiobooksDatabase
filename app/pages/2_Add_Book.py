import streamlit as st
from db import execute_procedure

st.title("➕ Add Book")

with st.form("add_book_form"):
    title = st.text_input("Title")
    authors = st.text_input("Authors (comma-separated)")
    series_name = st.text_input("Series Name")
    book_number = st.number_input("Book Number", min_value=0.0, step=0.5, value=0.0)
    length_type = st.text_input("Length Type")
    demographic = st.text_input("Demographic")
    full_cast = st.checkbox("Full Cast")
    notes = st.text_area("Notes")
    main_genres = st.text_input("Main Genres (comma-separated)")
    secondary_genres = st.text_input("Secondary Genres (comma-separated)")

    submitted = st.form_submit_button("Add Book")

if submitted:
    try:
        execute_procedure(
            "AddBook",
            [
                title,
                authors,
                series_name if series_name.strip() else None,
                book_number if book_number != 0.0 else None,
                length_type if length_type.strip() else None,
                demographic if demographic.strip() else None,
                int(full_cast),
                notes if notes.strip() else None,
                main_genres if main_genres.strip() else None,
                secondary_genres if secondary_genres.strip() else None,
            ],
        )
        st.success("Book added successfully.")
    except Exception as e:
        st.error(f"Error: {e}")