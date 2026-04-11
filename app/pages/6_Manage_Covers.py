import streamlit as st
from db import (
    run_query,
    get_book_covers,
    save_book_cover,
    set_primary_cover,
    delete_cover,
    load_cover_image_bytes,
)

st.title("🖼️ Manage Covers")
st.markdown("Upload, preview, and manage book cover images for each book.")


@st.cache_data(show_spinner=False)
def load_books_for_cover_manager():
    query = """
    SELECT
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        COUNT(bc.CoverID) AS CoverCount,
        MAX(CASE WHEN bc.IsPrimary = 1 THEN 1 ELSE 0 END) AS HasPrimaryCover
    FROM vw_book_details vd
    LEFT JOIN book_covers bc
        ON bc.BookID = vd.BookID
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


def clear_cover_caches():
    load_books_for_cover_manager.clear()
    get_book_covers.clear()
    load_cover_image_bytes.clear()


books_df = load_books_for_cover_manager()

if books_df.empty:
    st.info("No books found in the library.")
    st.stop()

search = st.text_input("Search by title, author, or series")
only_missing = st.checkbox("Show only books with no covers")

filtered_df = books_df.copy()

if search:
    mask = (
        filtered_df["Title"].str.contains(search, case=False, na=False)
        | filtered_df["Authors"].str.contains(search, case=False, na=False)
        | filtered_df["SeriesName"].fillna("").str.contains(search, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

if only_missing:
    filtered_df = filtered_df[filtered_df["CoverCount"] == 0]

if filtered_df.empty:
    st.warning("No books matched your filters.")
    st.stop()

# Keep the selectbox smaller and faster when not actively filtering
if not search and not only_missing and len(filtered_df) > 100:
    filtered_df = filtered_df.head(100)
    st.caption("Showing the first 100 books for speed. Use search or the missing-cover filter to narrow the list.")

filtered_df = filtered_df.copy()

filtered_df["DisplayLabel"] = filtered_df.apply(
    lambda row: (
        f"{row['Title']} — {row['Authors']}"
        + (f" | {row['SeriesName']}" if row["SeriesName"] else "")
        + f" | Covers: {int(row['CoverCount'])}"
    ),
    axis=1
)

book_ids = filtered_df["BookID"].astype(int).tolist()
display_map = dict(zip(book_ids, filtered_df["DisplayLabel"]))

if "selected_cover_book_id" not in st.session_state:
    st.session_state.selected_cover_book_id = book_ids[0]

if st.session_state.selected_cover_book_id not in book_ids:
    st.session_state.selected_cover_book_id = book_ids[0]

selected_book_id = st.selectbox(
    "Choose a book",
    options=book_ids,
    format_func=lambda book_id: display_map[book_id],
    index=book_ids.index(st.session_state.selected_cover_book_id),
)

st.session_state.selected_cover_book_id = selected_book_id

selected_row = filtered_df.loc[filtered_df["BookID"] == selected_book_id].iloc[0]

st.divider()

info_col1, info_col2, info_col3 = st.columns(3)
with info_col1:
    st.metric("Book ID", int(selected_row["BookID"]))
with info_col2:
    st.metric("Cover Count", int(selected_row["CoverCount"]))
with info_col3:
    st.metric(
        "Has Primary Cover",
        "Yes" if int(selected_row["HasPrimaryCover"] or 0) == 1 else "No"
    )

st.markdown(f"**Title:** {selected_row['Title']}")
st.markdown(f"**Author(s):** {selected_row['Authors']}")
st.markdown(
    f"**Series:** {selected_row['SeriesName'] if selected_row['SeriesName'] else 'Standalone'}"
)

st.divider()

st.subheader("Current Covers")

covers_df = get_book_covers(int(selected_book_id))

if covers_df.empty:
    st.info("This book does not have any covers yet.")
else:
    columns = st.columns(3)

    for idx, (_, row) in enumerate(covers_df.iterrows()):
        with columns[idx % 3]:
            try:
                image_bytes = load_cover_image_bytes(row["ImageFilePath"])
                st.image(image_bytes, use_container_width=True)
            except Exception:
                st.warning("Image file could not be loaded.")

            label = row["CoverLabel"] if row["CoverLabel"] else "Unlabeled"
            st.markdown(f"**{label}**")

            if row["IsPrimary"]:
                st.success("Primary cover")
            else:
                if st.button("Set as primary", key=f"primary_{row['CoverID']}"):
                    try:
                        set_primary_cover(int(row["CoverID"]))
                        clear_cover_caches()
                        st.success("Primary cover updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            st.caption(
                f"{row['WidthPx']} x {row['HeightPx']} px | "
                f"{str(row['ImageFormat']).upper()} | "
                f"{row['FileSizeKB']} KB"
            )

            if row["SourceNotes"]:
                st.caption(f"Notes: {row['SourceNotes']}")

            if st.button("Delete cover", key=f"delete_{row['CoverID']}"):
                try:
                    delete_cover(int(row["CoverID"]))
                    clear_cover_caches()
                    st.success("Cover deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

st.divider()

st.subheader("Upload New Cover(s)")
st.caption("Images will be converted to 400 x 600 WEBP files with padded white background.")

with st.form("upload_cover_form"):
    uploaded_files = st.file_uploader(
        "Choose image file(s)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )

    cover_label = st.text_input("Cover Label (optional)")
    source_notes = st.text_input("Source Notes (optional)")
    make_primary = st.checkbox("Make the first uploaded cover the primary cover")

    submitted = st.form_submit_button("Upload and Process Cover(s)")

if submitted:
    if not uploaded_files:
        st.error("Please select at least one image.")
    else:
        try:
            for index, uploaded_file in enumerate(uploaded_files):
                this_should_be_primary = make_primary and index == 0

                save_book_cover(
                    book_id=int(selected_book_id),
                    uploaded_file=uploaded_file,
                    cover_label=cover_label.strip() if cover_label.strip() else None,
                    source_notes=source_notes.strip() if source_notes.strip() else None,
                    make_primary=this_should_be_primary,
                    target_size=(400, 600)
                )

            clear_cover_caches()
            st.success(f"Uploaded and processed {len(uploaded_files)} cover(s).")
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")