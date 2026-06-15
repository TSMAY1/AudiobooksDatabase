import pandas as pd
import streamlit as st
from ui import configure_page
from db import bump_book_related_caches, run_query, execute_procedure

configure_page("Manage Audiobooks", icon="🎧")
st.title("🎧 Manage Audiobooks")
st.markdown("Add and review audiobook versions for each book.")


# =========================================================
# Cached loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_books_for_audiobook_manager():
    query = """
    SELECT
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        COUNT(av.AudiobookVersionID) AS AudiobookCount,
        MAX(CASE WHEN av.IsFullCast = 1 THEN 1 ELSE 0 END) AS HasFullCastVersion
    FROM vw_book_details vd
    LEFT JOIN audiobook_versions av
        ON av.BookID = vd.BookID
    GROUP BY
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName
    ORDER BY
        vd.Title,
        vd.Authors;
    """
    return run_query(query)


@st.cache_data(show_spinner=False)
def load_book_audiobooks(book_id: int, cache_buster: int = 0):
    return run_query("""
        SELECT
            AudiobookVersionID,
            EditionName,
            Publisher,
            ReleaseYear,
            DurationMinutes,
            DurationDisplay,
            IsAbridged,
            IsFullCast,
            Notes,
            Narrators
        FROM vw_book_audiobooks
        WHERE BookID = ?
        ORDER BY
            CASE WHEN IsFullCast = 1 THEN 1 ELSE 0 END,
            ReleaseYear,
            EditionName;
    """, params=[book_id])


def clear_audiobook_caches():
    load_books_for_audiobook_manager.clear()
    load_book_audiobooks.clear()

    bump_book_related_caches()


# =========================================================
# Load books
# =========================================================
books_df = load_books_for_audiobook_manager()

if books_df.empty:
    st.info("No books found in the library.")
    st.stop()

search = st.text_input("Search by title, author, or series")
only_missing = st.checkbox("Show only books with no audiobook versions")

filtered_df = books_df.copy()

