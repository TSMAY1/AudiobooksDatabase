import streamlit as st
import pandas as pd
from db import run_query, execute_procedure

st.title("🏷️ Update Genres")
st.markdown("View the current genre information for a book, then update it if needed.")

# Load books for selector
books = run_query("""
SELECT BookID, Title, Authors
FROM vw_book_details
ORDER BY Authors, Title;
""")

book_options = {
    f"{row['Title']} — {row['Authors']}": {
        "BookID": row["BookID"],
        "Title": row["Title"],
        "Authors": row["Authors"]
    }
    for _, row in books.iterrows()
}

selected_label = st.selectbox("📚 Select Book", list(book_options.keys()))
selected_book = book_options[selected_label]

selected_book_id = selected_book["BookID"]
selected_title = selected_book["Title"]
selected_authors = selected_book["Authors"]
selected_author_for_proc = selected_authors.split(",")[0].strip()

# Query current genre info for selected book
genre_df = run_query("""
SELECT
    bd.BookID,
    bd.Title,
    bd.Authors,
    STRING_AGG(CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END, ', ') AS MainGenres,
    STRING_AGG(CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END, ', ') AS SecondaryGenres
FROM vw_book_details bd
LEFT JOIN book_genres bg
    ON bg.BookID = bd.BookID
LEFT JOIN genres g
    ON g.GenreID = bg.GenreID
WHERE bd.BookID = ?
GROUP BY bd.BookID, bd.Title, bd.Authors;
""", params=[selected_book_id])

st.subheader("Current Genre Information")

if not genre_df.empty:
    current_main = genre_df.iloc[0]["MainGenres"] if pd.notna(genre_df.iloc[0]["MainGenres"]) else ""
    current_secondary = genre_df.iloc[0]["SecondaryGenres"] if pd.notna(genre_df.iloc[0]["SecondaryGenres"]) else ""

    # Two-row display table
    genre_display_df = pd.DataFrame({
        "Genre Type": ["Main", "Secondary"],
        "Genres": [
            current_main if current_main else "—",
            current_secondary if current_secondary else "—"
        ]
    })

    st.dataframe(genre_display_df, width='stretch', hide_index=True)


else:
    st.info("No genre information found for this book yet.")
    current_main = ""
    current_secondary = ""

st.markdown("Saving will replace the current genre list for this book")

st.divider()

st.subheader("Edit Genres")

main_genres = st.text_input(
    "Main Genres (comma-separated)",
    value=current_main
)

secondary_genres = st.text_input(
    "Secondary Genres (comma-separated)",
    value=current_secondary
)

if st.button("💾 Save Genre Update", width='stretch'):
    try:
        execute_procedure(
            "UpdateBookGenres",
            [
                selected_title,
                selected_author_for_proc,
                main_genres if main_genres.strip() else None,
                secondary_genres if secondary_genres.strip() else None,
            ],
        )
        st.success("Genres updated successfully.")
        st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")