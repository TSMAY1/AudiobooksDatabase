import streamlit as st
from db import run_query
import altair as alt

st.title("📊 Analytics")

def show_bar_chart(df, category_col, value_col, title):
    if df is None or df.empty:
        st.info("No data available for chart.")
        return

    chart = alt.Chart(df).mark_bar().encode(
        y=alt.Y(category_col, sort='-x', title=category_col),
        x=alt.X(value_col, title=value_col),
        tooltip=[category_col, value_col]
    ).properties(
        title=title
    )

    st.altair_chart(chart, width='stretch')


def load_readers():
    df = run_query("""
        SELECT ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)
    return df["ReaderName"].tolist()


def show_dataframe(query, params=None):
    df = run_query(query, params=params)
    if df is None or df.empty:
        st.info("No results found for this report.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)


reader_names = load_readers()

tab1, tab2, tab3 = st.tabs(["Overview", "Reader Stats", "Library Insights"])

# =========================================================
# OVERVIEW TAB
# =========================================================
with tab1:
    st.subheader("Overview")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    total_books_df = run_query("SELECT COUNT(*) AS TotalBooks FROM books;")
    total_read_df = run_query("""
        SELECT COUNT(*) AS TotalRead
        FROM reading_status
        WHERE ReadingStatus = 'Read';
    """)
    total_tbr_df = run_query("""
        SELECT COUNT(*) AS TotalTBR
        FROM reading_status
        WHERE ReadingStatus = 'TBR';
    """)
    avg_rating_df = run_query("""
        SELECT CAST(AVG(Rating) AS DECIMAL(4,2)) AS AvgRating
        FROM reading_status
        WHERE Rating IS NOT NULL;
    """)

    with metric_col1:
        st.metric("Total Books", int(total_books_df.iloc[0]["TotalBooks"]))

    with metric_col2:
        st.metric("Total Read Entries", int(total_read_df.iloc[0]["TotalRead"]))

    with metric_col3:
        st.metric("Total TBR Entries", int(total_tbr_df.iloc[0]["TotalTBR"]))

    with metric_col4:
        avg_rating = avg_rating_df.iloc[0]["AvgRating"]
        st.metric("Average Rating", f"{avg_rating:.2f}" if avg_rating is not None else "—")

    st.divider()

    st.subheader("Shared Reads Between Readers")
    show_dataframe("""
        SELECT
            r1.ReaderName AS Reader1,
            r2.ReaderName AS Reader2,
            COUNT(*) AS BooksReadInCommon
        FROM reading_status rs1
        JOIN reading_status rs2
            ON rs1.BookID = rs2.BookID
           AND rs1.ReaderID < rs2.ReaderID
        JOIN readers r1
            ON r1.ReaderID = rs1.ReaderID
        JOIN readers r2
            ON r2.ReaderID = rs2.ReaderID
        WHERE rs1.ReadingStatus = 'Read'
          AND rs2.ReadingStatus = 'Read'
        GROUP BY r1.ReaderName, r2.ReaderName
        ORDER BY BooksReadInCommon DESC, Reader1, Reader2;
    """)

    st.divider()

    st.subheader("Highest Rated Books Overall")
    show_dataframe("""
        WITH BookRatings AS (
            SELECT
                BookID,
                CAST(AVG(Rating) AS DECIMAL(4,2)) AS AverageRating,
                COUNT(Rating) AS NumRatings
            FROM reading_status
            WHERE Rating IS NOT NULL 
                   AND Rating > 3.5
            GROUP BY BookID
        )
        SELECT
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            br.AverageRating,
            br.NumRatings
        FROM vw_book_details bd
        JOIN BookRatings br
            ON bd.BookID = br.BookID
        ORDER BY br.AverageRating DESC, br.NumRatings DESC, bd.Title;
    """)

# =========================================================
# READER STATS TAB
# =========================================================
with tab2:
    st.subheader("Reader Stats")

    selected_reader = st.selectbox("Select a reader", reader_names, key="analytics_reader")

    reader_metric_col1, reader_metric_col2, reader_metric_col3 = st.columns(3)

    reader_read_df = run_query("""
        SELECT COUNT(*) AS TotalRead
        FROM vw_reader_books
        WHERE ReaderName = ?
          AND ReadingStatus = 'Read';
    """, params=[selected_reader])

    reader_tbr_df = run_query("""
        SELECT COUNT(*) AS TotalTBR
        FROM vw_reader_books
        WHERE ReaderName = ?
          AND ReadingStatus = 'TBR';
    """, params=[selected_reader])

    reader_avg_df = run_query("""
        SELECT CAST(AVG(Rating) AS DECIMAL(4,2)) AS AvgRating
        FROM vw_reader_books
        WHERE ReaderName = ?
          AND Rating IS NOT NULL;
    """, params=[selected_reader])

    with reader_metric_col1:
        st.metric("Books Read", int(reader_read_df.iloc[0]["TotalRead"]))

    with reader_metric_col2:
        st.metric("Books on TBR", int(reader_tbr_df.iloc[0]["TotalTBR"]))

    with reader_metric_col3:
        avg_rating = reader_avg_df.iloc[0]["AvgRating"]
        st.metric("Average Rating", f"{avg_rating:.2f}" if avg_rating is not None else "—")

    st.divider()

    report_option = st.selectbox(
        "Choose a reader report",
        [
            "Status breakdown",
            "Highest rated books",
            "Current TBR",
            "Currently reading",
            "DNF list",
        ],
        key="reader_report_option"
    )

    if report_option == "Status breakdown":
        df = run_query("""
            SELECT
                ReadingStatus,
                COUNT(*) AS NumBooks
            FROM vw_reader_books
            WHERE ReaderName = ?
            GROUP BY ReadingStatus
            ORDER BY NumBooks DESC, ReadingStatus;
        """, params=[selected_reader])

        show_bar_chart(df, "ReadingStatus", "NumBooks", f"{selected_reader} - Status Breakdown")
        st.dataframe(df, width="stretch", hide_index=True)

    elif report_option == "Highest rated books":
        show_dataframe("""
            SELECT
                bd.Title,
                bd.Authors,
                bd.SeriesName,
                rb.Rating
            FROM vw_reader_books rb
            JOIN vw_book_details bd
                ON bd.BookID = rb.BookID
            WHERE rb.ReaderName = ?
              AND rb.Rating IS NOT NULL
              AND rb.Rating > 3.5
            ORDER BY rb.Rating DESC, bd.Title;
        """, params=[selected_reader])

    elif report_option == "Current TBR":
        show_dataframe("""
            SELECT
                bd.Title,
                bd.Authors,
                bd.SeriesName,
                bd.BookNumber
            FROM vw_reader_books rb
            JOIN vw_book_details bd
                ON bd.BookID = rb.BookID
            WHERE rb.ReaderName = ?
              AND rb.ReadingStatus = 'TBR'
            ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber, bd.Title;
        """, params=[selected_reader])

    elif report_option == "Currently reading":
        show_dataframe("""
            SELECT
                bd.Title,
                bd.Authors,
                bd.SeriesName,
                bd.BookNumber
            FROM vw_reader_books rb
            JOIN vw_book_details bd
                ON bd.BookID = rb.BookID
            WHERE rb.ReaderName = ?
              AND rb.ReadingStatus = 'Reading'
            ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber, bd.Title;
        """, params=[selected_reader])

    elif report_option == "DNF list":
        show_dataframe("""
            SELECT
                bd.Title,
                bd.Authors,
                bd.SeriesName,
                bd.BookNumber,
                rb.Rating
            FROM vw_reader_books rb
            JOIN vw_book_details bd
                ON bd.BookID = rb.BookID
            WHERE rb.ReaderName = ?
              AND rb.ReadingStatus = 'DNF'
            ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber, bd.Title;
        """, params=[selected_reader])

# =========================================================
# LIBRARY INSIGHTS TAB
# =========================================================
with tab3:
    st.subheader("Library Insights")

    insight_option = st.selectbox(
        "Choose a library report",
        [
            "Most common main genres",
            "Most common secondary genres",
            "Books by demographic",
            "Books by length type",
            "Books per series",
        ],
        key="insight_report_option"
    )

    if insight_option == "Most common main genres":
        df = run_query("""
            SELECT TOP 10
                g.GenreName,
                COUNT(*) AS NumBooks
            FROM book_genres bg
            JOIN genres g
                ON bg.GenreID = g.GenreID
            WHERE bg.GenreType = 'Main'
            GROUP BY g.GenreName
            ORDER BY NumBooks DESC, g.GenreName;
        """)

        show_bar_chart(df, "GenreName", "NumBooks", "Main Genre Distribution")
        st.dataframe(df, width="stretch", hide_index=True)

    elif insight_option == "Most common secondary genres":
        df = run_query("""
            SELECT TOP 10
                g.GenreName,
                COUNT(*) AS NumBooks
            FROM book_genres bg
            JOIN genres g
                ON bg.GenreID = g.GenreID
            WHERE bg.GenreType = 'Secondary'
            GROUP BY g.GenreName
            ORDER BY NumBooks DESC, g.GenreName;
        """)

        show_bar_chart(df, "GenreName", "NumBooks", "Secondary Genre Distribution")
        st.dataframe(df, width="stretch", hide_index=True)

    elif insight_option == "Books by demographic":
        df = run_query("""
            SELECT
                Demographic,
                COUNT(*) AS NumBooks
            FROM books
            GROUP BY Demographic
            ORDER BY NumBooks DESC, Demographic;
        """)

        show_bar_chart(df, "Demographic", "NumBooks", "Books by Demographic")
        st.dataframe(df, width="stretch", hide_index=True)

    elif insight_option == "Books by length type":
        df = run_query("""
            SELECT
                LengthType,
                COUNT(*) AS NumBooks
            FROM books
            GROUP BY LengthType
            ORDER BY NumBooks DESC, LengthType;
        """)

        show_bar_chart(df, "LengthType", "NumBooks", "Books by Length Type")
        st.dataframe(df, width="stretch", hide_index=True)

    elif insight_option == "Books per series":
        show_dataframe("""
            SELECT
                s.SeriesName,
                COUNT(b.BookID) AS NumBooks
            FROM series s
            JOIN books b
                ON b.SeriesID = s.SeriesID
            GROUP BY s.SeriesName
            ORDER BY NumBooks DESC, s.SeriesName;
        """)