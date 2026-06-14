import streamlit as st
import pandas as pd
from db import run_query, execute_non_query, format_book_number

st.set_page_config(page_title="Upcoming Releases", page_icon="📅", layout="wide")

st.title("📅 Upcoming Releases")
st.caption("Track anticipated audiobook releases and mark them as released when they become available.")


# =========================================================
# Helpers
# =========================================================
def bump_cache():
    st.session_state["upcoming_releases_cache_buster"] = (
        st.session_state.get("upcoming_releases_cache_buster", 0) + 1
    )


def clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def format_release_date(row):
    precision = row.get("ReleaseDatePrecision") or "Unknown"
    release_date = row.get("ExpectedReleaseDate")

    if pd.isna(release_date):
        return "Unknown"

    release_date = pd.to_datetime(release_date)

    if precision == "Year":
        return release_date.strftime("%Y")
    if precision == "Month":
        return release_date.strftime("%B %Y")
    if precision == "Exact":
        return release_date.strftime("%B %d, %Y")

    return "Unknown"


def format_series_line(row):
    series_name = row.get("SeriesName")
    parent_series_name = row.get("ParentSeriesName")
    book_number = row.get("BookNumber")

    if pd.isna(series_name) or not series_name:
        return "Standalone / No series"

    number_text = format_book_number(book_number)
    series_text = f"{series_name} #{number_text}" if number_text else str(series_name)

    if pd.notna(parent_series_name) and parent_series_name:
        return f"{parent_series_name} · {series_text}"

    return series_text


def update_last_checked(release_id):
    execute_non_query(
        """
        UPDATE upcoming_releases
        SET LastChecked = SYSDATETIME()
        WHERE ReleaseID = ?;
        """,
        [int(release_id)],
    )
    bump_cache()
    st.toast("Last checked updated.")
    st.rerun()


def mark_released(release_id):
    execute_non_query(
        """
        UPDATE upcoming_releases
        SET WatchStatus = 'Released',
            LastChecked = SYSDATETIME()
        WHERE ReleaseID = ?;
        """,
        [int(release_id)],
    )
    bump_cache()
    st.toast("Marked as released.")
    st.rerun()


def move_back_to_watching(release_id):
    execute_non_query(
        """
        UPDATE upcoming_releases
        SET WatchStatus = 'Watching'
        WHERE ReleaseID = ?;
        """,
        [int(release_id)],
    )
    bump_cache()
    st.toast("Moved back to Watching.")
    st.rerun()


def update_release(
    release_id,
    title,
    authors,
    series_id,
    book_number,
    expected_release_date,
    release_date_precision,
    publisher,
    narrators,
):
    execute_non_query(
        """
        UPDATE upcoming_releases
        SET
            Title = ?,
            Authors = ?,
            SeriesID = ?,
            BookNumber = ?,
            ExpectedReleaseDate = ?,
            ReleaseDatePrecision = ?,
            Publisher = ?,
            Narrators = ?
        WHERE ReleaseID = ?;
        """,
        [
            title,
            authors,
            series_id,
            book_number,
            expected_release_date,
            release_date_precision,
            publisher,
            narrators,
            release_id,
        ],
    )
    st.cache_data.clear()
    st.rerun()


def delete_release(release_id):
    execute_non_query(
        """
        DELETE FROM upcoming_releases
        WHERE ReleaseID = ?;
        """,
        [release_id],
    )
    st.cache_data.clear()
    st.rerun()


def set_editing_release(release_id):
    st.session_state["editing_release_id"] = int(release_id)


# =========================================================
# Cached loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_series(cache_buster=0):
    return run_query(
        """
        SELECT SeriesID, SeriesName, ParentSeriesID
        FROM series
        WHERE SeriesName <> 'Standalone'
        ORDER BY SeriesName;
        """
    )