if search:
    mask = (
        filtered_df["Title"].str.contains(search, case=False, na=False)
        | filtered_df["Authors"].str.contains(search, case=False, na=False)
        | filtered_df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

if only_missing:
    filtered_df = filtered_df[filtered_df["AudiobookCount"] == 0]

if filtered_df.empty:
    st.warning("No books matched your filters.")
    st.stop()

incoming_book_id = st.session_state.pop("navigate_to_audiobook_book_id", None)

filtered_df = filtered_df.copy()
filtered_df["BookID"] = filtered_df["BookID"].astype(int)

existing_selected_book_id = st.session_state.get("manage_audiobooks_selected_book_id")
preferred_book_id = incoming_book_id or existing_selected_book_id

if not search and not only_missing and len(filtered_df) > 100:
    if preferred_book_id is not None and preferred_book_id in filtered_df["BookID"].tolist():
        pinned_row = filtered_df[filtered_df["BookID"] == preferred_book_id]
        remainder = filtered_df[filtered_df["BookID"] != preferred_book_id].head(99)
        filtered_df = pd.concat([pinned_row, remainder], ignore_index=True)
    else:
        filtered_df = filtered_df.head(100)

    st.caption("Showing a limited list for speed. Use search or the missing-audiobooks filter to narrow the list.")

filtered_df["DisplayLabel"] = filtered_df.apply(
    lambda row: (
        f"{row['Title']} — {row['Authors']}"
        + (f" | {row['SeriesName']}" if row["SeriesName"] else "")
        + f" | Audiobooks: {int(row['AudiobookCount'])}"
    ),
    axis=1
)

book_ids = filtered_df["BookID"].tolist()
display_map = dict(zip(book_ids, filtered_df["DisplayLabel"]))

if not book_ids:
    st.warning("No books are available to select.")
    st.stop()

default_book_id = preferred_book_id if preferred_book_id in book_ids else book_ids[0]

if (
    "manage_audiobooks_selected_book_id" not in st.session_state
    or st.session_state["manage_audiobooks_selected_book_id"] not in book_ids
):
    st.session_state["manage_audiobooks_selected_book_id"] = default_book_id

selected_book_id = st.selectbox(
    "Choose a book",
    options=book_ids,
    format_func=lambda book_id: display_map[book_id],
    key="manage_audiobooks_selected_book_id",
)

selected_row = filtered_df.loc[filtered_df["BookID"] == selected_book_id].iloc[0]

cache_buster = st.session_state.get("manage_audiobooks_cache_buster", 0)
audiobooks_df = load_book_audiobooks(int(selected_book_id), cache_buster=cache_buster)


# =========================================================
# Navigation + summary
# =========================================================
nav_col1, nav_col2 = st.columns([1, 3])

with nav_col1:
    if st.button("📖 Go to Book Details", width="stretch"):
        st.session_state["selected_book_id"] = int(selected_book_id)
        st.switch_page("pages/3_Book_Details.py")

st.divider()

info_col1, info_col2, info_col3 = st.columns(3)
with info_col1:
    st.metric("Book ID", int(selected_row["BookID"]))
with info_col2:
    st.metric("Audiobook Versions", int(selected_row["AudiobookCount"]))
with info_col3:
    st.metric(
        "Has Full Cast",
        "Yes" if int(selected_row["HasFullCastVersion"] or 0) == 1 else "No"
    )

title = str(selected_row["Title"])
authors = str(selected_row["Authors"])
series = selected_row["SeriesName"] if selected_row["SeriesName"] else "Standalone"

st.markdown(f"**Title:** {title}")
st.markdown(f"**Author(s):** {authors}")
st.markdown(f"**Series:** {series}")

st.divider()


# =========================================================
# Current audiobooks
# =========================================================
st.subheader("Current Audiobook Versions")

if audiobooks_df.empty:
    st.info("This book does not have any audiobook versions yet.")
else:
    for _, row in audiobooks_df.iterrows():
        audiobook_version_id = int(row["AudiobookVersionID"])

        edition_name = (
            row["EditionName"]
            if pd.notna(row.get("EditionName")) and str(row["EditionName"]).strip()
            else "Standard Audiobook"
        )

        narrators = (
            row["Narrators"]
            if pd.notna(row.get("Narrators")) and str(row["Narrators"]).strip()
            else "No narrators recorded"
        )

        duration = (
            row["DurationDisplay"]
            if pd.notna(row.get("DurationDisplay")) and str(row["DurationDisplay"]).strip()
            else "Unknown length"
        )

        publisher = (
            row["Publisher"]
            if pd.notna(row.get("Publisher")) and str(row["Publisher"]).strip()
            else None
        )

        release_year = (
            str(int(row["ReleaseYear"]))
            if pd.notna(row.get("ReleaseYear"))
            else None
        )

        notes = (
            row["Notes"]
            if pd.notna(row.get("Notes")) and str(row["Notes"]).strip()
            else None
        )

        tags = []
        if row.get("IsFullCast") in [True, 1]:
            tags.append("Full Cast")
        if row.get("IsAbridged") in [True, 1]:
            tags.append("Abridged")

        with st.container(border=True):
            top_col1, top_col2 = st.columns([5, 1])

            confirm_key = f"confirm_delete_audiobook_{audiobook_version_id}"

            with top_col1:
                st.markdown(f"### {edition_name}")

            with top_col2:
                if st.session_state.get(confirm_key, False):
                    st.warning("Click confirm to delete this audiobook version.")

                    confirm_col1, confirm_col2 = st.columns(2)

                    with confirm_col1:
                        if st.button(
                            "Confirm",
                            key=f"confirm_btn_{audiobook_version_id}",
                            width="stretch",
                        ):
                            try:
                                execute_procedure(
                                    "DeleteAudiobookVersion",
                                    [audiobook_version_id],
                                )
                                st.session_state.pop(confirm_key, None)
                                clear_audiobook_caches()
                                st.success(f"Deleted audiobook version: **{edition_name}**")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting audiobook version: {e}")

                    with confirm_col2:
                        if st.button(
                            "Cancel",
                            key=f"cancel_btn_{audiobook_version_id}",
                            width="stretch",
                        ):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button(
                        "Delete",
                        key=f"delete_audiobook_{audiobook_version_id}",
                        width="stretch",
                    ):
                        st.session_state[confirm_key] = True
                        st.rerun()

            st.markdown(f"**Narrator(s):** {narrators}")
            st.markdown(f"**Length:** {duration}")

            meta_parts = []
            if publisher:
                meta_parts.append(f"Publisher: {publisher}")
            if release_year:
                meta_parts.append(f"Release Year: {release_year}")
            if meta_parts:
                st.caption(" | ".join(meta_parts))

            if tags:
                st.caption(" • ".join(tags))

            if notes:
                st.markdown(f"**Notes:** {notes}")

st.divider()


# =========================================================
# Add audiobook version
# =========================================================
st.subheader("Add New Audiobook Version")
st.caption("Add one audiobook edition/version for the selected book.")

with st.form("add_audiobook_form"):
    edition_name = st.text_input(
        "Edition Name",
        placeholder="e.g. Standard Audiobook, Full Cast Edition, Anniversary Edition"
    )

    narrators = st.text_input(
        "Narrator(s) (comma-separated)",
        placeholder="e.g. Andy Serkis, Ensemble Cast"
    )

    col1, col2 = st.columns(2)

    with col1:
        publisher = st.text_input("Publisher", placeholder="Optional")
        duration_hours = st.number_input(
            "Hours",
            min_value=0,
            max_value=200,
            value=0,
            step=1
        )

    with col2:
        release_year = st.number_input(
            "Release Year",
            min_value=0,
            max_value=3000,
            value=0,
            step=1
        )
        duration_minutes_part = st.number_input(
            "Minutes",
            min_value=0,
            max_value=59,
            value=0,
            step=1
        )

    col3, col4 = st.columns(2)

    with col3:
        is_full_cast = st.checkbox("Full Cast")
    with col4:
        is_abridged = st.checkbox("Abridged")

    notes = st.text_area(
        "Notes",
        placeholder="Optional notes about this audiobook version",
        height=120
    )

    submitted = st.form_submit_button("➕ Add Audiobook Version", width="stretch")

if submitted:
    try:
        total_duration_minutes = None
        if duration_hours > 0 or duration_minutes_part > 0:
            total_duration_minutes = int(duration_hours * 60 + duration_minutes_part)

        final_release_year = int(release_year) if release_year > 0 else None
        final_edition_name = edition_name.strip() if edition_name.strip() else None
        final_publisher = publisher.strip() if publisher.strip() else None
        final_narrators = narrators.strip() if narrators.strip() else None
        final_notes = notes.strip() if notes.strip() else None

        execute_procedure(
            "AddAudiobookVersion",
            [
                int(selected_book_id),
                final_edition_name,
                final_publisher,
                final_release_year,
                total_duration_minutes,
                1 if is_abridged else 0,
                1 if is_full_cast else 0,
                final_notes,
                final_narrators,
            ],
        )

        clear_audiobook_caches()
        st.success(f"Added a new audiobook version for **{title}**.")
        st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")


st.divider()

bottom_col1, bottom_col2 = st.columns([1, 1])

with bottom_col1:
    if st.button("⬅ Back to Library", key="audiobooks_back", width="stretch"):
        st.switch_page("pages/2_Library.py")

with bottom_col2:
    if st.button("🔄 Refresh page", width="stretch"):
        clear_audiobook_caches()
        st.rerun()