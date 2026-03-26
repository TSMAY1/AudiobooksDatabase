import streamlit as st
from db import run_query

st.title("📊 Analytics")

report = st.selectbox(
    "Choose a report",
    [
        "Total books read by reader",
        "Average rating by reader",
        "Highest rated books",
        "Tori's highest rated books",
        "Angela's highest rated books",
    ],
)

queries = {
    "Total books read by reader": """
        SELECT ReaderName, COUNT(*) AS TotalBooksRead
        FROM vw_reader_books
        WHERE ReadStatus = 1
        GROUP BY ReaderName
        ORDER BY TotalBooksRead DESC;
    """,
    "Average rating by reader": """
        SELECT
            ReaderName,
            CAST(AVG(Rating) AS DECIMAL(4,2)) AS AverageRating,
            COUNT(Rating) AS NumberOfRatedBooks
        FROM vw_reader_books
        WHERE ReadStatus = 1 AND Rating IS NOT NULL
        GROUP BY ReaderName
        ORDER BY AverageRating DESC;
    """,
    "Highest rated books": """
        WITH BookRatings AS (
            SELECT
                BookID,
                CAST(AVG(Rating) AS DECIMAL(4,2)) AS AverageRating,
                COUNT(Rating) AS NumRatings
            FROM reading_status
            WHERE Rating IS NOT NULL
            GROUP BY BookID
        )
        SELECT
            bd.BookID,
            bd.Title,
            bd.Authors,
            br.AverageRating,
            br.NumRatings
        FROM vw_book_details bd
        JOIN BookRatings br
            ON bd.BookID = br.BookID
        ORDER BY br.AverageRating DESC, br.NumRatings DESC, bd.Title;
    """,
    "Tori's highest rated books": """
        SELECT TOP 100 BookID, Title, Authors, Rating
        FROM vw_tori_read_books
        WHERE Rating IS NOT NULL
        ORDER BY Rating DESC, Title;
    """,
    "Angela's highest rated books": """
        SELECT TOP 100 BookID, Title, Authors, Rating
        FROM vw_angela_read_books
        WHERE Rating IS NOT NULL
        ORDER BY Rating DESC, Title;
    """,
}

df = run_query(queries[report])
st.dataframe(df, width='stretch')