@st.cache_data(show_spinner=False)
def load_upcoming_releases(cache_buster=0):
    return run_query(
        """
        SELECT
            ReleaseID,
            Title,
            Authors,
            SeriesID,
            SeriesName,
            ParentSeriesName,
            UniverseName,
            BookNumber,
            ExpectedReleaseDate,
            ReleaseDatePrecision,
            Publisher,
            Narrators,
            WatchStatus,
            DateAdded,
            LastChecked
        FROM vw_upcoming_releases
        ORDER BY
            CASE WHEN WatchStatus = 'Watching' THEN 0 ELSE 1 END,
            CASE WHEN ExpectedReleaseDate IS NULL THEN 1 ELSE 0 END,
            ExpectedReleaseDate ASC,
            Title ASC;
        """
    )


def render_release_card(row, section_key, show_released_actions=False):
    with st.container(border=True):
        top_col, action_col = st.columns([4, 1.4])

        with top_col:
            st.markdown(f"### {row['Title']}")

            if pd.notna(row.get("Authors")) and row.get("Authors"):
                st.caption(f"✍️ {row['Authors']}")

            st.caption(f"📚 {format_series_line(row)}")
            st.caption(f"📅 Expected: {format_release_date(row)}")

            detail_bits = []

            if pd.notna(row.get("Narrators")) and row.get("Narrators"):
                detail_bits.append(f"🎙️ {row['Narrators']}")

            if pd.notna(row.get("Publisher")) and row.get("Publisher"):
                detail_bits.append(f"🏢 {row['Publisher']}")

            if detail_bits:
                st.caption(" · ".join(detail_bits))

            if pd.notna(row.get("LastChecked")):
                checked_date = pd.to_datetime(row["LastChecked"]).strftime("%b %d, %Y")
                st.caption(f"Last checked: {checked_date}")
            else:
                st.caption("Last checked: Not yet checked")

        with action_col:
            st.write("")
            st.write("")

            if row["WatchStatus"] == "Watching":
                if st.button("✅ Mark Released", key=f"{section_key}_release_{row['ReleaseID']}", width="stretch"):
                    mark_released(row["ReleaseID"])

                if st.button("🔎 Checked Today", key=f"{section_key}_checked_{row['ReleaseID']}", width="stretch"):
                    update_last_checked(row["ReleaseID"])
                
                if st.button("✏️ Edit", key=f"{section_key}_edit_{row['ReleaseID']}", width="stretch"):
                    set_editing_release(row["ReleaseID"])

                if st.button("🗑️ Delete", key=f"{section_key}_delete_{row['ReleaseID']}", width="stretch"):
                    st.session_state["delete_release_id"] = int(row["ReleaseID"])
        
            elif show_released_actions:
                if st.button("↩️ Back to Watching", key=f"{section_key}_watching_{row['ReleaseID']}", width="stretch"):
                    move_back_to_watching(row["ReleaseID"])


# =========================================================
# Load data
# =========================================================
cache_buster = st.session_state.get("upcoming_releases_cache_buster", 0)
series_df = load_series(cache_buster)
releases_df = load_upcoming_releases(cache_buster)


