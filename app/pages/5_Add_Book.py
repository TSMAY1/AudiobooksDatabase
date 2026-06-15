import streamlit as st
from ui import configure_page
from db import (
    bump_book_related_caches,
    execute_procedure,
    execute_procedure_returning_id,
    save_book_cover,
)

configure_page("Add Book", icon="➕")
st.title("➕ Add Book")
st.caption("Add a new book, with optional cover and audiobook details.")


# =========================================================
# Session state
# =========================================================
if "is_standalone" not in st.session_state:
    st.session_state.is_standalone = True

if "series_name_input" not in st.session_state:
    st.session_state.series_name_input = "Standalone"

if "add_audiobook_details" not in st.session_state:
    st.session_state.add_audiobook_details = False

if "last_added_book_id" not in st.session_state:
    st.session_state.last_added_book_id = None

if "last_added_book_title" not in st.session_state:
    st.session_state.last_added_book_title = None


# =========================================================
# Helpers
# =========================================================
def handle_standalone_toggle():
    if st.session_state.is_standalone:
        st.session_state.series_name_input = "Standalone"
    else:
        if st.session_state.series_name_input == "Standalone":
            st.session_state.series_name_input = ""


    bump_book_related_caches()


# =========================================================
# Top options
# =========================================================
option_col1, option_col2 = st.columns(2)

with option_col1:
    st.checkbox(
        "This is a standalone book",
        key="is_standalone",
        on_change=handle_standalone_toggle,
    )

with option_col2:
    st.checkbox(
        "Include audiobook details",
        key="add_audiobook_details",
    )

st.divider()


# =========================================================
# Add book form
# =========================================================
with st.form("add_book_form"):
    core_tab, genres_tab, cover_tab, audiobook_tab = st.tabs(
        ["📚 Core Details", "🏷️ Genres & Description", "🖼️ Cover", "🎧 Audiobook"]
    )

    with core_tab:
        st.markdown("### Core Book Details")

        title = st.text_input("Title")
        authors = st.text_input("Authors (comma-separated)")

        series_name = st.text_input(
            "Series Name",
            key="series_name_input",
            disabled=st.session_state.is_standalone,
        )

        if st.session_state.is_standalone:
            book_number = None
            st.caption("Standalone books use the series name 'Standalone' and no book number.")
        else:
            book_number = st.number_input(
                "Book Number",
                min_value=0.5,
                step=0.5,
                value=1.0,
            )

        meta_col1, meta_col2 = st.columns(2)

        with meta_col1:
            length_type = st.text_input("Length Type")

        with meta_col2:
            demographic = st.text_input("Demographic")

    with genres_tab:
        st.markdown("### Genres & Description")

        description = st.text_area("Description", height=140)
        main_genres = st.text_input("Main Genres (comma-separated)")
        secondary_genres = st.text_input("Secondary Genres (comma-separated)")

    with cover_tab:
        st.markdown("### Optional Covers")
        st.caption("Images will be converted to 400 x 600 WEBP files.")

        uploaded_covers = st.file_uploader(
            "Upload cover image(s)",
            type=["jpg", "jpeg", "png", "webp", "avif"],
            accept_multiple_files=True,
        )

        primary_cover_index = 0

        if uploaded_covers:
            uploaded_cover_names = [
                uploaded_file.name for uploaded_file in uploaded_covers
            ]

            primary_cover_name = st.selectbox(
                "Primary Cover",
                options=uploaded_cover_names,
                help="Choose which uploaded cover should be marked as primary.",
            )

            primary_cover_index = uploaded_cover_names.index(primary_cover_name)

        cover_col1, cover_col2 = st.columns(2)

        with cover_col1:
            cover_label = st.text_input(
                "Cover Label",
                value="",
                placeholder="Optional label applied to all uploaded covers",
            )

        with cover_col2:
            cover_source_notes = st.text_input(
                "Cover Source Notes",
                placeholder="Optional notes applied to all uploaded covers",
            )

    with audiobook_tab:
        st.markdown("### Optional Audiobook Details")

        if not st.session_state.add_audiobook_details:
            st.info("Turn on “Include audiobook details” at the top of the page to add audiobook information now.")

            audiobook_edition_name = ""
            audiobook_narrators = ""
            audiobook_publisher = ""
            audiobook_release_year = 0
            audiobook_duration_hours = 0
            audiobook_duration_minutes = 0
            audiobook_is_full_cast = False
            audiobook_is_abridged = False
            audiobook_notes = ""

        else:
            audiobook_edition_name = st.text_input(
                "Edition Name",
                placeholder="e.g. Standard Audiobook, Full Cast Edition, Anniversary Edition",
            )

            audiobook_narrators = st.text_input(
                "Narrator(s) (comma-separated)",
                placeholder="e.g. Andy Serkis, Ensemble Cast",
            )

            audio_col1, audio_col2 = st.columns(2)

            with audio_col1:
                audiobook_publisher = st.text_input(
                    "Audiobook Publisher",
                    placeholder="Optional",
                )

                audiobook_duration_hours = st.number_input(
                    "Hours",
                    min_value=0,
                    max_value=200,
                    value=0,
                    step=1,
                )

            with audio_col2:
                audiobook_release_year = st.number_input(
                    "Audiobook Release Year",
                    min_value=0,
                    max_value=3000,
                    value=0,
                    step=1,
                )

                audiobook_duration_minutes = st.number_input(
                    "Minutes",
                    min_value=0,
                    max_value=59,
                    value=0,
                    step=1,
                )

            flag_col1, flag_col2 = st.columns(2)

            with flag_col1:
                audiobook_is_full_cast = st.checkbox("Full Cast Audiobook")

            with flag_col2:
                audiobook_is_abridged = st.checkbox("Abridged")

            audiobook_notes = st.text_area(
                "Audiobook Notes",
                placeholder="Optional notes about this audiobook version",
                height=100,
            )

    submitted = st.form_submit_button("➕ Add Book", width="stretch")


