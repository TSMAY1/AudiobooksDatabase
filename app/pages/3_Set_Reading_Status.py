import streamlit as st
import pandas as pd
from db import run_query, execute_procedure

st.title("📖 Update Reading Status")
st.markdown(
    "Select a book and reader, then update the reading status. "
    "Ratings can be added for books marked as **Read** or **DNF**."
)

STATUS_OPTIONS = ["Unread", "TBR", "Reading", "Read", "DNF"]
RATING_ALLOWED_STATUSES = {"Read", "DNF"}


def get_first_author(authors: str) -> str:
    """Return the first author for stored procedures that expect one author name."""
    return authors.split(",")[0].strip()


def get_current_reader_book_status(book_id: int, reader_name: str) -> tuple[str, float | None]:
    """
    Fetch the current reading status and rating for the selected book/reader pair.
    Falls back to Unread / None if no row is found yet.
    """
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


# Load books
books = run_query(
    """
    SELECT
        BookID,
        Title,
        Authors,
        SeriesName,
        BookNumber
    FROM vw_book_details
    ORDER BY Authors, Title;
    """
)

if books.empty:
    st.info("No books found in the library yet.")
    st.stop()

book_options = {
    f"{row['Title']} — {row['Authors']}": {
        "BookID": row["BookID"],
        "Title": row["Title"],
        "Authors": row["Authors"],
        "SeriesName": row["SeriesName"],
        "BookNumber": row["BookNumber"],
    }
    for _, row in books.iterrows()
}

selected_label = st.selectbox("📚 Select Book", list(book_options.keys()))
selected_book = book_options[selected_label]

selected_book_id = selected_book["BookID"]
selected_title = selected_book["Title"]
selected_authors = selected_book["Authors"]
selected_author_for_proc = get_first_author(selected_authors)

reader = st.selectbox("👤 Select Reader", ["Angela", "Tori"])

current_status, current_rating = get_current_reader_book_status(selected_book_id, reader)

st.divider()

st.subheader("Current Status")
info_col1, info_col2 = st.columns(2)
with info_col1:
    st.write(f"**Status:** {current_status}")
with info_col2:
    st.write(f"**Rating:** {current_rating if current_rating is not None else '—'}")

st.divider()

st.subheader("Edit Status")

status_index = STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0

with st.form("reading_status_form"):
    new_status = st.selectbox(
        "Reading Status",
        STATUS_OPTIONS,
        index=status_index,
        help="Unread = not started and not intentionally tracked, TBR = want to read later."
    )

    default_rating = float(current_rating) if current_rating is not None else 4.0

    if new_status in RATING_ALLOWED_STATUSES:
        new_rating = st.slider(
            "⭐ Rating",
            min_value=0.0,
            max_value=5.0,
            value=default_rating,
            step=0.1,
            help="Ratings are available for Read and DNF statuses."
        )
        save_rating = st.checkbox(
            "Save rating",
            value=(current_rating is not None),
            help="Uncheck this if you want to save the status without changing/adding a rating."
        )
    else:
        new_rating = None
        save_rating = False
        st.caption("Rating is only available for Read and DNF.")

    submitted = st.form_submit_button("💾 Save Reading Status", use_container_width=True)

if submitted:
    try:
        # Always save status first
        execute_procedure(
            "SetReadingStatus",
            [
                selected_title,
                selected_author_for_proc,
                reader,
                new_status,
            ],
        )

        # Then optionally save rating
        if new_status in RATING_ALLOWED_STATUSES and save_rating and new_rating is not None:
            execute_procedure(
                "SetReaderRating",
                [
                    selected_title,
                    selected_author_for_proc,
                    reader,
                    new_rating,
                ],
            )

        success_message = f"Updated **{selected_title}** for **{reader}** to **{new_status}**"
        if new_status in RATING_ALLOWED_STATUSES and save_rating and new_rating is not None:
            success_message += f" with a rating of **{new_rating:.2f}**."

        st.success(success_message)
        st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")