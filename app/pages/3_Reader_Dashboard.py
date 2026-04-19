import math
import pandas as pd
import streamlit as st
import altair as alt

from db import (
    run_query,
    execute_procedure,
    get_book_covers,
    load_cover_image_bytes,
)

st.set_page_config(page_title="Reader Dashboard", page_icon="👤", layout="wide")

st.title("👤 Reader Dashboard")
st.markdown(
    "Browse a reader’s library by status, manage reading progress, review mini book workflow, and view reader-specific stats."
)


# =========================================================
# Cached data loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_readers():
    df = run_query("""
        SELECT ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)
    return df["ReaderName"].tolist()


@st.cache_data(show_spinner=False)
def load_reader_books(reader_name: str):
    """
    Loads the selected reader's books with reading status, rating, and genres.
    Mini-book workflow data is loaded separately from vw_reader_mini_books_dashboard.
    """
    return run_query(
        """
        SELECT
            rb.BookID,
            rb.ReaderName,
            rb.ReadingStatus,
            rb.Rating,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            STRING_AGG(
                CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END,
                ', '
            ) AS MainGenres,
            STRING_AGG(
                CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END,
                ', '
            ) AS SecondaryGenres
        FROM vw_reader_books rb
        JOIN vw_book_details bd
            ON rb.BookID = bd.BookID
        LEFT JOIN book_genres bg
            ON bd.BookID = bg.BookID
        LEFT JOIN genres g
            ON bg.GenreID = g.GenreID
        WHERE rb.ReaderName = ?
        GROUP BY
            rb.BookID,
            rb.ReaderName,
            rb.ReadingStatus,
            rb.Rating,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber
        ORDER BY
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            bd.Title;
        """,
        params=[reader_name],
    )


@st.cache_data(show_spinner=False)
def load_reader_metrics(reader_name: str):
    return {
        "read": run_query("""
            SELECT COUNT(*) AS TotalRead
            FROM vw_reader_books
            WHERE ReaderName = ?
              AND ReadingStatus = 'Read';
        """, params=[reader_name]).iloc[0]["TotalRead"],

        "reading": run_query("""
            SELECT COUNT(*) AS TotalReading
            FROM vw_reader_books
            WHERE ReaderName = ?
              AND ReadingStatus = 'Reading';
        """, params=[reader_name]).iloc[0]["TotalReading"],

        "tbr": run_query("""
            SELECT COUNT(*) AS TotalTBR
            FROM vw_reader_books
            WHERE ReaderName = ?
              AND ReadingStatus = 'TBR';
        """, params=[reader_name]).iloc[0]["TotalTBR"],

        "dnf": run_query("""
            SELECT COUNT(*) AS TotalDNF
            FROM vw_reader_books
            WHERE ReaderName = ?
              AND ReadingStatus = 'DNF';
        """, params=[reader_name]).iloc[0]["TotalDNF"],

        "avg_rating": run_query("""
            SELECT CAST(AVG(Rating) AS DECIMAL(4,2)) AS AvgRating
            FROM vw_reader_books
            WHERE ReaderName = ?
              AND Rating IS NOT NULL;
        """, params=[reader_name]).iloc[0]["AvgRating"],
    }


@st.cache_data(show_spinner=False)
def load_reader_genres_read(reader_name: str):
    return run_query("""
        SELECT TOP 10
            g.GenreName,
            COUNT(*) AS NumBooks
        FROM vw_reader_books rb
        JOIN book_genres bg
            ON rb.BookID = bg.BookID
        JOIN genres g
            ON bg.GenreID = g.GenreID
        WHERE rb.ReaderName = ?
          AND rb.ReadingStatus = 'Read'
          AND bg.GenreType = 'Main'
        GROUP BY g.GenreName
        ORDER BY NumBooks DESC, g.GenreName;
    """, params=[reader_name])


@st.cache_data(show_spinner=False)
def load_reader_mini_dashboard(reader_name: str):
    return run_query("""
        SELECT
            ReaderID,
            ReaderName,
            BookID,
            Authors,
            Title,
            SeriesName,
            BookNumber,
            ReadingStatus,
            IsPrinted,
            IsCrafted,
            MiniBookStage
        FROM vw_reader_mini_books_dashboard
        WHERE ReaderName = ?
        ORDER BY MiniBookStage, Authors, SeriesName, BookNumber, Title;
    """, params=[reader_name])


@st.cache_data(show_spinner=False)
def load_reader_favorite_book(reader_name: str):
    return run_query("""
        SELECT
            ReaderName,
            BookID,
            Title,
            Authors,
            SeriesName,
            BookNumber,
            ReadingStatus,
            Rating,
            FavoriteNotes,
            DateSelected
        FROM vw_reader_favorite_books
        WHERE ReaderName = ?;
    """, params=[reader_name])


@st.cache_data(show_spinner=False)
def load_primary_cover_bytes(book_id: int):
    covers_df = get_book_covers(book_id)

    if covers_df.empty:
        return None

    primary = covers_df[covers_df["IsPrimary"] == True]
    if primary.empty:
        primary = covers_df.iloc[[0]]

    image_path = primary.iloc[0]["ImageFilePath"]

    if not image_path:
        return None

    try:
        return load_cover_image_bytes(image_path)
    except Exception:
        return None
    
@st.cache_data(show_spinner=False)
def load_primary_cover_paths(book_ids: tuple[int, ...]):
    """
    Returns a DataFrame with one row per book that has a cover:
    BookID, ImageFilePath

    Prefers IsPrimary = 1. If no primary exists, falls back to the first cover found.
    """
    if not book_ids:
        return pd.DataFrame(columns=["BookID", "ImageFilePath"])

    placeholders = ",".join(["?"] * len(book_ids))

    return run_query(
        f"""
        WITH ranked_covers AS (
            SELECT
                bc.BookID,
                bc.ImageFilePath,
                ROW_NUMBER() OVER (
                    PARTITION BY bc.BookID
                    ORDER BY
                        CASE WHEN bc.IsPrimary = 1 THEN 0 ELSE 1 END,
                        bc.CoverID
                ) AS rn
            FROM book_covers bc
            WHERE bc.BookID IN ({placeholders})
        )
        SELECT
            BookID,
            ImageFilePath
        FROM ranked_covers
        WHERE rn = 1;
        """,
        params=list(book_ids),
    )

@st.cache_data(show_spinner=False)
def load_books_not_in_tbr(reader_name: str):
    return run_query(
        """
        SELECT
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber
        FROM vw_book_details bd
        WHERE NOT EXISTS (
            SELECT 1
            FROM vw_reader_books rb
            WHERE rb.BookID = bd.BookID
              AND rb.ReaderName = ?
              AND rb.ReadingStatus = 'TBR'
        )
        ORDER BY
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            bd.Title;
        """,
        params=[reader_name],
    )

def build_cover_bytes_map(book_ids):
    """
    Returns {book_id: image_bytes_or_None}
    """
    cover_map = {}

    if not book_ids:
        return cover_map

    cover_paths_df = load_primary_cover_paths(tuple(sorted(set(int(x) for x in book_ids))))

    if cover_paths_df.empty:
        return cover_map

    for _, row in cover_paths_df.iterrows():
        book_id = int(row["BookID"])
        image_path = row["ImageFilePath"]

        if not image_path:
            cover_map[book_id] = None
            continue

        try:
            cover_map[book_id] = load_cover_image_bytes(image_path)
        except Exception:
            cover_map[book_id] = None

    return cover_map

@st.cache_data(show_spinner=False)
def load_all_books_for_reader(reader_name: str):
    return run_query(
        """
        SELECT
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            CAST(NULL AS VARCHAR(50)) AS ReadingStatus,
            CAST(NULL AS DECIMAL(4,2)) AS Rating,
            CAST(NULL AS VARCHAR(MAX)) AS MainGenres,
            CAST(NULL AS VARCHAR(MAX)) AS SecondaryGenres,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM vw_reader_books rb
                    WHERE rb.BookID = bd.BookID
                      AND rb.ReaderName = ?
                      AND rb.ReadingStatus = 'TBR'
                ) THEN 1
                ELSE 0
            END AS IsOnTBR
        FROM vw_book_details bd
        ORDER BY
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            bd.Title;
        """,
        params=[reader_name],
    )

# =========================================================
# Utility helpers
# =========================================================
def clear_page_caches():
    load_reader_books.clear()
    load_reader_metrics.clear()
    load_reader_genres_read.clear()
    load_reader_mini_dashboard.clear()
    load_reader_favorite_book.clear()
    get_book_covers.clear()
    load_cover_image_bytes.clear()
    load_books_not_in_tbr.clear()
    load_all_books_for_reader.clear()
    load_primary_cover_paths.clear()


def format_book_number(value):
    if value is None or pd.isna(value):
        return None

    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(number).rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def yes_no(value):
    if pd.isna(value):
        return "No"

    normalized = str(value).strip().lower()
    return "Yes" if normalized in {"1", "true", "yes"} else "No"


def render_genre_line(label: str, value: str):
    if value and str(value).strip():
        st.caption(f"**{label}:** {value}")


def sort_books(df: pd.DataFrame, sort_option: str) -> pd.DataFrame:
    df = df.copy()

    if sort_option == "Author":
        return df.sort_values(
            by=["Authors", "SeriesName", "BookNumber", "Title"],
            na_position="last"
        )
    elif sort_option == "Title":
        return df.sort_values(by=["Title", "Authors"], na_position="last")
    elif sort_option == "Series":
        return df.sort_values(
            by=["SeriesName", "BookNumber", "Title", "Authors"],
            na_position="last"
        )
    elif sort_option == "Rating":
        return df.sort_values(
            by=["Rating", "Title"],
            ascending=[False, True],
            na_position="last"
        )

    return df


def filter_books(df: pd.DataFrame, search_text: str):
    if not search_text or df.empty:
        return df

    mask = (
        df["Title"].fillna("").str.contains(search_text, case=False, na=False)
        | df["Authors"].fillna("").str.contains(search_text, case=False, na=False)
        | df["SeriesName"].fillna("").str.contains(search_text, case=False, na=False)
        | df["MainGenres"].fillna("").str.contains(search_text, case=False, na=False)
        | df["SecondaryGenres"].fillna("").str.contains(search_text, case=False, na=False)
    )
    return df[mask]


def update_reading_status(book_id: int, reader_name: str, new_status: str, title: str):
    try:
        execute_procedure(
            "SetReadingStatus",
            [int(book_id), reader_name, new_status]
        )
        clear_page_caches()
        st.success(f"Updated **{title}** to **{new_status}**.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not update reading status. Error: {e}")


def update_mini_status(book_id: int, reader_name: str, is_printed: int, is_crafted: int, title: str):
    try:
        execute_procedure(
            "SetMiniBookStatus",
            [int(book_id), reader_name, int(is_printed), int(is_crafted)]
        )
        clear_page_caches()
        st.success(f"Updated mini book status for **{title}**.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not update mini book status. Error: {e}")


def show_bar_chart(df, category_col, value_col, title):
    if df is None or df.empty:
        st.info("No data available for chart.")
        return

    chart = alt.Chart(df).mark_bar().encode(
        y=alt.Y(category_col, sort="-x", title=category_col),
        x=alt.X(value_col, title=value_col),
        tooltip=[category_col, value_col]
    ).properties(title=title)

    st.altair_chart(chart, width='stretch')


def render_book_card(
    book_row,
    reader_name: str,
    show_status_actions: bool = True,
    current_favorite_book_id: int | None = None,
    show_add_to_tbr_button: bool = False,
    cover_bytes=None,
):
    book_id = int(book_row["BookID"])
    title = book_row["Title"]
    authors = book_row["Authors"]
    series_name = book_row["SeriesName"]
    book_number = format_book_number(book_row["BookNumber"])
    reading_status = book_row["ReadingStatus"] if "ReadingStatus" in book_row else None
    rating = book_row["Rating"] if "Rating" in book_row else None
    main_genres = book_row["MainGenres"] if "MainGenres" in book_row else None
    secondary_genres = book_row["SecondaryGenres"] if "SecondaryGenres" in book_row else None
    is_on_tbr = bool(book_row["IsOnTBR"]) if "IsOnTBR" in book_row and pd.notna(book_row["IsOnTBR"]) else False

    with st.container(border=True):
        if cover_bytes:
            st.image(cover_bytes, width='stretch')
        else:
            st.markdown(
                """
                <div style="
                    aspect-ratio: 2 / 3;
                    width: 100%;
                    border-radius: 0.75rem;
                    background: rgba(128,128,128,0.12);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-align: center;
                    padding: 1rem;
                    font-size: 0.95rem;
                    color: #888;
                    border: 1px dashed rgba(128,128,128,0.35);
                    margin-bottom: 0.5rem;
                ">
                    No cover available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(f"**{title}**")
        st.caption(authors)

        if series_name:
            if book_number:
                st.caption(f"Series: {series_name} #{book_number}")
            else:
                st.caption(f"Series: {series_name}")

        if reading_status and not pd.isna(reading_status):
            st.caption(f"Status: {reading_status}")

        if rating is not None and not pd.isna(rating):
            st.caption(f"Rating: {rating}")

        render_genre_line("Main Genres", main_genres)
        render_genre_line("Secondary Genres", secondary_genres)

        if show_add_to_tbr_button:
            st.markdown("")
            if is_on_tbr:
                st.button(
                    "📝 Already on TBR",
                    key=f"all_books_tbr_disabled_{reader_name}_{book_id}",
                    use_container_width=True,
                    disabled=True,
                )
            else:
                if st.button(
                    "➕ Add to TBR",
                    key=f"all_books_tbr_{reader_name}_{book_id}",
                    use_container_width=True,
                ):
                    update_reading_status(book_id, reader_name, "TBR", title)

        if show_status_actions and reading_status:
            st.markdown("")

            if reading_status == "TBR":
                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "▶️ Mark Reading",
                        key=f"reading_{reader_name}_{book_id}",
                        use_container_width=True,
                    ):
                        update_reading_status(book_id, reader_name, "Reading", title)

                with col2:
                    if st.button(
                        "➖ Remove TBR",
                        key=f"remove_tbr_{reader_name}_{book_id}",
                        use_container_width=True,
                    ):
                        update_reading_status(book_id, reader_name, "Unread", title)

            elif reading_status == "Reading":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        "✅ Mark Read",
                        key=f"read_{reader_name}_{book_id}",
                        width='stretch',
                    ):
                        update_reading_status(book_id, reader_name, "Read", title)
                with col2:
                    if st.button(
                        "⛔ Mark DNF",
                        key=f"dnf_{reader_name}_{book_id}",
                        width='stretch',
                    ):
                        update_reading_status(book_id, reader_name, "DNF", title)

            elif reading_status == "Read":
                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "↩️ Move to TBR",
                        key=f"tbr_{reader_name}_{book_id}",
                        use_container_width=True,
                    ):
                        update_reading_status(book_id, reader_name, "TBR", title)

                with col2:
                    if current_favorite_book_id == book_id:
                        st.button(
                            "⭐ Favorite",
                            key=f"favorite_current_{reader_name}_{book_id}",
                            use_container_width=True,
                            disabled=True,
                        )
                    else:
                        if st.button(
                            "⭐ Mark Favorite",
                            key=f"favorite_{reader_name}_{book_id}",
                            use_container_width=True,
                        ):
                            set_favorite_book(book_id, reader_name, title)

            elif reading_status == "DNF":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        "↩️ Move to TBR",
                        key=f"dnf_tbr_{reader_name}_{book_id}",
                        width='stretch',
                    ):
                        update_reading_status(book_id, reader_name, "TBR", title)
                with col2:
                    if st.button(
                        "▶️ Resume",
                        key=f"resume_{reader_name}_{book_id}",
                        width='stretch',
                    ):
                        update_reading_status(book_id, reader_name, "Reading", title)

