import streamlit as st
import pandas as pd
from db import run_query, load_cover_image_bytes

st.title("📚 Library")


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
        STRING_AGG(
            CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END,
            ', '
        ) AS MainGenres,
        STRING_AGG(
            CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END,
            ', '
        ) AS SecondaryGenres,
        vd.Full_Cast,
        pc.ImageFilePath AS CoverImagePath
    FROM vw_book_details vd
    LEFT JOIN book_genres bg
        ON bg.BookID = vd.BookID
    LEFT JOIN genres g
        ON g.GenreID = bg.GenreID
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
        vd.Full_Cast,
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

    if reader_df.empty:
        df = books_df.copy()
        df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])
        return df, reader_names

    status = reader_df.pivot(index="BookID", columns="ReaderName", values="ReadingStatus")
    rating = reader_df.pivot(index="BookID", columns="ReaderName", values="Rating")

    status.columns = [f"{c} Status" for c in status.columns]
    rating.columns = [f"{c} Rating" for c in rating.columns]

    df = books_df.merge(status.reset_index(), on="BookID", how="left")
    df = df.merge(rating.reset_index(), on="BookID", how="left")

    df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])

    return df, reader_names


# =========================================================
# Cache clearing
# =========================================================
def clear_library_caches():
    load_readers.clear()
    load_library_data.clear()
    build_df.clear()
    load_cover_image_bytes.clear()

    st.session_state["library_cache_buster"] = (
        st.session_state.get("library_cache_buster", 0) + 1
    )


# =========================================================
# Helpers
# =========================================================
def format_book_number(num):
    if pd.isna(num):
        return ""

    try:
        num = float(num)
        if num.is_integer():
            return str(int(num))
        return f"{num:.1f}".rstrip("0").rstrip(".")
    except Exception:
        return str(num)


def format_series(series, num):
    if pd.notna(series):
        formatted_num = format_book_number(num)
        return f"{series} • Book {formatted_num}" if formatted_num else str(series)
    return "Standalone"


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


def render_card(row, reader_cols):
    with st.container(border=True):
        if row.get("CoverImagePath"):
            try:
                st.image(load_cover_image_bytes(row["CoverImagePath"]), width='stretch')
            except Exception:
                st.caption("No cover")
        else:
            st.caption("No cover")

        series_line = format_series(row["SeriesName"], row["BookNumber"])

        st.markdown(
            f"""
            <div style="padding:6px 2px 2px 2px;">
                <div style="font-weight:600; line-height:1.2;">
                    {row['Title']}
                </div>
                <div style="font-size:0.8rem; opacity:0.85;">
                    {row['Authors']}
                </div>
                <div style="font-size:0.72rem; opacity:0.65;">
                    📚 {series_line}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for col in reader_cols:
            if col.endswith("Status"):
                val = clean(row.get(col))
                if val:
                    reader = col.replace(" Status", "")
                    render_status(reader, val)

        book_id = int(row["BookID"])
        details_url = f"/Book_Details?book_id={book_id}"

        html = f"""
<a href="{details_url}" target="_blank" style="text-decoration:none;">
<div style="
    width:100%;
    box-sizing:border-box;
    padding:0.45rem 0.6rem;
    border-radius:0.5rem;
    background-color:rgba(75,85,99,0.9);
    color:white;
    text-align:center;
    font-size:0.85rem;
    line-height:1.2;
    margin:0.25rem;
">
Open details ↗
</div>
</a>
""".strip()

        st.markdown(html, unsafe_allow_html=True)


# =========================================================
# Load page data
# =========================================================
cache_buster = st.session_state.get("library_cache_buster", 0)
df, readers = build_df(cache_buster=cache_buster)


# =========================================================
# Controls
# =========================================================
search = st.text_input("Search")

col1, col2 = st.columns([1, 1])

with col1:
    sort = st.selectbox("Sort by", ["Title", "Author", "Series", "Universe"], index=2)

with col2:
    view = st.selectbox("View", ["Cards", "Table"], index=0)

if st.button("🔄 Refresh Library", width='stretch'):
    clear_library_caches()
    st.rerun()


# =========================================================
# Search
# =========================================================
if search:
    df = df[
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
        | df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
    ]


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
    df = df.sort_values(["UniverseName", "SortOrder"], na_position="last")


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

    st.dataframe(display_df, width='stretch', hide_index=True)

else:
    cards_per_row = 7

    for i in range(0, len(df), cards_per_row):
        cols = st.columns(cards_per_row)
        chunk = df.iloc[i:i + cards_per_row]

        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                render_card(row, reader_cols)