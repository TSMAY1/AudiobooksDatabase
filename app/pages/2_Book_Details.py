import streamlit as st
import pandas as pd
from db import run_query, load_cover_image_bytes, execute_procedure

st.title("📖 Book Details")

query_params = st.query_params
query_book_id = query_params.get("book_id")

if query_book_id:
    st.session_state["selected_book_id"] = int(query_book_id)

STATUS_OPTIONS = ["Unread", "TBR", "Reading", "Read", "DNF"]
RATING_ALLOWED_STATUSES = {"Read", "DNF"}


# =========================================================
# Cached loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_book_detail(book_id: int, cache_buster: int = 0):
    book_query = """
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
    WHERE vd.BookID = ?
    GROUP BY
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
        vd.Full_Cast,
        pc.ImageFilePath;
    """

    reader_query = """
    SELECT
        rb.BookID,
        rb.ReaderName,
        rb.ReadingStatus,
        rb.Rating
    FROM vw_reader_books rb
    WHERE rb.BookID = ?
    ORDER BY rb.ReaderName, rb.BookID;
    """

    book_df = run_query(book_query, params=[book_id])
    reader_df = run_query(reader_query, params=[book_id])
    return book_df, reader_df


@st.cache_data(show_spinner=False)
def load_all_titles():
    return run_query("""
        SELECT BookID, Title
        FROM books
        ORDER BY Title;
    """)


