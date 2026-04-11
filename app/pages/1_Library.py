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
        vd.ParentSeriesName,
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
        vd.ParentSeriesName,
        vd.UniverseName,
        vd.BookNumber,
        vd.UniverseReadingOrder,
        vd.Full_Cast,
        pc.ImageFilePath
    ORDER BY
        vd.Authors, vd.SeriesName, vd.Title;
    """

    reader_status_query = """
    SELECT
        rb.BookID,
        rb.ReaderName,
        rb.ReadingStatus,
        rb.Rating
    FROM vw_reader_books rb
    ORDER BY
        rb.ReaderName, rb.BookID;
    """

    books_df = run_query(books_query)
    reader_df = run_query(reader_status_query)

    return books_df, reader_df


def build_library_dataframe():
    cache_buster = st.session_state.get("library_cache_buster", 0)
    books_df, reader_df = load_library_data(cache_buster)
    reader_names = load_readers()

    if books_df is None or books_df.empty:
        return None, reader_names

    status_pivot = reader_df.pivot(
        index="BookID",
        columns="ReaderName",
        values="ReadingStatus"
    )

    rating_pivot = reader_df.pivot(
        index="BookID",
        columns="ReaderName",
        values="Rating"
    )

    status_pivot.columns = [f"{col} Status" for col in status_pivot.columns]
    rating_pivot.columns = [f"{col} Rating" for col in rating_pivot.columns]

    status_pivot = status_pivot.reset_index()
    rating_pivot = rating_pivot.reset_index()

    df = books_df.merge(status_pivot, on="BookID", how="left")
    df = df.merge(rating_pivot, on="BookID", how="left")

    df["SortOrder"] = df["UniverseReadingOrder"].fillna(df["BookNumber"])

    return df, reader_names


def format_status(value):
    status_map = {
        "Read": "✅ Read",
        "Unread": "📖 Unread",
        "TBR": "⭐ TBR",
        "Reading": "📘 Reading",
        "DNF": "❌ DNF"
    }
    return status_map.get(value, value)


def clean_status_text(value):
    if pd.isna(value):
        return value

    value = str(value)
    replacements = {
        "✅ ": "",
        "📖 ": "",
        "⭐ ": "",
        "📘 ": "",
        "❌ ": ""
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def format_series_line(series_name, book_number):
    series_text = series_name if pd.notna(series_name) and series_name else "Standalone"

    if pd.notna(book_number):
        return f"{series_text} • Book {book_number}"

    return series_text


def render_status_chip(reader_name, status):
    clean_status = clean_status_text(status)

    color_map = {
        "Read": "#22c55e",
        "Reading": "#3b82f6",
        "TBR": "#f59e0b",
        "Unread": "#6b7280",
        "DNF": "#ef4444"
    }

    color = color_map.get(clean_status, "#6b7280")

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
            {reader_name}: {clean_status}
        </span>
        """,
        unsafe_allow_html=True
    )


