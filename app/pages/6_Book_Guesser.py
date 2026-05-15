import streamlit as st
import pandas as pd
from db import (
    run_query,
    load_cover_image_bytes,
    format_book_number,
    detail_link,
)

st.set_page_config(page_title="Book Guesser", page_icon="❓")

st.title("❓ Book Guesser")
st.caption("Pick a category & generate your secret book!")
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
# Cached loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_random_book_pool(category: str):
    if category == "Books only Angela has read":
        where_clause = """
        WHERE AngelaStatus.ReadingStatus = 'Read'
        AND (
                ToriStatus.ReadingStatus IS NULL
                OR ToriStatus.ReadingStatus <> 'Read'
            )
        """

    elif category == "Books only Tori has read":
        where_clause = """
        WHERE ToriStatus.ReadingStatus = 'Read'
        AND (
                AngelaStatus.ReadingStatus IS NULL
                OR AngelaStatus.ReadingStatus <> 'Read'
            )
        """

    elif category == "Books both readers have read":
        where_clause = """
        WHERE AngelaStatus.ReadingStatus = 'Read'
        AND ToriStatus.ReadingStatus = 'Read'
        """
    
    elif category == "Books neither reader has read":
        where_clause = """
        WHERE (
                AngelaStatus.ReadingStatus IS NULL
                OR AngelaStatus.ReadingStatus <> 'Read'
            )
        AND (
                ToriStatus.ReadingStatus IS NULL
                OR ToriStatus.ReadingStatus <> 'Read'
            )
        """

    else:
        where_clause = ""

    query = f"""
    SELECT
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        vd.ParentSeriesName,
        vd.UniverseName,
        vd.BookNumber,
        vd.UniverseReadingOrder,
        vd.LengthType,
        vd.Demographic,
        vd.Notes,
        pc.ImageFilePath AS CoverImagePath,
        AngelaStatus.ReadingStatus AS AngelaStatus,
        ToriStatus.ReadingStatus AS ToriStatus,
        MainGenres.MainGenres,
        SecondaryGenres.SecondaryGenres,
        Audio.Narrators,
        Audio.Publisher,
        Audio.ReleaseYear,
        Audio.DurationDisplay,
        Audio.DurationMinutes,
        Audio.IsFullCast,
        Audio.IsAbridged
    FROM vw_book_details vd
    LEFT JOIN vw_book_primary_cover pc
        ON pc.BookID = vd.BookID

    LEFT JOIN vw_reader_books AngelaStatus
        ON AngelaStatus.BookID = vd.BookID
       AND AngelaStatus.ReaderName = 'Angela'

    LEFT JOIN vw_reader_books ToriStatus
        ON ToriStatus.BookID = vd.BookID
       AND ToriStatus.ReaderName = 'Tori'

    LEFT JOIN (
        SELECT
            bg.BookID,
            STRING_AGG(g.GenreName, ', ') AS MainGenres
        FROM book_genres bg
        JOIN genres g
            ON g.GenreID = bg.GenreID
        WHERE bg.GenreType = 'Main'
        GROUP BY bg.BookID
    ) MainGenres
        ON MainGenres.BookID = vd.BookID

    LEFT JOIN (
        SELECT
            bg.BookID,
            STRING_AGG(g.GenreName, ', ') AS SecondaryGenres
        FROM book_genres bg
        JOIN genres g
            ON g.GenreID = bg.GenreID
        WHERE bg.GenreType = 'Secondary'
        GROUP BY bg.BookID
    ) SecondaryGenres
        ON SecondaryGenres.BookID = vd.BookID

    LEFT JOIN (
        SELECT
            BookID,
            STRING_AGG(Narrators, ', ') AS Narrators,
            MAX(Publisher) AS Publisher,
            MAX(ReleaseYear) AS ReleaseYear,
            MAX(DurationDisplay) AS DurationDisplay,
            MAX(DurationMinutes) AS DurationMinutes,
            MAX(CAST(IsFullCast AS INT)) AS IsFullCast,
            MAX(CAST(IsAbridged AS INT)) AS IsAbridged
        FROM vw_book_audiobooks
        GROUP BY BookID
    ) Audio
        ON Audio.BookID = vd.BookID

    {where_clause}

    ORDER BY vd.Title;
    """

    return run_query(query)


# =========================================================
# Helpers
# =========================================================

def clean(value):
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def yes_no(value):
    return "Yes" if value in [True, 1] else "No"


def render_meta(label, value, icon=None):
    value = clean(value)

    if not value:
        return

    prefix = f"{icon} " if icon else ""
    st.markdown(f"**{prefix}{label}:** {value}")


