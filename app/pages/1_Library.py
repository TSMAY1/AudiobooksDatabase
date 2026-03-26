import streamlit as st
from db import run_query

st.title("📚 Library")

query = """
SELECT
    bd.BookID,
    bd.Authors,
    bd.Title,
    bd.SeriesName,
    bd.BookNumber,
    a.Rating AS AngelaRating,
    t.Rating AS ToriRating
FROM vw_book_details bd
LEFT JOIN vw_angela_read_books a
    ON bd.BookID = a.BookID
LEFT JOIN vw_tori_read_books t
    ON bd.BookID = t.BookID
ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber;
"""

df = run_query(query)

search = st.text_input("Search by title or author")

if search:
    mask = (
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

st.dataframe(df, width='stretch')