def render_genre_chip(genre_name, chip_type="main"):
    if not genre_name:
        return

    style_map = {
        "main": {
            "text": "#c084fc",
            "bg": "#c084fc22",
            "border": "#c084fc55"
        },
        "secondary": {
            "text": "#38bdf8",
            "bg": "#38bdf822",
            "border": "#38bdf855"
        }
    }

    style = style_map.get(chip_type, style_map["secondary"])

    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background-color:{style['bg']};
            color:{style['text']};
            font-size:0.72rem;
            font-weight:600;
            margin-right:6px;
            margin-bottom:6px;
            border:1px solid {style['border']};
        ">
            {genre_name}
        </span>
        """,
        unsafe_allow_html=True
    )


def split_genres(genre_value):
    if pd.isna(genre_value) or not genre_value:
        return []

    return [part.strip() for part in str(genre_value).split(",") if part.strip()]


df, reader_names = build_library_dataframe()

if df is None or df.empty:
    st.info("No books found in the library.")
    st.stop()

search = st.text_input("Search by title, author, series, universe, or genre")

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    sort_option = st.selectbox(
        "Sort by",
        ["Title", "Author", "Series", "Universe Reading Order"]
    )

with filter_col2:
    reader_filter = st.selectbox(
        "Filter reader columns",
        ["All Readers"] + reader_names
    )

with filter_col3:
    view_mode = st.selectbox(
        "View mode",
        ["Table", "Cards"]
    )

if st.button("🔄 Refresh Library Cache"):
    load_library_data.clear()
    st.rerun()

if search:
    mask = (
        df["Title"].str.contains(search, case=False, na=False)
        | df["Authors"].str.contains(search, case=False, na=False)
        | df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
        | df["UniverseName"].fillna("").str.contains(search, case=False, na=False)
        | df["MainGenres"].fillna("").str.contains(search, case=False, na=False)
        | df["SecondaryGenres"].fillna("").str.contains(search, case=False, na=False)
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
    "MainGenres": "Main Genre(s)",
    "SecondaryGenres": "Secondary Genre(s)",
    "Full_Cast": "Full Cast Audio",
    "CoverImagePath": "Cover Image"
})

status_columns = [col for col in df_display.columns if col.endswith(" Status")]
rating_columns = [col for col in df_display.columns if col.endswith(" Rating")]

for col in status_columns:
    df_display[col] = df_display[col].map(format_status).fillna(df_display[col])

for col in rating_columns:
    df_display[col] = df_display[col].round(2)

display_columns = [
    "Title",
    "Author(s)",
    "Universe",
    "Series",
    "Book #",
    "Main Genre(s)",
    "Secondary Genre(s)",
    "Universe Order",
    "Full Cast Audio"
]

reader_columns = []

if reader_filter == "All Readers":
    for reader_name in reader_names:
        status_col = f"{reader_name} Status"
        rating_col = f"{reader_name} Rating"

        if status_col in df_display.columns:
            reader_columns.append(status_col)
        if rating_col in df_display.columns:
            reader_columns.append(rating_col)
else:
    status_col = f"{reader_filter} Status"
    rating_col = f"{reader_filter} Rating"

    if status_col in df_display.columns:
        reader_columns.append(status_col)
    if rating_col in df_display.columns:
        reader_columns.append(rating_col)

display_columns.extend(reader_columns)

if sort_option != "Universe Reading Order" and "Universe Order" in display_columns:
    display_columns.remove("Universe Order")

st.caption(f"{len(df_display)} book(s) shown")

if view_mode == "Table":
    st.dataframe(
        df_display[display_columns],
        width="stretch",
        hide_index=True
    )

else:
    if len(df_display) > 100 and not search:
        st.caption("Showing the first 100 books in card view for speed. Use search to narrow the list.")
        df_display = df_display.head(100)

    cards_per_row = 5
    rows = range(0, len(df_display), cards_per_row)

    for start_idx in rows:
        cols = st.columns(cards_per_row)
        row_slice = df_display.iloc[start_idx:start_idx + cards_per_row]

        for col, (_, row) in zip(cols, row_slice.iterrows()):
            with col:
                with st.container(border=True):
                    cover_loaded = False

                    if row.get("Cover Image"):
                        try:
                            image_bytes = load_cover_image_bytes(row["Cover Image"])
                            st.image(image_bytes, width='stretch')
                            cover_loaded = True
                        except Exception:
                            cover_loaded = False

                    if not cover_loaded:
                        st.caption("No primary cover")

                    st.markdown(f"**{row['Title']}**")
                    st.caption(row["Author(s)"])

                    series_line = format_series_line(row["Series"], row["Book #"])
                    st.caption(f"📚 {series_line}")

                    for reader_col in reader_columns:
                        if reader_col.endswith(" Status"):
                            value = row.get(reader_col)
                            if pd.notna(value):
                                reader_name = reader_col.replace(" Status", "")
                                render_status_chip(reader_name, value)

                    with st.expander("📖 More details"):
                        if pd.notna(row.get("Universe")) and row["Universe"]:
                            st.caption("Universe")
                            st.write(row["Universe"])

                        main_genres = split_genres(row.get("Main Genre(s)"))
                        secondary_genres = split_genres(row.get("Secondary Genre(s)"))

                        if main_genres:
                            st.caption("Main Genres")
                            for genre in main_genres:
                                render_genre_chip(genre, "main")

                        if secondary_genres:
                            st.caption("Secondary Genres")
                            for genre in secondary_genres:
                                render_genre_chip(genre, "secondary")

                        if row["Full Cast Audio"] in [True, 1]:
                            st.caption("Audio")
                            st.write("🎭 Full Cast Audio")

                        if pd.notna(row.get("Universe Order")):
                            st.caption("Universe Order")
                            st.write(row["Universe Order"])

                        for reader_col in reader_columns:
                            if reader_col.endswith(" Rating"):
                                value = row.get(reader_col)
                                if pd.notna(value):
                                    st.caption(reader_col)
                                    st.write(value)