# =========================================================
# Submit handling
# =========================================================
if submitted:
    if not title.strip():
        st.error("Please enter a title.")
        st.stop()

    if not authors.strip():
        st.error("Please enter at least one author.")
        st.stop()

    try:
        final_title = title.strip()
        final_authors = authors.strip()

        final_series_name = (
            "Standalone"
            if st.session_state.is_standalone
            else st.session_state.series_name_input.strip()
        )

        new_book_id = execute_procedure_returning_id(
            "AddBook",
            [
                final_title,
                final_authors,
                final_series_name,
                book_number,
                length_type.strip() if length_type.strip() else None,
                demographic.strip() if demographic.strip() else None,
                description.strip() if description.strip() else None,
                main_genres.strip() if main_genres.strip() else None,
                secondary_genres.strip() if secondary_genres.strip() else None,
            ],
        )

        if new_book_id is None:
            st.warning(
                "Book was added, but the new BookID could not be found. "
                "Cover and audiobook details were not added."
            )
            st.stop()

        if uploaded_covers:
            for index, uploaded_cover in enumerate(uploaded_covers):
                is_primary = index == primary_cover_index

                save_book_cover(
                    book_id=int(new_book_id),
                    uploaded_file=uploaded_cover,
                    cover_label=cover_label.strip() if cover_label.strip() else None,
                    source_notes=cover_source_notes.strip() if cover_source_notes.strip() else None,
                    make_primary=is_primary,
                    target_size=(400, 600),
                )

        if st.session_state.add_audiobook_details:
            total_duration_minutes = None
            if audiobook_duration_hours > 0 or audiobook_duration_minutes > 0:
                total_duration_minutes = int(
                    audiobook_duration_hours * 60 + audiobook_duration_minutes
                )

            execute_procedure(
                "AddAudiobookVersion",
                [
                    int(new_book_id),
                    audiobook_edition_name.strip() if audiobook_edition_name.strip() else None,
                    audiobook_publisher.strip() if audiobook_publisher.strip() else None,
                    int(audiobook_release_year) if audiobook_release_year > 0 else None,
                    total_duration_minutes,
                    1 if audiobook_is_abridged else 0,
                    1 if audiobook_is_full_cast else 0,
                    audiobook_notes.strip() if audiobook_notes.strip() else None,
                    audiobook_narrators.strip() if audiobook_narrators.strip() else None,
                ],
            )

        bump_book_related_caches()

        st.session_state["last_added_book_id"] = int(new_book_id)
        st.session_state["last_added_book_title"] = final_title

        st.success(f"Book added successfully: **{final_title}**")

    except Exception as e:
        st.error(f"Error: {e}")


# =========================================================
# Post-add actions
# =========================================================
if st.session_state.get("last_added_book_id"):
    st.divider()

    st.markdown(f"### Last Added: {st.session_state['last_added_book_title']}")

    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        if st.button("📖 View Details", width="stretch"):
            st.session_state["selected_book_id"] = int(st.session_state["last_added_book_id"])
            st.switch_page("pages/3_Book_Details.py")

    with action_col2:
        if st.button("🖼️ Manage Covers", width="stretch"):
            st.session_state["navigate_to_cover_book_id"] = int(st.session_state["last_added_book_id"])
            st.switch_page("pages/8_Manage_Covers.py")

    with action_col3:
        if st.button("🎧 Manage Audiobooks", width="stretch"):
            st.session_state["navigate_to_audiobook_book_id"] = int(st.session_state["last_added_book_id"])
            st.switch_page("pages/7_Manage_Audiobooks.py")