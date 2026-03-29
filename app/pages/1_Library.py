import streamlit as st
from db import run_query

st.title("📚 Library")

query = """
SELECT
    vd.BookID,
    vd.Title,
    vd.Authors,
    vd.SeriesName,
    vd.ParentSeriesName,
    vd.UniverseName,
    vd.BookNumber,
    vd.UniverseReadingOrder,
    ang.ReadingStatus AS Angela_Read,
    tor.ReadingStatus AS Tori_Read,
    ang.Rating AS Angela_Rating,
    tor.Rating AS Tori_Rating
FROM vw_book_details vd
LEFT JOIN vw_reader_books ang
    ON ang.BookID = vd.BookID
   AND ang.ReaderName = 'Angela'
LEFT JOIN vw_reader_books tor
    ON tor.BookID = vd.BookID
   AND tor.ReaderName = 'Tori'
ORDER BY
    vd.Authors, vd.SeriesName;
"""

df = run_query(query)

if df is None or df.empty:
    st.info("No books found in the library.")
    st.stop()

df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])

search = st.text_input("Search by title, author, series name, or universe")

sort_option = st.selectbox(
    "Sort by",
    ["Title", "Author", "Series", "Universe Reading Order"]
)

if search:
    mask = (
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
        | df["SeriesName"].str.contains(search, case=False, na=False)
        | df["UniverseName"].str.contains(search, case=False, na=False)
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
    "Angela_Read": "Angela Status",
    "Tori_Read": "Tori Status",
    "Angela_Rating": "Angela Rating",
    "Tori_Rating": "Tori Rating"
})

status_map = {
    "Read": "✅ Read",
    "Unread": "📖 Unread",
    "TBR": "⭐ TBR",
    "DNF": "❌ DNF"
}

df_display["Angela Status"] = df_display["Angela Status"].map(status_map).fillna(df_display["Angela Status"])
df_display["Tori Status"] = df_display["Tori Status"].map(status_map).fillna(df_display["Tori Status"])

df_display["Angela Rating"] = df_display["Angela Rating"].round(2)
df_display["Tori Rating"] = df_display["Tori Rating"].round(2)

display_columns = [
    "Title",
    "Author(s)",
    "Universe",
    "Series",
    "Book #",
    "Universe Order",
    "Angela Status",
    "Angela Rating",
    "Tori Status",
    "Tori Rating"
]

if sort_option != "Universe Reading Order":
    display_columns.remove("Universe Order")

st.dataframe(df_display[display_columns], width="stretch")