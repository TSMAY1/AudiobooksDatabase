import streamlit as st
import pandas as pd
from ui import configure_page

from db import (
    bump_book_related_caches,
    run_query,
    load_cover_image_bytes,
    format_book_number,
    format_duration,
    format_series,
    detail_link,
)
configure_page("Library", icon="📚")
st.title("📚 Library")

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
def load_readers(cache_buster: int = 0):
    df = run_query("""
        SELECT ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)
    return df["ReaderName"].tolist()


@st.cache_data(show_spinner=False)
def load_narrators(cache_buster: int = 0):
    df = run_query("""
        SELECT NarratorName
        FROM narrators
        ORDER BY NarratorName;
    """)
    return df["NarratorName"].tolist()

@st.cache_data(show_spinner=False)
def load_publishers(cache_buster: int = 0):
    df = run_query("""
        SELECT DISTINCT Publisher
        FROM vw_book_audiobooks
        WHERE Publisher IS NOT NULL
        ORDER BY Publisher;
    """)
    return df["Publisher"].tolist()


@st.cache_data(show_spinner=False)
def load_release_years(cache_buster: int = 0):
    df = run_query("""
        SELECT DISTINCT ReleaseYear
        FROM vw_book_audiobooks
        WHERE ReleaseYear IS NOT NULL
        ORDER BY ReleaseYear DESC;
    """)
    return df["ReleaseYear"].astype(int).tolist()

@st.cache_data(show_spinner=False)
def load_library_data(cache_buster: int = 0):
    books_query = """
    SELECT
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        vd.UniverseName,
        vd.BookNumber,
        vd.UniverseReadingOrder,
        vd.DateAdded,
        ab.Publishers,
        ab.ReleaseYear,
        ab.IsFullCast,
        STRING_AGG(
            CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END,
            ', '
        ) AS MainGenres,
        STRING_AGG(
            CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END,
            ', '
        ) AS SecondaryGenres,
        ab.Narrators,
        ab.DurationMinutes,
        pc.ImageFilePath AS CoverImagePath
    FROM vw_book_details vd
    LEFT JOIN book_genres bg
        ON bg.BookID = vd.BookID
    LEFT JOIN genres g
        ON g.GenreID = bg.GenreID
    LEFT JOIN (
        SELECT
            BookID,
            STRING_AGG(Narrators, ', ') AS Narrators,
            MAX(DurationMinutes) AS DurationMinutes,
            STRING_AGG(Publisher, ', ') AS Publishers,
            MAX(ReleaseYear) AS ReleaseYear,
            MAX(CAST(IsFullCast AS INT)) AS IsFullCast
        FROM vw_book_audiobooks
        GROUP BY BookID
    ) ab
        ON ab.BookID = vd.BookID
    LEFT JOIN vw_book_primary_cover pc
        ON pc.BookID = vd.BookID
    GROUP BY
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        vd.UniverseName,
        vd.BookNumber,
        vd.UniverseReadingOrder,
        vd.DateAdded,
        ab.Narrators,
        ab.DurationMinutes,
        ab.IsFullCast,
        ab.Publishers,
        ab.ReleaseYear,
        pc.ImageFilePath
    """

    reader_query = """
    SELECT
        BookID,
        ReaderName,
        ReadingStatus,
        Rating
    FROM vw_reader_books
    """

    books_df = run_query(books_query)
    reader_df = run_query(reader_query)
    return books_df, reader_df


@st.cache_data(show_spinner=False)
def build_df(cache_buster: int = 0):
    books_df, reader_df = load_library_data(cache_buster=cache_buster)
    reader_names = load_readers(cache_buster=cache_buster)
    narrator_names = load_narrators(cache_buster=cache_buster)
    publisher_names = load_publishers(cache_buster=cache_buster)
    release_years = load_release_years(cache_buster=cache_buster)

    if reader_df.empty:
        df = books_df.copy()
        df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])
        return df, reader_names, narrator_names, publisher_names, release_years

    status = reader_df.pivot(index="BookID", columns="ReaderName", values="ReadingStatus")
    rating = reader_df.pivot(index="BookID", columns="ReaderName", values="Rating")

    status.columns = [f"{c} Status" for c in status.columns]
    rating.columns = [f"{c} Rating" for c in rating.columns]

    df = books_df.merge(status.reset_index(), on="BookID", how="left")
    df = df.merge(rating.reset_index(), on="BookID", how="left")

    df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])

    return df, reader_names, narrator_names, publisher_names, release_years


# =========================================================
# Cache clearing
# =========================================================
def clear_library_caches():
    load_readers.clear()
    load_narrators.clear()
    load_library_data.clear()
    build_df.clear()
    load_cover_image_bytes.clear()
    load_publishers.clear()
    load_release_years.clear()

    bump_book_related_caches()


# =========================================================
# Helpers
# =========================================================


def clean(val):
    if pd.isna(val):
        return None
    return str(val)


def render_status(reader, status):
    if not status:
        return

    colors = {
        "Read": "#22c55e",
        "Reading": "#3b82f6",
        "TBR": "#f59e0b",
        "Unread": "#6b7280",
        "DNF": "#ef4444",
    }

    c = colors.get(status, "#6b7280")

    st.markdown(
        f"""
        <span style="
            padding:3px 8px;
            border-radius:999px;
            background:{c}22;
            color:{c};
            font-size:0.7rem;
            margin-right:4px;
            margin-bottom:4px;
            display:inline-block;
        ">{reader}: {status}</span>
        """,
        unsafe_allow_html=True,
    )


def render_card(row):
    with st.container(border=True):
        if row.get("CoverImagePath"):
            try:
                st.image(load_cover_image_bytes(row["CoverImagePath"]), width="stretch")
            except Exception:
                st.caption("No cover")
        else:
            st.caption("No cover")

        series_line = format_series(row["SeriesName"], row["BookNumber"])
        details_url = detail_link(row["BookID"])

        meta_lines = []

        if pd.notna(row.get("DurationMinutes")):
            meta_lines.append(f"⏱️ {format_duration(row['DurationMinutes'])}")

        if pd.notna(row.get("ReleaseYear")):
            meta_lines.append(f"📅 {int(row['ReleaseYear'])}")

        if row.get("Publishers"):
            meta_lines.append(f"🏢 {row['Publishers']}")

        if int(row.get("IsFullCast") or 0) == 1:
            meta_lines.append("🎭 Full cast")

        meta_html = "".join(
            f"""
            <div style="
                font-size:0.72rem;
                opacity:0.65;
                margin-top:0.12rem;
                line-height:1.2;
            ">
                {line}
            </div>
            """
            for line in meta_lines
        )

        st.markdown("<div style='height:0.35rem;'></div>", unsafe_allow_html=True)

        st.markdown(
            f"""
            <div style="line-height:1.2;">
                <a class="book-title-link" href="{details_url}" target="_self">
                    {row["Title"]}
                </a>
                <div style="font-size:0.78rem; opacity:0.75; margin-top:0.15rem;">
                    {row["Authors"]}
                </div>
                <div style="font-size:0.75rem; opacity:0.65; margin-top:0.12rem;">
                    {series_line}
                </div>
                {meta_html}
            </div>
            """,
            unsafe_allow_html=True,
            )

        st.markdown("<div style='height:0.35rem;'></div>", unsafe_allow_html=True)


# =========================================================
# Load page data
# =========================================================
cache_buster = st.session_state.get("library_cache_buster", 0)
df, readers, narrators, publishers, release_years = build_df(cache_buster=cache_buster)


# =========================================================
# Controls
# =========================================================
search = st.text_input("Search")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    sort = st.selectbox(
        "Sort by",
        [
            "Title",
            "Author",
            "Series",
            "Universe",
            "Recently Added",
            "Audiobook Length: Shortest First",
            "Audiobook Length: Longest First",
        ],
        index=2,
    )

with col2:
    view = st.selectbox("View", ["Cards", "Table"], index=0)

with col3:
    selected_narrator = st.selectbox(
        "Narrator",
        ["All narrators"] + narrators,
    )

filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])

with filter_col1:
    selected_publisher = st.selectbox(
        "Publisher",
        ["All publishers"] + publishers,
    )

with filter_col2:
    selected_release_year = st.selectbox(
        "Release year",
        ["All years"] + release_years,
    )

with filter_col3:
    full_cast_filter = st.selectbox(
        "Full cast",
        ["All", "Full cast only", "Traditional Audiobooks only"],
    )

if st.button("🔄 Refresh Library", width="stretch"):
    clear_library_caches()
    st.rerun()


# =========================================================
# Search and filters
# =========================================================
if search:
    df = df[
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
        | df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
        | df["UniverseName"].fillna("").str.contains(search, case=False, na=False)
        | df["Narrators"].fillna("").str.contains(search, case=False, na=False)
    ]

if selected_narrator != "All narrators":
    df = df[
        df["Narrators"]
        .fillna("")
        .str.contains(selected_narrator, case=False, regex=False)
    ]

if selected_publisher != "All publishers":
    df = df[
        df["Publishers"]
        .fillna("")
        .str.contains(selected_publisher, case=False, regex=False)
    ]

if selected_release_year != "All years":
    df = df[df["ReleaseYear"] == selected_release_year]

if full_cast_filter == "Full cast only":
    df = df[df["IsFullCast"].fillna(0).astype(int) == 1]

elif full_cast_filter == "Traditional Audiobooks only":
    df = df[df["IsFullCast"].fillna(0).astype(int) == 0]




# =========================================================
# Sort
# =========================================================
if sort == "Series":
    df = df.sort_values(["SeriesName", "BookNumber", "Title"], na_position="last")
elif sort == "Author":
    df = df.sort_values(["Authors", "Title"], na_position="last")
elif sort == "Title":
    df = df.sort_values(["Title"], na_position="last")
elif sort == "Universe":
    df["UniverseSort"] = (
        df["UniverseName"]
        .fillna(df["SeriesName"])
        .fillna("Standalone")
    )

    df["UniverseOrderSort"] = (
        df["UniverseReadingOrder"]
        .fillna(df["BookNumber"])
        .fillna(999999)
    )

    df = df.sort_values(
        ["UniverseSort", "UniverseOrderSort", "SeriesName", "BookNumber", "Title"],
        na_position="last",
    )
elif sort == "Recently Added":
    df = df.sort_values(
        ["DateAdded", "Title"],
        ascending=[False, True],
        na_position="last",
    )
elif sort == "Audiobook Length: Shortest First":
    df = df.sort_values(["DurationMinutes", "Title"], na_position="last")
elif sort == "Audiobook Length: Longest First":
    df = df.sort_values(
        ["DurationMinutes", "Title"],
        ascending=[False, True],
        na_position="last",
    )


# =========================================================
# Reader columns
# =========================================================
reader_cols = []
for r in readers:
    for suffix in ["Status", "Rating"]:
        col = f"{r} {suffix}"
        if col in df.columns:
            reader_cols.append(col)

st.caption(f"{len(df)} books")


# =========================================================
# View
# =========================================================
if view == "Table":
    display_df = df.copy()

    if "BookNumber" in display_df.columns:
        display_df["BookNumber"] = display_df["BookNumber"].apply(format_book_number)

    if "UniverseReadingOrder" in display_df.columns:
        display_df["UniverseReadingOrder"] = display_df["UniverseReadingOrder"].apply(format_book_number)

    if "DurationMinutes" in display_df.columns:
        display_df["Duration"] = display_df["DurationMinutes"].apply(format_duration)
        display_df = display_df.drop(columns=["DurationMinutes"], errors="ignore")

    st.dataframe(display_df, width="stretch", hide_index=True)

else:
    cards_per_row = 7

    for i in range(0, len(df), cards_per_row):
        cols = st.columns(cards_per_row)
        chunk = df.iloc[i:i + cards_per_row]

        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                render_card(row)