# =========================================================
# Add release form
# =========================================================
with st.expander("➕ Add Upcoming Release", expanded=False):
    with st.form("add_upcoming_release_form", clear_on_submit=True):
        title = st.text_input("Title")
        authors = st.text_input("Authors", placeholder="Comma-separated, if needed")

        series_options = ["No series / Standalone"]
        series_id_lookup = {"No series / Standalone": None}

        if not series_df.empty:
            for _, series_row in series_df.iterrows():
                label = series_row["SeriesName"]
                series_options.append(label)
                series_id_lookup[label] = int(series_row["SeriesID"])

        selected_series = st.selectbox("Series", options=series_options)

        book_number = None
        if selected_series != "No series / Standalone":
            book_number = st.number_input(
                "Book Number",
                min_value=0.0,
                step=0.5,
                value=1.0,
            )

        date_col1, date_col2 = st.columns(2)

        with date_col1:
            release_precision = st.selectbox(
                "Release Date Precision",
                options=["Exact", "Month", "Year", "Unknown"],
            )

        with date_col2:
            release_date = None
            if release_precision != "Unknown":
                release_date = st.date_input("Expected Release Date")
            else:
                st.text_input("Expected Release Date", value="Unknown", disabled=True)

        meta_col1, meta_col2 = st.columns(2)

        with meta_col1:
            publisher = st.text_input("Publisher")

        with meta_col2:
            narrators = st.text_input("Narrator(s)", placeholder="Comma-separated, if needed")

        submitted = st.form_submit_button("➕ Add Release", width="stretch")

    if submitted:
        if not title.strip():
            st.error("Please enter a title.")
            st.stop()

        try:
            execute_non_query(
                """
                INSERT INTO upcoming_releases (
                    Title,
                    Authors,
                    SeriesID,
                    BookNumber,
                    ExpectedReleaseDate,
                    ReleaseDatePrecision,
                    Publisher,
                    Narrators,
                    WatchStatus
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Watching');
                """,
                [
                    title.strip(),
                    clean_text(authors),
                    series_id_lookup[selected_series],
                    float(book_number) if book_number is not None else None,
                    release_date if release_precision != "Unknown" else None,
                    release_precision,
                    clean_text(publisher),
                    clean_text(narrators),
                ],
            )
            bump_cache()
            st.success(f"Added upcoming release: **{title.strip()}**")
            st.rerun()
        except Exception as e:
            st.error(f"Error adding release: {e}")


# =========================================================
# Overview metrics
# =========================================================
watching_df = releases_df[releases_df["WatchStatus"] == "Watching"] if not releases_df.empty else pd.DataFrame()
released_df = releases_df[releases_df["WatchStatus"] == "Released"] if not releases_df.empty else pd.DataFrame()

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("Watching", len(watching_df))
metric_col2.metric("Released", len(released_df))

if not watching_df.empty and watching_df["ExpectedReleaseDate"].notna().any():
    next_release = watching_df[watching_df["ExpectedReleaseDate"].notna()].sort_values("ExpectedReleaseDate").iloc[0]
    metric_col3.metric("Next Release", pd.to_datetime(next_release["ExpectedReleaseDate"]).strftime("%b %d, %Y"))
else:
    metric_col3.metric("Next Release", "Unknown")

st.divider()

# =========================================================
# Delete confirmation
# =========================================================
if st.session_state.get("delete_release_id"):
    release_id = st.session_state["delete_release_id"]

    delete_row = releases_df[releases_df["ReleaseID"] == release_id]

    if not delete_row.empty:
        row = delete_row.iloc[0]

        st.divider()
        st.warning(f"Are you sure you want to delete **{row['Title']}**?")

        confirm_col, cancel_col = st.columns(2)

        with confirm_col:
            if st.button("Yes, delete this release", key=f"confirm_delete_{release_id}", width="stretch"):
                delete_release(release_id)

        with cancel_col:
            if st.button("Cancel", key=f"cancel_delete_{release_id}", width="stretch"):
                st.session_state["delete_release_id"] = None
                st.rerun()


# =========================================================
# Tabs
# =========================================================
watching_tab, needs_check_tab, released_tab, table_tab = st.tabs(
    ["👀 Watching", "🔎 Needs Checking", "✅ Released", "📋 Table View"]
)

with watching_tab:
    st.subheader("Watching")

    if watching_df.empty:
        st.info("No upcoming releases are currently being watched.")
    else:
        search = st.text_input("Search watching releases", key="watching_search")

        filtered_df = watching_df.copy()
        if search.strip():
            search_text = search.strip().lower()
            filtered_df = filtered_df[
                filtered_df["Title"].fillna("").str.lower().str.contains(search_text)
                | filtered_df["Authors"].fillna("").str.lower().str.contains(search_text)
                | filtered_df["SeriesName"].fillna("").str.lower().str.contains(search_text)
                | filtered_df["Narrators"].fillna("").str.lower().str.contains(search_text)
            ]

        if filtered_df.empty:
            st.info("No matching upcoming releases found.")
        else:
            for _, row in filtered_df.iterrows():
                render_release_card(row, section_key="watching")

