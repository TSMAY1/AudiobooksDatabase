import streamlit as st
import pandas as pd
from ui import configure_page
from db import (
    run_query,
    load_cover_image_bytes,
    format_book_number,
    detail_link,
)

configure_page("Book Guesser", icon="❓")
st.title("❓ Book Guesser")
st.caption("Pick a category & generate your secret book!")

st.markdown("""
<style>
.book-title-link,
.book-title-link:visited,
.book-title-link:active {
    color: inherit !important;
    text-decoration: none !important;
    font-weight: 800;
}

.book-title-link:hover {
    text-decoration: underline !important;
    text-decoration-thickness: 1px;
    text-underline-offset: 5px;
    opacity: 0.9;
}

.meta-chip {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    background-color: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.25);
    margin: 0 6px 8px 0;
    font-size: 0.82rem;
    font-weight: 600;
}

.status-chip {
    display: inline-block;
    padding: 5px 11px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    margin-right: 6px;
    margin-bottom: 6px;
}

.small-muted {
    opacity: 0.75;
    font-size: 0.85rem;
}

.section-title {
    font-size: 1.1rem;
    font-weight: 800;
    margin-bottom: 0.75rem;
}

.tight-line {
    margin-bottom: 0.45rem;
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
        vd.Description,
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


def format_flag(value, true_label, false_label):
    return true_label if value in [True, 1] else false_label


def render_chip(text):
    text = clean(text)
    if text:
        st.markdown(f'<span class="meta-chip">{text}</span>', unsafe_allow_html=True)


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
        <span class="status-chip" style="
            background-color:{color}22;
            color:{color};
            border:1px solid {color}55;
        ">
            {reader_name}: {status}
        </span>
        """,
        unsafe_allow_html=True,
    )


def render_detail_line(label, value, icon=None):
    value = clean(value)
    if not value:
        return

    prefix = f"{icon} " if icon else ""
    st.markdown(
        f'<div class="tight-line"><strong>{prefix}{label}:</strong> {value}</div>',
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

left_col, right_col = st.columns([0.85, 2.15], gap="large")


# =========================================================
# Left column: cover + quick facts
# =========================================================
with left_col:
    cover_path = clean(book.get("CoverImagePath"))

    if cover_path:
        try:
            st.image(load_cover_image_bytes(cover_path), width=280)
        except Exception:
            st.caption("Cover could not be loaded.")
    else:
        st.caption("No cover available.")

    st.markdown("")

    with st.container(border=True):
        st.markdown('<div class="section-title">Quick Facts</div>', unsafe_allow_html=True)

        render_detail_line("Length", book.get("DurationDisplay"), "⏱️")
        render_detail_line("Release Year", book.get("ReleaseYear"), "📅")
        render_detail_line("Publisher", book.get("Publisher"), "🏢")

        if pd.notna(book.get("IsFullCast")):
            render_detail_line(
                "Cast",
                format_flag(book.get("IsFullCast"), "Full cast", "Single narrator"),
                "🎭",
            )

        if pd.notna(book.get("IsAbridged")):
            render_detail_line("Abridged", yes_no(book.get("IsAbridged")), "✂️")


# =========================================================
# Right column: hero + details
# =========================================================
with right_col:
    # -------------------------
    # Hero section
    # -------------------------
    with st.container(border=True):
        st.markdown(
            f"""
            <h1 style="margin-bottom:0.25rem;">
                <a href="{detail_link(book['BookID'])}"
                   target="_blank"
                   class="book-title-link">
                    {book['Title']}
                </a>
            </h1>
            <div class="small-muted">{clean(book.get("Authors"))}</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("")

        series_name = clean(book.get("SeriesName"))
        book_number = format_book_number(book.get("BookNumber"))
        parent_series = clean(book.get("ParentSeriesName"))
        universe = clean(book.get("UniverseName"))
        universe_order = format_book_number(book.get("UniverseReadingOrder"))
        length_type = clean(book.get("LengthType"))
        demographic = clean(book.get("Demographic"))

        if series_name:
            series_display = f"📚 {series_name} #{book_number}" if book_number else f"📚 {series_name}"
        else:
            series_display = "📚 Standalone"

        chips = [series_display]

        if parent_series:
            chips.append(f"🧭 {parent_series}")

        if universe:
            chips.append(f"🌌 {universe}")

        if universe_order:
            chips.append(f"🔢 Order {universe_order}")

        if length_type:
            chips.append(f"⏱️ {length_type}")

        if demographic:
            chips.append(f"👥 {demographic}")

        if pd.notna(book.get("IsFullCast")):
            chips.append(
                "🎭 Full cast"
                if book.get("IsFullCast") in [True, 1]
                else "🎧 Single narrator"
            )

        st.markdown(
            "".join([f'<span class="meta-chip">{chip}</span>' for chip in chips]),
            unsafe_allow_html=True,
        )

    # -------------------------
    # Genres + audiobook details
    # -------------------------
    detail_col1, detail_col2 = st.columns(2, gap="medium")

    with detail_col1:
        with st.container(border=True):
            st.markdown('<div class="section-title">Genres</div>', unsafe_allow_html=True)

            main_genres = clean(book.get("MainGenres"))
            secondary_genres = clean(book.get("SecondaryGenres"))

            if main_genres:
                render_detail_line("Main", main_genres)
            else:
                st.caption("No main genres recorded.")

            if secondary_genres:
                render_detail_line("Secondary", secondary_genres)
            else:
                st.caption("No secondary genres recorded.")

    with detail_col2:
        with st.container(border=True):
            st.markdown('<div class="section-title">Audiobook Details</div>', unsafe_allow_html=True)

            render_detail_line("Narrator(s)", book.get("Narrators"), "🎧")
            render_detail_line("Publisher", book.get("Publisher"), "🏢")
            render_detail_line("Release Year", book.get("ReleaseYear"), "📅")
            render_detail_line("Length", book.get("DurationDisplay"), "⏱️")

            if pd.notna(book.get("IsFullCast")):
                render_detail_line("Full Cast", yes_no(book.get("IsFullCast")), "🎭")

            if pd.notna(book.get("IsAbridged")):
                render_detail_line("Abridged", yes_no(book.get("IsAbridged")), "✂️")

    # -------------------------
    # Description
    # -------------------------
    description = clean(book.get("Description"))

    if description:
        with st.expander("📖 Description", expanded=False):
            st.write(description)