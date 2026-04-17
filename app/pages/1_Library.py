import streamlit as st
import pandas as pd
from db import run_query, load_cover_image_bytes

st.title("📚 Library")


@st.cache_data(show_spinner=False)
def load_readers():
    df = run_query("""
        SELECT ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)
    return df["ReaderName"].tolist()


@st.cache_data(show_spinner=False)
def load_library_data(cache_buster=0):
    books_query = """
    SELECT
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        vd.UniverseName,
        vd.BookNumber,
        vd.UniverseReadingOrder,
        STRING_AGG(CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END, ', ') AS MainGenres,
        STRING_AGG(CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END, ', ') AS SecondaryGenres,
        vd.Full_Cast,
        pc.ImageFilePath AS CoverImagePath
    FROM vw_book_details vd
    LEFT JOIN book_genres bg ON bg.BookID = vd.BookID
    LEFT JOIN genres g ON g.GenreID = bg.GenreID
    LEFT JOIN vw_book_primary_cover pc ON pc.BookID = vd.BookID
    GROUP BY
        vd.BookID, vd.Title, vd.Authors, vd.SeriesName,
        vd.UniverseName, vd.BookNumber, vd.UniverseReadingOrder,
        vd.Full_Cast, pc.ImageFilePath
    """

    reader_query = """
    SELECT BookID, ReaderName, ReadingStatus, Rating
    FROM vw_reader_books
    """

    return run_query(books_query), run_query(reader_query)


def build_df():
    books_df, reader_df = load_library_data()
    reader_names = load_readers()

    status = reader_df.pivot(index="BookID", columns="ReaderName", values="ReadingStatus")
    rating = reader_df.pivot(index="BookID", columns="ReaderName", values="Rating")

    status.columns = [f"{c} Status" for c in status.columns]
    rating.columns = [f"{c} Rating" for c in rating.columns]

    df = books_df.merge(status.reset_index(), on="BookID", how="left")
    df = df.merge(rating.reset_index(), on="BookID", how="left")

    df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])

    return df, reader_names


def format_series(series, num):
    if pd.notna(series):
        return f"{series} • Book {int(num)}" if pd.notna(num) else series
    return "Standalone"


def clean(val):
    if pd.isna(val): return None
    return str(val)


def render_status(reader, status):
    if not status: return

    colors = {
        "Read": "#22c55e",
        "Reading": "#3b82f6",
        "TBR": "#f59e0b",
        "Unread": "#6b7280",
        "DNF": "#ef4444"
    }

    c = colors.get(status, "#6b7280")

    st.markdown(f"""
    <span style="
        padding:3px 8px;
        border-radius:999px;
        background:{c}22;
        color:{c};
        font-size:0.7rem;
        margin-right:4px;
    ">{reader}: {status}</span>
    """, unsafe_allow_html=True)


def render_card(row, reader_cols):
    with st.container(border=True):

        # COVER
        if row.get("CoverImagePath"):
            try:
                st.image(load_cover_image_bytes(row["CoverImagePath"]), width='stretch')
            except:
                st.caption("No cover")
        else:
            st.caption("No cover")

        # TITLE + AUTHOR + SERIES (clean, stacked)
        series_line = format_series(row["SeriesName"], row["BookNumber"])

        st.markdown(f"""
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
        """, unsafe_allow_html=True)

        # STATUS CHIPS
        for col in reader_cols:
            if col.endswith("Status"):
                val = clean(row.get(col))
                if val:
                    reader = col.replace(" Status", "")
                    render_status(reader, val)

        # BUTTON
        if st.button("Open details", key=f"open_{row['BookID']}", width='stretch'):
            st.session_state["selected_book_id"] = row["BookID"]
            st.switch_page("pages/2_Book_Details.py")



# LOAD

df, readers = build_df()

search = st.text_input("Search")

col1, col2 = st.columns(2)

with col1:
    sort = st.selectbox("Sort by", ["Title", "Author", "Series", "Universe"], index=2)

with col2:
    view = st.selectbox("View", ["Cards", "Table"], index=0)

# SEARCH
if search:
    df = df[
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
        | df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
    ]

# SORT
if sort == "Series":
    df = df.sort_values(["SeriesName", "BookNumber", "Title"])
elif sort == "Author":
    df = df.sort_values(["Authors", "Title"])
elif sort == "Title":
    df = df.sort_values(["Title"])
elif sort == "Universe":
    df = df.sort_values(["UniverseName", "SortOrder"])

# ALL READERS ALWAYS
reader_cols = []
for r in readers:
    for suffix in ["Status", "Rating"]:
        col = f"{r} {suffix}"
        if col in df.columns:
            reader_cols.append(col)

st.caption(f"{len(df)} books")

# VIEW
if view == "Table":
    st.dataframe(df, width='stretch')

else:
    cards_per_row = 7

    for i in range(0, len(df), cards_per_row):
        cols = st.columns(cards_per_row)
        chunk = df.iloc[i:i+cards_per_row]

        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                render_card(row, reader_cols)
