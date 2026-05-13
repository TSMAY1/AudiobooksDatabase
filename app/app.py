import streamlit as st
import pandas as pd
from db import (
    run_query,
    load_cover_image_bytes,
    format_book_number,
    format_duration,
    format_series,
    detail_link,
)


st.set_page_config(page_title="Audiobooks Dashboard", layout="wide")

st.title("🎧 Audiobooks Dashboard")
st.caption("A cozy home base for your library, readers, recommendations, and book club tools.")
st.markdown("""
<style>
.book-title-link,
.book-title-link:visited,
.book-title-link:active {
    color: inherit !important;
    text-decoration: none !important;
    font-weight: 700;
}

.book-title-link:hover {
    color: inherit !important;
    text-decoration: underline !important;
    text-decoration-thickness: 1px;
    text-underline-offset: 4px;
    opacity: 0.9;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# Helpers
# =========================================================


def render_small_book_card(row):
    with st.container(border=True):
        col1, col2 = st.columns([1, 3])

        with col1:
            if pd.notna(row.get("ImageFilePath")):
                try:
                    st.image(load_cover_image_bytes(row["ImageFilePath"]), width=90)
                except Exception:
                    st.caption("No cover")
            else:
                st.caption("No cover")

        with col2:
            st.markdown(
                f"""
                <a href="{detail_link(row['BookID'])}" 
                target="_blank" 
                class="book-title-link">
                    {row['Title']}
                </a>
                """,
                unsafe_allow_html=True,
            )
            st.caption(row["Authors"])

            if "SeriesName" in row:
                st.caption(f"📚 {format_series(row['SeriesName'], row.get('BookNumber'))}")

            if "ReaderName" in row:
                st.caption(f"👤 {row['ReaderName']}")

            if "DateAdded" in row and pd.notna(row["DateAdded"]):
                st.caption(f"Added: {pd.to_datetime(row['DateAdded']).strftime('%b %d, %Y')}")


# =========================================================
# Cached loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_dashboard_stats():
    return run_query("""
        SELECT
            (SELECT COUNT(*) FROM books) AS TotalBooks,
            (SELECT COUNT(*) FROM series WHERE SeriesName <> 'Standalone') AS TotalSeries,
            (SELECT COUNT(*) FROM authors_new) AS TotalAuthors,
            (SELECT COUNT(*) FROM narrators) AS TotalNarrators,
            (SELECT ISNULL(SUM(DurationMinutes), 0) FROM vw_book_audiobooks) AS TotalMinutes;
    """)


@st.cache_data(show_spinner=False)
def load_reader_stats():
    return run_query("""
        SELECT
            r.ReaderName,
            SUM(CASE WHEN rs.ReadingStatus = 'Read' THEN 1 ELSE 0 END) AS ReadCount,
            SUM(CASE WHEN rs.ReadingStatus = 'Reading' THEN 1 ELSE 0 END) AS ReadingCount,
            SUM(CASE WHEN rs.ReadingStatus = 'TBR' THEN 1 ELSE 0 END) AS TBRCount,
            SUM(CASE WHEN rs.ReadingStatus = 'DNF' THEN 1 ELSE 0 END) AS DNFCount
        FROM readers r
        LEFT JOIN reading_status rs
            ON rs.ReaderID = r.ReaderID
        GROUP BY r.ReaderName
        ORDER BY r.ReaderName;
    """)


@st.cache_data(show_spinner=False)
def load_currently_reading():
    return run_query("""
        SELECT
            rb.ReaderName,
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            pc.ImageFilePath
        FROM vw_reader_books rb
        JOIN vw_book_details bd
            ON bd.BookID = rb.BookID
        LEFT JOIN vw_book_primary_cover pc
            ON pc.BookID = bd.BookID
        WHERE rb.ReadingStatus = 'Reading'
        ORDER BY rb.ReaderName, bd.Title;
    """)


@st.cache_data(show_spinner=False)
def load_recently_added():
    return run_query("""
        SELECT TOP 15
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            bd.DateAdded,
            pc.ImageFilePath
        FROM vw_book_details bd
        LEFT JOIN vw_book_primary_cover pc
            ON pc.BookID = bd.BookID
        ORDER BY bd.DateAdded DESC, bd.Title;
    """)

def load_random_unread():
    return run_query("""
        SELECT TOP 1
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            pc.ImageFilePath
        FROM vw_book_details bd
        LEFT JOIN vw_reader_books rb
            ON rb.BookID = bd.BookID
        LEFT JOIN vw_book_primary_cover pc
            ON pc.BookID = bd.BookID
        WHERE rb.ReadingStatus = 'Unread'
        ORDER BY NEWID();
    """)


# =========================================================
# Load data
# =========================================================
stats = load_dashboard_stats()
reader_stats = load_reader_stats()
currently_reading = load_currently_reading()
recently_added = load_recently_added()

# =========================================================
# Quick actions
# =========================================================
st.subheader("Quick Actions")

quick_cols1 = st.columns(4)

with quick_cols1[0]:
    st.page_link(
        "pages/1_Reader_Dashboard.py",
        label="👤 Reader Dashboard"
    )

with quick_cols1[1]:
    st.page_link(
        "pages/2_Library.py",
        label="📚 Library"
    )

with quick_cols1[2]:
    st.page_link(
        "pages/4_Recommendations.py",
        label="✨ Recommendations"
    )

with quick_cols1[3]:
    st.page_link(
        "pages/5_Add_Book.py",
        label="➕ Add Book"
    )


quick_cols2 = st.columns(4)

with quick_cols2[0]:
    st.page_link(
        "pages/6_Book_Guesser.py",
        label="🎲 Book Guesser"
    )

with quick_cols2[1]:
    st.page_link(
        "pages/7_Book_Title_Hangman.py",
        label="🔤 Book Hangman"
    )

with quick_cols2[2]:
    st.page_link(
        "pages/8_Fun_Stats.py",
        label="📊 Fun Stats"
    )

with quick_cols2[3]:
    st.page_link(
        "pages/8_Manage_Audiobooks.py",
        label="🎧 Manage Audiobooks"
    )


quick_cols3 = st.columns(4)

with quick_cols3[0]:
    st.page_link(
        "pages/8_Manage_Covers.py",
        label="🖼️ Manage Covers"
    )

with quick_cols3[1]:
    st.page_link(
        "pages/8_Manage_Mini_Books.py",
        label="📖 Mini Books"
    )

with quick_cols3[2]:
    st.page_link(
        "pages/9_Cozy_Corner_Bookclub_Flyers.py",
        label="☕ Bookclub Flyers"
    )

with quick_cols3[3]:
    st.page_link(
        "pages/10_Cozy_Corner_Book_Club_Calendars.py",
        label="🗓️ Bookclub Calendars"
    )

# =========================================================
# Reader activity
# =========================================================
st.subheader("Reader Activity")

if reader_stats.empty:
    st.info("No reader stats found yet.")
else:
    cols = st.columns(len(reader_stats))

    for col, (_, reader_row) in zip(cols, reader_stats.iterrows()):
        reader_name = reader_row["ReaderName"]

        reader_current = currently_reading[
            currently_reading["ReaderName"] == reader_name
        ]

        with col:
            with st.container(border=True):
                st.markdown(f"### {reader_name}")

                st.metric("Read", int(reader_row["ReadCount"] or 0))

                st.caption(
                    f"Reading: {int(reader_row['ReadingCount'] or 0)} · "
                    f"TBR: {int(reader_row['TBRCount'] or 0)} · "
                    f"DNF: {int(reader_row['DNFCount'] or 0)}"
                )

                st.markdown("**Currently Reading**")

                if reader_current.empty:
                    st.caption("Nothing marked as Reading.")
                else:
                    for _, book_row in reader_current.iterrows():
                        cover_col, info_col = st.columns([1, 3])

                        with cover_col:
                            if pd.notna(book_row.get("ImageFilePath")):
                                try:
                                    st.image(
                                        load_cover_image_bytes(book_row["ImageFilePath"]),
                                        width=80
                                    )
                                except Exception:
                                    st.caption("No cover")
                            else:
                                st.caption("No cover")

                        with info_col:
                            st.markdown(f"**{book_row['Title']}**")
                            st.caption(book_row["Authors"])

                            if pd.notna(book_row.get("SeriesName")):
                                st.caption(
                                    f"📚 {format_series(book_row['SeriesName'], book_row.get('BookNumber'))}"
                                )


# =========================================================
# Top row
# =========================================================
top_col1, top_col2 = st.columns([1.2, 1])


# =========================================================
# Library Overview
# =========================================================
with top_col1:

    st.subheader("Library Overview")

    if not stats.empty:
        s = stats.iloc[0]

        total_hours = (
            int(s["TotalMinutes"]) // 60
            if pd.notna(s["TotalMinutes"])
            else 0
        )

        metric_cols_top = st.columns(3)
        metric_cols_bottom = st.columns(2)

        metric_cols_top[0].metric("Books", int(s["TotalBooks"]))
        metric_cols_top[1].metric("Series", int(s["TotalSeries"]))
        metric_cols_top[2].metric("Authors", int(s["TotalAuthors"]))

        metric_cols_bottom[0].metric("Narrators", int(s["TotalNarrators"]))
        metric_cols_bottom[1].metric("Hours", f"{total_hours:,}")

# =========================================================
# Surprise pick
# =========================================================
with top_col2:

    st.subheader("Surprise Pick")

    if st.button("🎲 Pick Random Unread Book", use_container_width=True):

        random_unread = load_random_unread()

        if random_unread.empty:
            st.info("No unread books found.")
        else:
            st.session_state["homepage_random_book"] = (
                random_unread.iloc[0].to_dict()
            )

    if "homepage_random_book" in st.session_state:
        render_small_book_card(
            pd.Series(st.session_state["homepage_random_book"])
        )

# =========================================================
# Recently added
# =========================================================
st.subheader("Recently Added")

if recently_added.empty:
    st.info("No recently added books found.")
else:
    cards_per_row = 3

    for i in range(0, len(recently_added), cards_per_row):
        cols = st.columns(cards_per_row)
        chunk = recently_added.iloc[i:i + cards_per_row]

        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                render_small_book_card(row)