def render_overview_book_card(
    title: str,
    authors: str,
    series_name=None,
    book_number=None,
    rating=None,
    note=None,
    cover_bytes=None,
    status_label=None,
):
    with st.container():
        if cover_bytes:
            st.image(cover_bytes, width=180)
        else:
            st.markdown(
                """
                <div style="
                    aspect-ratio: 2 / 3;
                    width: 100%;
                    border-radius: 0.75rem;
                    background: rgba(128,128,128,0.12);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-align: center;
                    padding: 1rem;
                    font-size: 0.95rem;
                    color: #888;
                    border: 1px dashed rgba(128,128,128,0.35);
                    margin-bottom: 0.5rem;
                ">
                    No cover available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(f"**{title}**")
        st.caption(authors)

        if pd.notna(series_name):
            formatted_number = format_book_number(book_number)
            if formatted_number:
                st.caption(f"{series_name} #{formatted_number}")
            else:
                st.caption(str(series_name))

        if status_label:
            st.caption(f"Status: {status_label}")

        if rating is not None and not pd.isna(rating):
            st.caption(f"Rating: {rating}")

        if note and str(note).strip():
            st.info(str(note).strip())

def render_books_grid(
    df: pd.DataFrame,
    reader_name: str,
    cards_per_row: int = 7,
    show_status_actions: bool = True,
    current_favorite_book_id: int | None = None,
    show_add_to_tbr_button: bool = False,
):
    if df.empty:
        st.info("No books match the current filters.")
        return

    # Batch-load cover bytes once for the currently visible set of books
    visible_book_ids = df["BookID"].dropna().astype(int).tolist()
    cover_bytes_map = build_cover_bytes_map(visible_book_ids)

    rows = math.ceil(len(df) / cards_per_row)

    for row_index in range(rows):
        cols = st.columns(cards_per_row)
        row_slice = df.iloc[row_index * cards_per_row : (row_index + 1) * cards_per_row]

        for col, (_, book_row) in zip(cols, row_slice.iterrows()):
            with col:
                book_id = int(book_row["BookID"])

                render_book_card(
                    book_row,
                    reader_name,
                    show_status_actions=show_status_actions,
                    current_favorite_book_id=current_favorite_book_id,
                    show_add_to_tbr_button=show_add_to_tbr_button,
                    cover_bytes=cover_bytes_map.get(book_id),
                )


def set_favorite_book(book_id: int, reader_name: str, title: str, favorite_notes: str = None):
    try:
        execute_procedure(
            "SetReaderFavoriteBook",
            [
                reader_name,
                int(book_id),
                favorite_notes.strip() if favorite_notes and favorite_notes.strip() else None,
            ],
        )
        clear_page_caches()
        st.success(f"Set **{title}** as **{reader_name}’s** favorite book.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not set favorite book. Error: {e}")

def render_book_browser(
    tab_df: pd.DataFrame,
    tab_key: str,
    reader_name: str,
    default_view: str = "Cards",
    current_favorite_book_id: int | None = None,
    show_status_actions: bool = True,
    show_add_to_tbr_button: bool = False,
):
    control_col1, control_col2, control_col3 = st.columns([2, 1, 1])

    with control_col1:
        search_text = st.text_input(
            "Search by title, author, series, or genre",
            key=f"search_{tab_key}"
        )

    with control_col2:
        sort_option = st.selectbox(
            "Sort by",
            ["Author", "Title", "Series"],
            key=f"sort_{tab_key}"
        )

    with control_col3:
        view_mode = st.selectbox(
            "View",
            ["Cards", "Table"],
            key=f"view_{tab_key}",
            index=0 if default_view == "Cards" else 1,
        )

    working_df = filter_books(tab_df, search_text)
    working_df = sort_books(working_df, sort_option)

    st.caption(f"{len(working_df)} book(s) shown")

    if view_mode == "Cards":
        render_books_grid(
            working_df,
            reader_name,
            cards_per_row=7,
            show_status_actions=show_status_actions,
            current_favorite_book_id=current_favorite_book_id,
            show_add_to_tbr_button=show_add_to_tbr_button,
        )
    else:
        table_df = working_df.copy()
        table_df["BookNumber"] = table_df["BookNumber"].apply(format_book_number)

        display_cols = ["Authors", "Title", "SeriesName", "BookNumber"]

        if "ReadingStatus" in table_df.columns:
            display_cols.append("ReadingStatus")
        if "Rating" in table_df.columns:
            display_cols.append("Rating")

        display_cols.extend(["MainGenres", "SecondaryGenres"])

        if "IsOnTBR" in table_df.columns:
            table_df["IsOnTBR"] = table_df["IsOnTBR"].apply(lambda x: "Yes" if bool(x) else "No")
            display_cols.append("IsOnTBR")

        st.dataframe(
            table_df[display_cols],
            width='stretch',
            hide_index=True,
        )


# =========================================================
# Load main data
# =========================================================
reader_names = load_readers()

if not reader_names:
    st.info("No readers found.")
    st.stop()

selected_reader = st.selectbox("👤 Select Reader", reader_names)

books_df = load_reader_books(selected_reader)
metrics = load_reader_metrics(selected_reader)
genres_read_df = load_reader_genres_read(selected_reader)
mini_dashboard_df = load_reader_mini_dashboard(selected_reader)
favorite_df = load_reader_favorite_book(selected_reader)
current_favorite_book_id = None if favorite_df.empty else int(favorite_df.iloc[0]["BookID"])

if books_df.empty:
    st.info("No books found for this reader.")
    st.stop()


# =========================================================
# Top metrics
# =========================================================
metric_cols = st.columns(4)

with metric_cols[0]:
    st.metric("Read", int(metrics["read"]))

with metric_cols[1]:
    st.metric("TBR", int(metrics["tbr"]))

with metric_cols[2]:
    st.metric("DNF", int(metrics["dnf"]))

with metric_cols[3]:
    avg_rating = metrics["avg_rating"]
    st.metric("Average Rating", f"{avg_rating:.2f}" if avg_rating is not None else "—")

st.divider()


# =========================================================
# Overview row
# =========================================================
overview_col1, overview_col2 = st.columns([1, 1.35], gap="large")

with overview_col1:
    st.subheader("Currently Reading")

    currently_reading_df = books_df[
        books_df["ReadingStatus"] == "Reading"
    ].copy()

    if currently_reading_df.empty:
        st.caption("Nothing is currently marked as Reading.")
    else:
        currently_reading_df = currently_reading_df.sort_values(
            by=["Authors", "SeriesName", "BookNumber", "Title"],
            na_position="last"
        )

        preview_df = currently_reading_df.head(3)
        reading_cols = st.columns(len(preview_df))

        for col, (_, row) in zip(reading_cols, preview_df.iterrows()):
            with col:
                cover_bytes = load_primary_cover_bytes(int(row["BookID"]))

                render_overview_book_card(
                    title=row["Title"],
                    authors=row["Authors"],
                    series_name=row["SeriesName"],
                    book_number=row["BookNumber"],
                    rating=row["Rating"],
                    cover_bytes=cover_bytes,
                    status_label="Reading",
                )

with overview_col2:
    st.subheader("Favorite Book")

    if favorite_df.empty:
        st.caption("No favorite book selected yet.")
    else:
        favorite = favorite_df.iloc[0]
        favorite_cover = load_primary_cover_bytes(int(favorite["BookID"]))

        render_overview_book_card(
            title=favorite["Title"],
            authors=favorite["Authors"],
            series_name=favorite["SeriesName"],
            book_number=favorite["BookNumber"],
            rating=favorite["Rating"],
            note=favorite["FavoriteNotes"],
            cover_bytes=favorite_cover,
            status_label=favorite["ReadingStatus"],
        )



# =========================================================
# Main tabs
# =========================================================
tab_all, tab_read, tab_tbr, tab_dnf, tab_mini, tab_insights = st.tabs(
    ["📚 All Books", "✅ Read", "📝 TBR", "⛔ DNF", "🎨 Mini Books", "📊 Insights"]
)

with tab_all:
    st.subheader("All Books")
    all_books_df = load_all_books_for_reader(selected_reader)

    render_book_browser(
        all_books_df,
        "all_books",
        selected_reader,
        default_view="Cards",
        current_favorite_book_id=current_favorite_book_id,
        show_status_actions=False,
        show_add_to_tbr_button=True,
    )

with tab_read:
    st.subheader("Read")
    read_df = books_df[books_df["ReadingStatus"] == "Read"].copy()
    render_book_browser(
        read_df,
        "read_books",
        selected_reader,
        default_view="Cards",
        current_favorite_book_id=current_favorite_book_id,
    )

with tab_tbr:
    st.subheader("TBR")

    available_books_df = load_books_not_in_tbr(selected_reader)

    with st.container(border=True):
        st.markdown("### ➕ Add a Book to TBR")
        st.caption("Choose any book not currently on this reader’s TBR list.")

        if available_books_df.empty:
            st.info("All books are already on this reader’s TBR list.")
        else:
            available_books_df = available_books_df.copy()
            available_books_df["SeriesDisplay"] = available_books_df["SeriesName"].fillna("Standalone")
            available_books_df["BookNumberDisplay"] = available_books_df["BookNumber"].apply(
                lambda x: f" #{format_book_number(x)}" if pd.notna(x) else ""
            )
            available_books_df["BookLabel"] = (
                available_books_df["Title"]
                + " — "
                + available_books_df["Authors"]
                + " ("
                + available_books_df["SeriesDisplay"]
                + available_books_df["BookNumberDisplay"]
                + ")"
            )

            with st.form("add_to_tbr_form"):
                selected_label = st.selectbox(
                    "Choose a book",
                    available_books_df["BookLabel"].tolist()
                )
                submitted = st.form_submit_button("Add to TBR", use_container_width=True)

            if submitted:
                selected_row = available_books_df[
                    available_books_df["BookLabel"] == selected_label
                ].iloc[0]

                try:
                    execute_procedure(
                        "SetReadingStatus",
                        [
                            int(selected_row["BookID"]),
                            selected_reader,
                            "TBR",
                        ],
                    )
                    clear_page_caches()
                    st.success(
                        f"Added **{selected_row['Title']}** to **{selected_reader}’s** TBR list."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add book to TBR. Error: {e}")

    st.divider()

    tbr_df = books_df[books_df["ReadingStatus"] == "TBR"].copy()
    render_book_browser(tbr_df, "tbr_books", selected_reader, default_view="Cards")

with tab_dnf:
    st.subheader("DNF")
    dnf_df = books_df[books_df["ReadingStatus"] == "DNF"].copy()
    render_book_browser(dnf_df, "dnf_books", selected_reader, default_view="Table")

with tab_mini:
    st.subheader("Mini Books")

    if mini_dashboard_df.empty:
        st.info("No mini book rows found for this reader.")
    else:
        mini_filter_col1, mini_filter_col2 = st.columns([1, 2])

        with mini_filter_col1:
            selected_stage = st.selectbox(
                "Workflow stage",
                ["All Stages", "To Print", "Printed Not Crafted", "Completed"],
                key="reader_dashboard_mini_stage"
            )

        with mini_filter_col2:
            mini_search = st.text_input(
                "Search mini books by title, author, or series",
                key="reader_dashboard_mini_search"
            )

        filtered_mini_df = mini_dashboard_df.copy()

        if selected_stage != "All Stages":
            filtered_mini_df = filtered_mini_df[filtered_mini_df["MiniBookStage"] == selected_stage]

        if mini_search:
            mask = (
                filtered_mini_df["Title"].str.contains(mini_search, case=False, na=False)
                | filtered_mini_df["Authors"].str.contains(mini_search, case=False, na=False)
                | filtered_mini_df["SeriesName"].fillna("").str.contains(mini_search, case=False, na=False)
            )
            filtered_mini_df = filtered_mini_df[mask]

        st.caption(f"{len(filtered_mini_df)} mini book row(s) shown")

        mini_tab1, mini_tab2, mini_tab3 = st.tabs(
            ["🖨️ To Print", "✂️ Printed Not Crafted", "✅ Completed"]
        )

        display_columns = [
            "Authors",
            "Title",
            "SeriesName",
            "BookNumber",
            "ReadingStatus",
            "IsPrinted",
            "IsCrafted",
            "MiniBookStage",
        ]

        def display_mini_table(stage_name: str):
            stage_df = filtered_mini_df[filtered_mini_df["MiniBookStage"] == stage_name].copy()
            if stage_df.empty:
                st.info(f"No books currently in '{stage_name}'.")
            else:
                stage_df["BookNumber"] = stage_df["BookNumber"].apply(format_book_number)
                stage_df["IsPrinted"] = stage_df["IsPrinted"].apply(yes_no)
                stage_df["IsCrafted"] = stage_df["IsCrafted"].apply(yes_no)
                st.dataframe(stage_df[display_columns], width='stretch', hide_index=True)

        with mini_tab1:
            display_mini_table("To Print")

        with mini_tab2:
            display_mini_table("Printed Not Crafted")

        with mini_tab3:
            display_mini_table("Completed")

        st.divider()
        st.markdown("### Quick Mini Book Update")

        quick_df = filtered_mini_df.copy()
        quick_df["SeriesDisplay"] = quick_df["SeriesName"].fillna("Standalone")
        quick_df["BookNumberDisplay"] = quick_df["BookNumber"].apply(
            lambda x: f" #{format_book_number(x)}" if pd.notna(x) else ""
        )
        quick_df["BookLabel"] = (
            quick_df["Title"]
            + " — "
            + quick_df["Authors"]
            + " ("
            + quick_df["SeriesDisplay"]
            + quick_df["BookNumberDisplay"]
            + ")"
        )

        if quick_df.empty:
            st.info("No mini books available for update with the current filters.")
        else:
            selected_book_label = st.selectbox(
                "Choose a mini book",
                quick_df["BookLabel"].tolist(),
                key="reader_dashboard_mini_book"
            )

            selected_row = quick_df[quick_df["BookLabel"] == selected_book_label].iloc[0]

            detail_col1, detail_col2 = st.columns([1.3, 1])

            with detail_col1:
                st.markdown(f"**{selected_row['Title']}**")
                st.caption(selected_row["Authors"])
                st.caption(
                    f"Series: {selected_row['SeriesName'] if pd.notna(selected_row['SeriesName']) else 'Standalone'}"
                )
                st.caption(
                    f"Stage: {selected_row['MiniBookStage']} | Printed: {yes_no(selected_row['IsPrinted'])} | Crafted: {yes_no(selected_row['IsCrafted'])}"
                )

            with detail_col2:
                action_col1, action_col2, action_col3 = st.columns(3)

                with action_col1:
                    if st.button("🖨️ Mark Printed", key="mini_printed", width='stretch'):
                        update_mini_status(
                            selected_row["BookID"],
                            selected_reader,
                            1,
                            0,
                            selected_row["Title"]
                        )

                with action_col2:
                    if st.button("✅ Complete", key="mini_complete", width='stretch'):
                        update_mini_status(
                            selected_row["BookID"],
                            selected_reader,
                            1,
                            1,
                            selected_row["Title"]
                        )

                with action_col3:
                    if st.button("↺ Reset", key="mini_reset", width='stretch'):
                        update_mini_status(
                            selected_row["BookID"],
                            selected_reader,
                            0,
                            0,
                            selected_row["Title"]
                        )

with tab_insights:
    st.subheader("Insights")

    insight_col1, insight_col2 = st.columns(2, gap="large")

    with insight_col1:
        st.markdown("**Highest Rated Books**")

        highest_rated = run_query("""
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

        if highest_rated.empty:
            st.info("No highly rated books found yet.")
        else:
            st.dataframe(highest_rated, width='stretch', hide_index=True)

    with insight_col2:
        st.markdown("**Genre Breakdown**")

        genre_df = run_query("""
            SELECT TOP 10
                g.GenreName,
                COUNT(*) AS NumBooks
            FROM vw_reader_books rb
            JOIN book_genres bg
                ON rb.BookID = bg.BookID
            JOIN genres g
                ON bg.GenreID = g.GenreID
            WHERE rb.ReaderName = ?
              AND bg.GenreType = 'Main'
            GROUP BY g.GenreName
            ORDER BY NumBooks DESC, g.GenreName;
        """, params=[selected_reader])

        show_bar_chart(
            genre_df,
            "GenreName",
            "NumBooks",
            f"{selected_reader} - Main Genres"
        )

    st.divider()

    shared_reads = run_query("""
        SELECT
            other.ReaderName AS OtherReader,
            COUNT(*) AS BooksReadInCommon
        FROM reading_status rs_self
        JOIN readers self_reader
            ON self_reader.ReaderID = rs_self.ReaderID
        JOIN reading_status rs_other
            ON rs_other.BookID = rs_self.BookID
           AND rs_other.ReaderID <> rs_self.ReaderID
        JOIN readers other
            ON other.ReaderID = rs_other.ReaderID
        WHERE self_reader.ReaderName = ?
          AND rs_self.ReadingStatus = 'Read'
          AND rs_other.ReadingStatus = 'Read'
        GROUP BY other.ReaderName
        ORDER BY BooksReadInCommon DESC, OtherReader;
    """, params=[selected_reader])

    st.markdown("**Shared Reads With Other Readers**")
    if shared_reads.empty:
        st.info("No shared reads found.")
    else:
        st.dataframe(shared_reads, width='stretch', hide_index=True)

    st.divider()
    st.markdown("### Set Favorite Book")

    favorite_options_df = books_df[
        books_df["ReadingStatus"] == "Read"
    ].copy()
    favorite_options_df["SeriesDisplay"] = favorite_options_df["SeriesName"].fillna("Standalone")
    favorite_options_df["BookNumberDisplay"] = favorite_options_df["BookNumber"].apply(
        lambda x: f" #{format_book_number(x)}" if pd.notna(x) else ""
    )
    favorite_options_df["BookLabel"] = (
        favorite_options_df["Title"]
        + " — "
        + favorite_options_df["Authors"]
        + " ("
        + favorite_options_df["SeriesDisplay"]
        + favorite_options_df["BookNumberDisplay"]
        + ")"
    )

    current_favorite_book_id = None if favorite_df.empty else int(favorite_df.iloc[0]["BookID"])

    default_index = 0
    if current_favorite_book_id is not None:
        matches = favorite_options_df.index[
            favorite_options_df["BookID"] == current_favorite_book_id
        ].tolist()
        if matches:
            default_index = favorite_options_df.index.get_loc(matches[0])

    with st.form("set_favorite_book_form"):
        selected_label = st.selectbox(
            "Choose a favorite book",
            favorite_options_df["BookLabel"].tolist(),
            index=default_index
        )

        favorite_notes = st.text_input(
            "Optional note",
            value="" if favorite_df.empty else str(favorite_df.iloc[0]["FavoriteNotes"] or "")
        )

        submitted_favorite = st.form_submit_button("Save Favorite Book")

    if submitted_favorite:
        selected_row = favorite_options_df[
            favorite_options_df["BookLabel"] == selected_label
        ].iloc[0]

        try:
            execute_procedure(
                "SetReaderFavoriteBook",
                [
                    selected_reader,
                    int(selected_row["BookID"]),
                    favorite_notes.strip() if favorite_notes.strip() else None,
                ],
            )
            clear_page_caches()
            st.success(
                f"Set **{selected_row['Title']}** as **{selected_reader}’s** favorite book."
            )
            st.rerun()
        except Exception as e:
            st.error(f"Could not save favorite book. Error: {e}")

    if not favorite_df.empty:
        if st.button("Remove Favorite Book", width='stretch'):
            try:
                execute_procedure("ClearReaderFavoriteBook", [selected_reader])
                clear_page_caches()
                st.success("Favorite book removed.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not remove favorite book. Error: {e}")