def render_status_chip(reader_name, status):
    status = clean(status) or "Unread"

    color_map = {
        "Read": "#22c55e",
        "Reading": "#3b82f6",
        "TBR": "#f59e0b",
        "Unread": "#6b7280",
        "DNF": "#ef4444",
    }

    color = color_map.get(status, "#6b7280")

    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background-color:{color}22;
            color:{color};
            font-size:0.75rem;
            font-weight:600;
            margin-right:6px;
            margin-bottom:6px;
            border:1px solid {color}55;
        ">
            {reader_name}: {status}
        </span>
        """,
        unsafe_allow_html=True,
    )


def choose_random_book(pool_df: pd.DataFrame):
    row = pool_df.sample(1).iloc[0]
    st.session_state.yes_no_selected_book_id = int(row["BookID"])


# =========================================================
# Controls
# =========================================================
category = st.selectbox(
    "Choose a category",
    [
    "Books only Angela has read",
    "Books only Tori has read",
    "Books both readers have read",
    "Books neither reader has read",
    ],
)

pool_df = load_random_book_pool(category)

if pool_df.empty:
    st.warning("No books found for this category.")
    st.stop()

st.caption(f"{len(pool_df)} possible books")

button_col1, button_col2 = st.columns([1, 1])

with button_col1:
    if st.button("🎲 Pick Random Book", width="stretch"):
        choose_random_book(pool_df)
        st.rerun()

with button_col2:
    if st.button("🔄 Clear Selection", width="stretch"):
        st.session_state.pop("yes_no_selected_book_id", None)
        st.rerun()


# =========================================================
# Selected book display
# =========================================================
selected_book_id = st.session_state.get("yes_no_selected_book_id")

if not selected_book_id:
    st.info("Pick a random book to begin.")
    st.stop()

selected_df = pool_df[pool_df["BookID"] == selected_book_id]

if selected_df.empty:
    st.warning("The selected book is no longer in this category. Pick a new one.")
    st.stop()

book = selected_df.iloc[0]

st.divider()

left_col, right_col = st.columns([1, 2])

with left_col:
    cover_path = clean(book.get("CoverImagePath"))

    if cover_path:
        try:
            st.image(load_cover_image_bytes(cover_path), width=260)
        except Exception:
            st.caption("Cover could not be loaded.")
    else:
        st.caption("No cover available.")

    st.markdown("### Reader Status")
    render_status_chip("Angela", book.get("AngelaStatus"))
    render_status_chip("Tori", book.get("ToriStatus"))

with right_col:
    with st.container(border=True):
        st.markdown(
            f"""
            <h2 style="margin-bottom:0.25rem;">
                <a href="{detail_link(book['BookID'])}"
                target="_blank"
                class="book-title-link">
                    {book['Title']}
                </a>
            </h2>
            """,
            unsafe_allow_html=True,
        )
        st.caption(book["Authors"])

        st.markdown("### Core Details")

        series_name = clean(book.get("SeriesName"))
        book_number = format_book_number(book.get("BookNumber"))

        if series_name:
            if book_number:
                render_meta("Series", f"{series_name} #{book_number}", "📚")
            else:
                render_meta("Series", series_name, "📚")
        else:
            render_meta("Series", "Standalone", "📚")

        render_meta("Parent Series", book.get("ParentSeriesName"), "🧭")
        render_meta("Universe", book.get("UniverseName"), "🌌")
        render_meta("Universe Reading Order", format_book_number(book.get("UniverseReadingOrder")), "🔢")
        render_meta("Length Type", book.get("LengthType"), "⏱️")
        render_meta("Demographic", book.get("Demographic"), "👥")

        render_meta("Full Cast Audiobook", yes_no(book.get("IsFullCast")), "🎭")

    with st.container(border=True):
        st.markdown("### Genres")

        main_genres = clean(book.get("MainGenres"))
        secondary_genres = clean(book.get("SecondaryGenres"))

        if main_genres:
            st.markdown(f"**Main:** {main_genres}")
        else:
            st.caption("No main genres recorded.")

        if secondary_genres:
            st.markdown(f"**Secondary:** {secondary_genres}")
        else:
            st.caption("No secondary genres recorded.")

    with st.container(border=True):
        st.markdown("### Audiobook Details")

        render_meta("Narrator(s)", book.get("Narrators"), "🎧")
        render_meta("Publisher", book.get("Publisher"), "🏢")
        render_meta("Release Year", book.get("ReleaseYear"), "📅")
        render_meta("Length", book.get("DurationDisplay"), "⏱️")

        if pd.notna(book.get("IsFullCast")):
            render_meta("Audiobook Full Cast", yes_no(book.get("IsFullCast")), "🎭")

        if pd.notna(book.get("IsAbridged")):
            render_meta("Abridged", yes_no(book.get("IsAbridged")), "✂️")

    notes = clean(book.get("Notes"))

    if notes:
        with st.container(border=True):
            st.markdown("### Notes")
            st.write(notes)