@st.cache_data(show_spinner=False)
def load_readers():
    df = run_query("""
        SELECT ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)
    return df["ReaderName"].tolist()


@st.cache_data(show_spinner=False)
def load_reader_status_lookup(book_id: int, cache_buster: int = 0):
    df = run_query("""
        SELECT
            r.ReaderName,
            rs.ReadingStatus
        FROM reading_status rs
        JOIN readers r
            ON rs.ReaderID = r.ReaderID
        WHERE rs.BookID = ?
    """, params=[book_id])

    return {
        row["ReaderName"]: row["ReadingStatus"]
        for _, row in df.iterrows()
    }


@st.cache_data(show_spinner=False)
def get_current_reader_book_status(
    book_id: int,
    reader_name: str,
    cache_buster: int = 0,
) -> tuple[str, float | None]:
    df = run_query(
        """
        SELECT TOP 1
            rb.ReadingStatus,
            rb.Rating
        FROM vw_reader_books rb
        WHERE rb.BookID = ?
          AND rb.ReaderName = ?;
        """,
        params=[book_id, reader_name],
    )

    if df.empty:
        return "Unread", None

    current_status = df.iloc[0]["ReadingStatus"]
    current_rating = df.iloc[0]["Rating"]

    if pd.isna(current_status):
        current_status = "Unread"

    if pd.isna(current_rating):
        current_rating = None

    return current_status, current_rating


@st.cache_data(show_spinner=False)
def load_book_for_edit(book_id: int, cache_buster: int = 0):
    return run_query("""
        SELECT
            BookID,
            Title,
            Authors,
            SeriesName,
            BookNumber,
            UniverseReadingOrder,
            LengthType,
            Demographic,
            Full_Cast,
            Notes
        FROM vw_book_edit_details
        WHERE BookID = ?;
    """, params=[book_id])


# =========================================================
# Cache clearing
# =========================================================
def clear_book_details_caches():
    load_book_detail.clear()
    load_all_titles.clear()
    load_readers.clear()
    load_reader_status_lookup.clear()
    get_current_reader_book_status.clear()
    load_book_for_edit.clear()
    load_cover_image_bytes.clear()

    st.session_state["book_details_cache_buster"] = (
        st.session_state.get("book_details_cache_buster", 0) + 1
    )
    st.session_state["library_cache_buster"] = (
        st.session_state.get("library_cache_buster", 0) + 1
    )


# =========================================================
# Helpers
# =========================================================
def clean_status_text(value):
    if pd.isna(value):
        return value

    value = str(value)
    replacements = {
        "✅ ": "",
        "📖 ": "",
        "⭐ ": "",
        "📘 ": "",
        "❌ ": "",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def add_to_tbr(book_id: int, reader_name: str, title: str):
    try:
        execute_procedure(
            "SetReadingStatus",
            [
                int(book_id),
                reader_name,
                "TBR",
            ],
        )
        clear_book_details_caches()
        st.success(f"Added **{title}** to **{reader_name}’s** TBR.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not add to TBR. Error: {e}")


def render_status_chip(reader_name, status):
    clean_status = clean_status_text(status)

    color_map = {
        "Read": "#22c55e",
        "Reading": "#3b82f6",
        "TBR": "#f59e0b",
        "Unread": "#6b7280",
        "DNF": "#ef4444",
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
        unsafe_allow_html=True,
    )


def split_genres(genre_value):
    if pd.isna(genre_value) or not genre_value:
        return []
    return [part.strip() for part in str(genre_value).split(",") if part.strip()]


def render_meta_row(label, value, icon=None):
    if value is None or value == "":
        return

    prefix = f"{icon} " if icon else ""
    st.markdown(f"**{prefix}{label}:** {value}")


# =========================================================
# Book selection
# =========================================================
book_id = st.session_state.get("selected_book_id")

if not book_id:
    st.warning("No book selected.")

    all_titles = load_all_titles()
    if not all_titles.empty:
        selected_title = st.selectbox(
            "Jump to a book",
            all_titles["Title"].tolist(),
        )

        if st.button("Open selected book", width='stretch'):
            selected_row = all_titles[all_titles["Title"] == selected_title].iloc[0]
            st.session_state["selected_book_id"] = int(selected_row["BookID"])
            st.rerun()

    if st.button("⬅ Back to Library"):
        st.switch_page("pages/1_Library.py")
    st.stop()


# =========================================================
# Load page data
# =========================================================
cache_buster = st.session_state.get("book_details_cache_buster", 0)

book_df, reader_df = load_book_detail(book_id, cache_buster=cache_buster)
reader_status_lookup = load_reader_status_lookup(book_id, cache_buster=cache_buster)

if book_df.empty:
    st.error("Book not found.")
    if st.button("⬅ Back to Library"):
        st.switch_page("pages/1_Library.py")
    st.stop()

book = book_df.iloc[0]
title = book["Title"]

main_genres = split_genres(book.get("MainGenres"))
secondary_genres = split_genres(book.get("SecondaryGenres"))


# =========================================================
# Header
# =========================================================
header_left, header_right = st.columns([1, 2])

with header_left:
    cover_path = book.get("CoverImagePath")
    if pd.notna(cover_path) and cover_path:
        try:
            image_bytes = load_cover_image_bytes(cover_path)
            st.image(image_bytes, width=220)
        except Exception:
            st.caption("Cover could not be loaded.")
    else:
        st.caption("No primary cover")

    st.markdown("### Actions")

    if st.button("⬅ Back to Library", width='stretch'):
        st.switch_page("pages/1_Library.py")

    if st.button("🖼️ Manage Covers", width='stretch'):
        st.session_state["navigate_to_cover_book_id"] = int(book_id)
        st.switch_page("pages/6_Manage_Covers.py")

    button_col1, button_col2 = st.columns(2)

    with button_col1:
        angela_status = reader_status_lookup.get("Angela")

        if angela_status == "TBR":
            st.button("✔ Angela TBR", disabled=True, width='stretch')
        else:
            if st.button("➕ Angela TBR", width='stretch'):
                add_to_tbr(book_id, "Angela", title)

    with button_col2:
        tori_status = reader_status_lookup.get("Tori")

        if tori_status == "TBR":
            st.button("✔ Tori TBR", disabled=True, width='stretch')
        else:
            if st.button("➕ Tori TBR", width='stretch'):
                add_to_tbr(book_id, "Tori", title)

with header_right:
    with st.container(border=True):
        st.markdown(f"## {book['Title']}")
        st.caption(book["Authors"])

        st.markdown("### Summary")

        if pd.notna(book.get("SeriesName")) and book["SeriesName"]:
            if pd.notna(book.get("BookNumber")):
                render_meta_row("Series", f"{book['SeriesName']} • Book {book['BookNumber']}", "📚")
            else:
                render_meta_row("Series", book["SeriesName"], "📚")
        else:
            render_meta_row("Series", "Standalone", "📚")

        if pd.notna(book.get("UniverseName")) and book["UniverseName"]:
            render_meta_row("Universe", book["UniverseName"], "🌌")

        if pd.notna(book.get("UniverseReadingOrder")):
            render_meta_row("Universe Reading Order", book["UniverseReadingOrder"], "🔢")

        if book["Full_Cast"] in [True, 1]:
            render_meta_row("Audio", "Full Cast Audio", "🎭")
        else:
            render_meta_row("Audio", "Standard Audiobook", "🎧")

        if pd.notna(book.get("LengthType")) and book["LengthType"]:
            render_meta_row("Length Type", book["LengthType"], "⏱️")

        if pd.notna(book.get("Demographic")) and book["Demographic"]:
            render_meta_row("Demographic", book["Demographic"], "👥")

    with st.container(border=True):
        st.markdown("### Reader Status")
        if reader_df.empty or reader_df["ReadingStatus"].dropna().empty:
            st.caption("No reader statuses recorded yet.")
        else:
            for _, row in reader_df.iterrows():
                if pd.notna(row.get("ReadingStatus")):
                    render_status_chip(row["ReaderName"], row["ReadingStatus"])


st.divider()


# =========================================================
# Tabs
# =========================================================
overview_tab, edit_tab, reading_tab, genres_tab = st.tabs(
    ["Overview", "Edit", "Reading", "Genres"]
)

with overview_tab:
    info_left, info_right = st.columns(2)

    with info_left:
        with st.container(border=True):
            st.markdown("### Genres")

            if main_genres:
                st.markdown("**Main Genres**")
                st.write(", ".join(main_genres))
            else:
                st.caption("No main genres recorded.")

            st.markdown("")

            if secondary_genres:
                st.markdown("**Secondary Genres**")
                st.write(", ".join(secondary_genres))
            else:
                st.caption("No secondary genres recorded.")

    with info_right:
        with st.container(border=True):
            st.markdown("### Library Notes")
            if pd.notna(book.get("Notes")) and str(book["Notes"]).strip():
                st.write(book["Notes"])
            else:
                st.caption("No notes recorded for this book.")

with edit_tab:
    st.markdown("### Edit Book Details")
    st.caption("Update core metadata for this book.")

    edit_df = load_book_for_edit(int(book["BookID"]), cache_buster=cache_buster)

    if edit_df.empty:
        st.error("Could not load book details for editing.")
    else:
        edit_book = edit_df.iloc[0]

        current_title = str(edit_book["Title"])
        current_authors = "" if pd.isna(edit_book["Authors"]) else str(edit_book["Authors"])
        current_series = str(edit_book["SeriesName"])
        current_book_number = "" if pd.isna(edit_book["BookNumber"]) else str(edit_book["BookNumber"])
        current_universe_order = "" if pd.isna(edit_book["UniverseReadingOrder"]) else str(edit_book["UniverseReadingOrder"])
        current_length_type = "" if pd.isna(edit_book["LengthType"]) else str(edit_book["LengthType"])
        current_demographic = "" if pd.isna(edit_book["Demographic"]) else str(edit_book["Demographic"])
        current_notes = "" if pd.isna(edit_book["Notes"]) else str(edit_book["Notes"])
        current_full_cast = bool(edit_book["Full_Cast"]) if pd.notna(edit_book["Full_Cast"]) else False

        series_options_df = run_query("""
            SELECT SeriesName
            FROM series
            ORDER BY SeriesName;
        """)
        series_options = series_options_df["SeriesName"].tolist()

        if current_series not in series_options:
            series_options = [current_series] + series_options

        with st.form(f"edit_details_form_{book['BookID']}"):
            new_title = st.text_input("Title", value=current_title)

            series_name = st.selectbox(
                "Series",
                options=series_options,
                index=series_options.index(current_series),
                help="Use Standalone for books not part of a series.",
            )

            new_series_name = st.text_input(
                "Or create a new series",
                value="",
            )

            authors = st.text_input(
                "Authors (comma-separated)",
                value=current_authors,
            )

            col1, col2 = st.columns(2)

            with col1:
                book_number_text = st.text_input(
                    "Book Number",
                    value=current_book_number,
                )

            with col2:
                universe_order_text = st.text_input(
                    "Universe Reading Order",
                    value=current_universe_order,
                )

            col3, col4 = st.columns(2)

            with col3:
                length_type = st.text_input(
                    "Length Type",
                    value=current_length_type,
                )

            with col4:
                demographic = st.text_input(
                    "Demographic",
                    value=current_demographic,
                )

            full_cast = st.checkbox(
                "Full Cast Audio",
                value=current_full_cast,
            )

            notes = st.text_area(
                "Notes",
                value=current_notes,
                height=140,
            )

            submitted = st.form_submit_button("💾 Save Changes", width='stretch')

        if submitted:
            try:
                final_series_name = new_series_name.strip() if new_series_name.strip() else series_name

                book_number = float(book_number_text) if book_number_text.strip() else None
                universe_order = float(universe_order_text) if universe_order_text.strip() else None

                execute_procedure(
                    "UpdateBookCoreDetails",
                    [
                        int(book["BookID"]),
                        new_title.strip(),
                        final_series_name.strip(),
                        book_number,
                        universe_order,
                        length_type.strip() if length_type.strip() else None,
                        demographic.strip() if demographic.strip() else None,
                        1 if full_cast else 0,
                        notes.strip() if notes.strip() else None,
                    ],
                )

                execute_procedure(
                    "UpdateBookAuthors",
                    [
                        int(book["BookID"]),
                        authors.strip(),
                    ],
                )

                clear_book_details_caches()
                st.toast("Book details updated.", icon="✅")
                st.rerun()

            except ValueError:
                st.error("Book Number and Universe Reading Order must be valid numbers.")
            except Exception as e:
                st.error(f"Error: {e}")

with reading_tab:
    st.markdown("### Update Reading Status")
    st.caption("Update reading progress and ratings for each reader for this book.")

    readers = load_readers()

    if not readers:
        st.info("No readers found.")
    else:
        for reader_name in readers:
            current_status, current_rating = get_current_reader_book_status(
                int(book["BookID"]),
                reader_name,
                cache_buster=cache_buster,
            )

            default_status_index = (
                STATUS_OPTIONS.index(current_status)
                if current_status in STATUS_OPTIONS
                else 0
            )

            default_rating = float(current_rating) if current_rating is not None else 4.0
            default_save_rating = current_rating is not None

            with st.container(border=True):
                st.markdown(f"#### 👤 {reader_name}")

                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.caption(f"Current Status: {current_status}")
                with info_col2:
                    st.caption(f"Current Rating: {current_rating if current_rating is not None else '—'}")

                status_widget_key = f"details_status_{book['BookID']}_{reader_name}"
                rating_widget_key = f"details_rating_{book['BookID']}_{reader_name}"
                save_rating_widget_key = f"details_save_rating_{book['BookID']}_{reader_name}"
                form_key = f"reading_status_form_{book['BookID']}_{reader_name}"

                with st.form(form_key):
                    new_status = st.selectbox(
                        f"Reading Status for {reader_name}",
                        STATUS_OPTIONS,
                        index=default_status_index,
                        key=status_widget_key,
                        help="Unread = not started, TBR = want to read later.",
                    )

                    if new_status in RATING_ALLOWED_STATUSES:
                        new_rating = st.slider(
                            f"Rating for {reader_name}",
                            min_value=0.0,
                            max_value=5.0,
                            value=default_rating,
                            step=0.1,
                            key=rating_widget_key,
                        )

                        save_rating = st.checkbox(
                            f"Save rating for {reader_name}",
                            value=default_save_rating,
                            key=save_rating_widget_key,
                        )
                    else:
                        new_rating = None
                        save_rating = False
                        st.caption("Rating is only available for Read and DNF.")

                    submitted = st.form_submit_button(
                        f"💾 Save {reader_name}'s Status",
                        width='stretch',
                    )

                if submitted:
                    try:
                        execute_procedure(
                            "SetReadingStatus",
                            [
                                int(book["BookID"]),
                                reader_name,
                                new_status,
                            ],
                        )

                        if new_status in RATING_ALLOWED_STATUSES and save_rating and new_rating is not None:
                            execute_procedure(
                                "SetReaderRating",
                                [
                                    int(book["BookID"]),
                                    reader_name,
                                    float(new_rating),
                                ],
                            )

                        clear_book_details_caches()

                        success_message = (
                            f"Updated **{book['Title']}** for **{reader_name}** "
                            f"to **{new_status}**"
                        )

                        if new_status in RATING_ALLOWED_STATUSES and save_rating and new_rating is not None:
                            success_message += f" with a rating of **{new_rating:.2f}**."

                        st.toast(success_message, icon="✅")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error: {e}")

with genres_tab:
    with st.container(border=True):
        st.markdown("### Edit Genres")
        st.caption("Update the genre lists for this book. Saving will replace the current genre assignments.")

        current_main_value = ", ".join(main_genres) if main_genres else ""
        current_secondary_value = ", ".join(secondary_genres) if secondary_genres else ""

        with st.form(f"genres_form_{book_id}"):
            main_genres_input = st.text_input(
                "Main Genres (comma-separated)",
                value=current_main_value,
            )

            secondary_genres_input = st.text_input(
                "Secondary Genres (comma-separated)",
                value=current_secondary_value,
            )

            save_genres = st.form_submit_button("💾 Save Genre Update", width='stretch')

        if save_genres:
            try:
                execute_procedure(
                    "UpdateBookGenres",
                    [
                        int(book["BookID"]),
                        main_genres_input.strip() if main_genres_input.strip() else None,
                        secondary_genres_input.strip() if secondary_genres_input.strip() else None,
                    ],
                )

                clear_book_details_caches()
                st.toast("Genres updated.", icon="✅")
                st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")


st.divider()

nav_col1, nav_col2 = st.columns([1, 1])

with nav_col1:
    if st.button("⬅ Back to Library", key="bottom_back", width='stretch'):
        st.switch_page("pages/1_Library.py")

with nav_col2:
    if st.button("🔄 Refresh page", width='stretch'):
        clear_book_details_caches()
        st.rerun()