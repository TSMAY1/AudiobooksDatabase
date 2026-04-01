import streamlit as st
from db import run_query, execute_procedure

st.title("📚 TBR List")
st.markdown(
    "View a reader’s current **To Be Read** list and add new books to it."
)

readers_df = run_query("SELECT ReaderName FROM readers ORDER BY ReaderName;")
READERS = readers_df["ReaderName"].tolist()


def load_tbr_books(reader_name: str):
    """Load the current TBR list for the selected reader, including genres."""
    return run_query(
        """
        SELECT
            bd.BookID,
            bd.Authors,
            rb.Title,
            bd.SeriesName,
            bd.BookNumber,
            rb.ReaderName,
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
          AND rb.ReadingStatus = 'TBR'
        GROUP BY
            bd.BookID,
            bd.Authors,
            rb.Title,
            bd.SeriesName,
            bd.BookNumber,
            rb.ReaderName
        ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber, rb.Title;
        """,
        params=[reader_name],
    )


def load_books_not_in_tbr(reader_name: str):
    """
    Load books that are not currently on the selected reader's TBR list.
    This still allows books with other statuses (Unread, Reading, DNF, Read)
    to be selected and moved into TBR if desired.
    """
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
        ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber, bd.Title;
        """,
        params=[reader_name],
    )


selected_reader = st.selectbox("👤 Select Reader", READERS)

st.divider()

# -----------------------------
# Current TBR list
# -----------------------------
st.subheader(f"Current TBR for {selected_reader}")

tbr_df = load_tbr_books(selected_reader)

search = st.text_input("Search this TBR list by title, author, or series")

display_df = tbr_df.copy()

if search and not display_df.empty:
    mask = (
        display_df["Title"].str.contains(search, case=False, na=False)
        | display_df["Authors"].str.contains(search, case=False, na=False)
        | display_df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
    )
    display_df = display_df[mask]

if display_df.empty:
    st.info("No books are currently on this TBR list.")
else:
    st.dataframe(
        display_df[
            [
                "Authors",
                "Title",
                "SeriesName",
                "BookNumber",
                "MainGenres",
                "SecondaryGenres",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

st.divider()

# -----------------------------
# Add a book to TBR
# -----------------------------
st.subheader("➕ Add a Book to TBR")

available_books_df = load_books_not_in_tbr(selected_reader)

if available_books_df.empty:
    st.info("All books are already on this reader’s TBR list.")
else:
    book_options = {
        f"{row['Title']} — {row['Authors']}": {
            "BookID": row["BookID"],
            "Title": row["Title"],
            "Authors": row["Authors"],
            "SeriesName": row["SeriesName"],
            "BookNumber": row["BookNumber"],
        }
        for _, row in available_books_df.iterrows()
    }

    with st.form("add_to_tbr_form"):
        selected_label = st.selectbox("📖 Choose a Book", list(book_options.keys()))
        selected_book = book_options[selected_label]

        submitted = st.form_submit_button("Add to TBR")

    if submitted:
        try:
            execute_procedure(
                "SetReadingStatus",
                [
                    selected_book["BookID"],
                    selected_reader,
                    "TBR",
                ],
            )

            st.success(
                f"Added **{selected_book['Title']}** to **{selected_reader}’s** TBR list."
            )
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

st.divider()

# -----------------------------
# Optional removal section
# -----------------------------
st.subheader("➖ Remove a Book from TBR")

if tbr_df.empty:
    st.caption("There are no TBR books to remove.")
else:
    remove_options = {
        f"{row['Title']} — {row['Authors']}": {
            "BookID": row["BookID"],
            "Title": row["Title"],
            "Authors": row["Authors"],
        }
        for _, row in tbr_df.iterrows()
    }

    with st.form("remove_from_tbr_form"):
        remove_label = st.selectbox("Select a Book to Remove", list(remove_options.keys()))
        remove_book = remove_options[remove_label]

        removed = st.form_submit_button("Remove from TBR")

    if removed:
        try:
            execute_procedure(
                "SetReadingStatus",
                [
                    remove_book["BookID"],
                    selected_reader,
                    "Unread",
                ],
            )

            st.success(
                f"Removed **{remove_book['Title']}** from **{selected_reader}’s** TBR list."
            )
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")