with needs_check_tab:
    st.subheader("Needs Checking")
    st.caption("Shows watched releases that have never been checked, or have not been checked in 30+ days.")

    if watching_df.empty:
        st.info("No watched releases found.")
    else:
        today = pd.Timestamp.today().normalize()
        needs_check_df = watching_df[
            watching_df["LastChecked"].isna()
            | ((today - pd.to_datetime(watching_df["LastChecked"]).dt.normalize()).dt.days >= 30)
        ]

        if needs_check_df.empty:
            st.success("Everything has been checked recently.")
        else:
            for _, row in needs_check_df.iterrows():
                render_release_card(row, section_key="needs_check")

with released_tab:
    st.subheader("Released")

    if released_df.empty:
        st.info("No releases have been marked as released yet.")
    else:
        for _, row in released_df.iterrows():
            render_release_card(row, section_key="released", show_released_actions=True)

with table_tab:
    st.subheader("All Upcoming Release Records")

    if releases_df.empty:
        st.info("No upcoming release records found.")
    else:
        display_df = releases_df.copy()
        display_df["Expected"] = display_df.apply(format_release_date, axis=1)
        display_df["Series"] = display_df.apply(format_series_line, axis=1)

        st.dataframe(
            display_df[
                [
                    "Title",
                    "Authors",
                    "Series",
                    "Expected",
                    "Narrators",
                    "Publisher",
                    "WatchStatus",
                    "LastChecked",
                ]
            ],
            width='stretch',
            hide_index=True,
        )

# =========================================================
# Edit selected release
# =========================================================
if st.session_state.get("editing_release_id"):
    release_id = st.session_state["editing_release_id"]

    edit_row = releases_df[releases_df["ReleaseID"] == release_id]

    if edit_row.empty:
        st.warning("Selected release could not be found.")
        st.session_state["editing_release_id"] = None
    else:
        row = edit_row.iloc[0]

        st.divider()
        st.subheader(f"✏️ Edit: {row['Title']}")

        with st.form(f"edit_release_form_{release_id}"):
            title = st.text_input("Title", value=row["Title"] or "")
            authors = st.text_input("Authors", value=row["Authors"] or "")

            book_number = st.number_input(
                "Book Number",
                min_value=0.0,
                step=0.5,
                value=float(row["BookNumber"]) if pd.notna(row["BookNumber"]) else 0.0,
            )

            expected_release_date = st.date_input(
                "Expected Release Date",
                value=pd.to_datetime(row["ExpectedReleaseDate"]).date()
                if pd.notna(row["ExpectedReleaseDate"])
                else None,
            )

            release_date_precision = st.selectbox(
                "Release Date Precision",
                ["Exact", "Month", "Year", "Unknown"],
                index=["Exact", "Month", "Year", "Unknown"].index(row["ReleaseDatePrecision"])
                if row["ReleaseDatePrecision"] in ["Exact", "Month", "Year", "Unknown"]
                else 0,
            )

            publisher = st.text_input("Publisher", value=row["Publisher"] or "")
            narrators = st.text_input("Narrators", value=row["Narrators"] or "")

            save_col, cancel_col = st.columns(2)

            with save_col:
                save_changes = st.form_submit_button("💾 Save Changes", width="stretch")

            with cancel_col:
                cancel_edit = st.form_submit_button("Cancel", width="stretch")

        if save_changes:
            update_release(
                release_id=release_id,
                title=title.strip(),
                authors=authors.strip() if authors.strip() else None,
                series_id=int(row["SeriesID"]) if pd.notna(row["SeriesID"]) else None,
                book_number=book_number if book_number > 0 else None,
                expected_release_date=expected_release_date,
                release_date_precision=release_date_precision,
                publisher=publisher.strip() if publisher.strip() else None,
                narrators=narrators.strip() if narrators.strip() else None,
            )

        if cancel_edit:
            st.session_state["editing_release_id"] = None
            st.rerun()


