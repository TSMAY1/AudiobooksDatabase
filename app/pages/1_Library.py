import streamlit as st
import pandas as pd
from db import run_query

st.title("📚 Library")


def load_readers():
    df = run_query("""
        SELECT ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)
    return df["ReaderName"].tolist()


books_query = """
SELECT
    vd.BookID,
    vd.Title,
    vd.Authors,
    vd.SeriesName,
    vd.ParentSeriesName,
    vd.UniverseName,
    vd.BookNumber,
    vd.UniverseReadingOrder,
    STRING_AGG(
        CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END,
        ', '
    ) AS MainGenres,
    STRING_AGG(
        CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END,
        ', '
    ) AS SecondaryGenres
FROM vw_book_details vd
LEFT JOIN book_genres bg
    ON bg.BookID = vd.BookID
LEFT JOIN genres g
    ON g.GenreID = bg.GenreID
GROUP BY
    vd.BookID,
    vd.Title,
    vd.Authors,
    vd.SeriesName,
    vd.ParentSeriesName,
    vd.UniverseName,
    vd.BookNumber,
    vd.UniverseReadingOrder
ORDER BY
    vd.Authors, vd.SeriesName, vd.Title;
"""

reader_status_query = """
SELECT
    rb.BookID,
    rb.ReaderName,
    rb.ReadingStatus,
    rb.Rating
FROM vw_reader_books rb
ORDER BY
    rb.ReaderName, rb.BookID;
"""

books_df = run_query(books_query)
reader_df = run_query(reader_status_query)
reader_names = load_readers()

if books_df is None or books_df.empty:
    st.info("No books found in the library.")
    st.stop()

status_pivot = reader_df.pivot(
    index="BookID",
    columns="ReaderName",
    values="ReadingStatus"
)

rating_pivot = reader_df.pivot(
    index="BookID",
    columns="ReaderName",
    values="Rating"
)

status_pivot.columns = [f"{col} Status" for col in status_pivot.columns]
rating_pivot.columns = [f"{col} Rating" for col in rating_pivot.columns]

status_pivot = status_pivot.reset_index()
rating_pivot = rating_pivot.reset_index()

df = books_df.merge(status_pivot, on="BookID", how="left")
df = df.merge(rating_pivot, on="BookID", how="left")

df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])

search = st.text_input("Search by title, author, series, universe, or genre")

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    sort_option = st.selectbox(
        "Sort by",
        ["Title", "Author", "Series", "Universe Reading Order"]
    )

with filter_col2:
    reader_filter = st.selectbox(
        "Filter reader columns",
        ["All Readers"] + reader_names
    )

if search:
    mask = (
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
        | df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
        | df["UniverseName"].fillna("").str.contains(search, case=False, na=False)
        | df["MainGenres"].fillna("").str.contains(search, case=False, na=False)
        | df["SecondaryGenres"].fillna("").str.contains(search, case=False, na=False)
    )
    df = df[mask]

if sort_option == "Title":
    df = df.sort_values(
        by=["Title", "Authors"],
        ascending=[True, True],
        na_position="last"
    )

elif sort_option == "Author":
    df = df.sort_values(
        by=["Authors", "Title"],
        ascending=[True, True],
        na_position="last"
    )

elif sort_option == "Series":
    df = df.sort_values(
        by=["SeriesName", "BookNumber", "Title"],
        ascending=[True, True, True],
        na_position="last"
    )

elif sort_option == "Universe Reading Order":
    df = df.sort_values(
        by=["UniverseName", "SortOrder", "SeriesName", "Title"],
        ascending=[True, True, True, True],
        na_position="last"
    )

df_display = df.rename(columns={
    "Authors": "Author(s)",
    "UniverseName": "Universe",
    "SeriesName": "Series",
    "BookNumber": "Book #",
    "UniverseReadingOrder": "Universe Order",
    "MainGenres": "Main Genre(s)",
    "SecondaryGenres": "Secondary Genre(s)",
})

status_map = {
    "Read": "✅ Read",
    "Unread": "📖 Unread",
    "TBR": "⭐ TBR",
    "Reading": "📘 Reading",
    "DNF": "❌ DNF"
}

status_columns = [col for col in df_display.columns if col.endswith(" Status")]
rating_columns = [col for col in df_display.columns if col.endswith(" Rating")]

for col in status_columns:
    df_display[col] = df_display[col].map(status_map).fillna(df_display[col])

for col in rating_columns:
    df_display[col] = df_display[col].round(2)

display_columns = [
    "Title",
    "Author(s)",
    "Universe",
    "Series",
    "Book #",
    "Main Genre(s)",
    "Secondary Genre(s)",
    "Universe Order",
]

reader_columns = []

if reader_filter == "All Readers":
    for reader_name in reader_names:
        status_col = f"{reader_name} Status"
        rating_col = f"{reader_name} Rating"

        if status_col in df_display.columns:
            reader_columns.append(status_col)
        if rating_col in df_display.columns:
            reader_columns.append(rating_col)
else:
    status_col = f"{reader_filter} Status"
    rating_col = f"{reader_filter} Rating"

    if status_col in df_display.columns:
        reader_columns.append(status_col)
    if rating_col in df_display.columns:
        reader_columns.append(rating_col)

display_columns.extend(reader_columns)

if sort_option != "Universe Reading Order" and "Universe Order" in display_columns:
    display_columns.remove("Universe Order")

st.dataframe(df_display[display_columns], width="stretch", hide_index=True)