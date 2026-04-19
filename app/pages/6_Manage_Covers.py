import html
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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
    st.session_state["library_cache_buster"] = st.session_state.get("library_cache_buster", 0) + 1
    st.session_state["book_details_cache_buster"] = st.session_state.get("book_details_cache_buster", 0) + 1

def render_copyable_row(label: str, display_value: str, copy_value: str, height: int = 36):
    """
    Render a compact text row with a small icon-style copy button.
    """
    safe_label = html.escape(label)
    safe_display_value = html.escape(display_value)
    js_copy_value = json.dumps(copy_value)

    components.html(
        f"""
        <div style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:8px;
            font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            color:#e5e7eb;
            margin:0 0 4px 0;
            padding:0;
        ">
            <div style="
                overflow:hidden;
                text-overflow:ellipsis;
                white-space:nowrap;
                flex:1;
                font-size:0.98rem;
                line-height:1.3;
            ">
                <strong>{safe_label}</strong> {safe_display_value}
            </div>

            <button
                onclick='navigator.clipboard.writeText({js_copy_value})'
                title="Copy"
                onmouseover="this.style.backgroundColor='#1f2937'; this.style.borderColor='#60a5fa'; this.style.transform='scale(1.05)';"
                onmouseout="this.style.backgroundColor='#111827'; this.style.borderColor='#374151'; this.style.transform='scale(1)';"
                style="
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    width:30px;
                    height:30px;
                    border:1px solid #374151;
                    background:#111827;
                    color:#e5e7eb;
                    border-radius:8px;
                    cursor:pointer;
                    font-size:0.95rem;
                    line-height:1;
                    transition:all 0.15s ease;
                    flex-shrink:0;
                "
            >
                ⧉
            </button>
        </div>
        """,
        height=height,
        scrolling=False,
    )


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

# Read one-time cross-page navigation state
incoming_cover_book_id = st.session_state.pop("navigate_to_cover_book_id", None)

filtered_df = filtered_df.copy()
filtered_df["BookID"] = filtered_df["BookID"].astype(int)

# Figure out what book we want selected before creating the widget
existing_selected_book_id = st.session_state.get("manage_covers_selected_book_id")
preferred_book_id = incoming_cover_book_id or existing_selected_book_id

# If the page is showing a limited list for speed, keep the preferred book pinned
if not search and not only_missing and len(filtered_df) > 100:
    if preferred_book_id is not None and preferred_book_id in filtered_df["BookID"].tolist():
        pinned_row = filtered_df[filtered_df["BookID"] == preferred_book_id]
        remainder = filtered_df[filtered_df["BookID"] != preferred_book_id].head(99)
        filtered_df = pd.concat([pinned_row, remainder], ignore_index=True)
    else:
        filtered_df = filtered_df.head(100)

    st.caption("Showing a limited list for speed. Use search or the missing-cover filter to narrow the list.")

filtered_df = filtered_df.copy()
filtered_df["BookID"] = filtered_df["BookID"].astype(int)

filtered_df["DisplayLabel"] = filtered_df.apply(
    lambda row: (
        f"{row['Title']} — {row['Authors']}"
        + (f" | {row['SeriesName']}" if row["SeriesName"] else "")
        + f" | Covers: {int(row['CoverCount'])}"
    ),
    axis=1
)

book_ids = filtered_df["BookID"].tolist()
display_map = dict(zip(book_ids, filtered_df["DisplayLabel"]))

if not book_ids:
    st.warning("No books are available to select.")
    st.stop()

default_cover_book_id = preferred_book_id if preferred_book_id in book_ids else book_ids[0]

# Only initialize/reset BEFORE the widget is instantiated
if (
    "manage_covers_selected_book_id" not in st.session_state
    or st.session_state["manage_covers_selected_book_id"] not in book_ids
):
    st.session_state["manage_covers_selected_book_id"] = default_cover_book_id

selected_book_id = st.selectbox(
    "Choose a book",
    options=book_ids,
    format_func=lambda book_id: display_map[book_id],
    key="manage_covers_selected_book_id",
)

# Keep this in sync so other pages can still use it if needed
st.session_state["selected_cover_book_id"] = selected_book_id

selected_row = filtered_df.loc[filtered_df["BookID"] == selected_book_id].iloc[0]

nav_col1, nav_col2 = st.columns([1, 3])

with nav_col1:
    if st.button("📖 Go to Book Details", width="stretch"):
        st.session_state["selected_book_id"] = int(selected_book_id)
        st.switch_page("pages/2_Book_Details.py")

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

title = str(selected_row["Title"])
authors = str(selected_row["Authors"])
series = selected_row["SeriesName"] if selected_row["SeriesName"] else "Standalone"

render_copyable_row("Title:", title, title)
render_copyable_row("Author(s):", authors, authors)
render_copyable_row("Series:", series, series)

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
                st.image(image_bytes, width='stretch')
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
        type=["jpg", "jpeg", "png", "webp", "avif"],
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