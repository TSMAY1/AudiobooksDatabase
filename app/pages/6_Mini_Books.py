import streamlit as st
import pandas as pd
from db import run_query, execute_procedure

st.set_page_config(page_title="Mini Books", layout="wide")

st.title("🎨 Mini Books")
st.markdown(
    "Track what still needs printing, what is printed and waiting to be crafted, and what is fully complete."
)

SUMMARY_QUERY = """
SELECT
    ReaderName,
    MiniBookStage,
    BookCount
FROM vw_reader_mini_books_dashboard_summary
ORDER BY ReaderName, MiniBookStage;
"""

DASHBOARD_QUERY = """
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
ORDER BY ReaderName, MiniBookStage, Authors, SeriesName, BookNumber, Title;
"""

READER_OPTIONS_QUERY = """
SELECT DISTINCT ReaderName
FROM readers
ORDER BY ReaderName;
"""


@st.cache_data(show_spinner=False)
def load_summary():
    return run_query(SUMMARY_QUERY)


@st.cache_data(show_spinner=False)
def load_dashboard():
    return run_query(DASHBOARD_QUERY)


@st.cache_data(show_spinner=False)
def load_readers():
    return run_query(READER_OPTIONS_QUERY)


def refresh_data():
    load_summary.clear()
    load_dashboard.clear()
    st.rerun()


def build_book_labels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SeriesDisplay"] = df["SeriesName"].fillna("Standalone")
    df["BookNumberDisplay"] = df["BookNumber"].apply(
        lambda x: f" #{x}" if pd.notna(x) else ""
    )
    df["BookLabel"] = (
        df["Title"]
        + " — "
        + df["Authors"]
        + " ("
        + df["SeriesDisplay"]
        + df["BookNumberDisplay"]
        + ")"
    )
    return df


def yes_no_map(series: pd.Series) -> pd.Series:
    normalized = (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return normalized.map({
        "1": "Yes",
        "0": "No",
        "true": "Yes",
        "false": "No",
        "yes": "Yes",
        "no": "No",
        "": "No",
    }).fillna("No")


def get_stage_style(stage: str) -> str:
    stage_map = {
        "To Print": "blue",
        "Printed Not Crafted": "amber",
        "Completed": "green",
    }
    return stage_map.get(stage, "gray")


def make_status_chip(label: str, kind: str = "gray") -> str:
    color_map = {
        "blue": ("rgba(59, 130, 246, 0.12)", "#C7D2FE"),
        "amber": ("rgba(245, 158, 11, 0.12)", "#FDE68A"),
        "green": ("rgba(16, 185, 129, 0.12)", "#BBF7D0"),
        "gray": ("rgba(148, 163, 184, 0.14)", "#E5E7EB"),
        "red": ("rgba(239, 68, 68, 0.12)", "#FECACA"),
    }
    bg_color, text_color = color_map.get(kind, color_map["gray"])
    return (
        f'<span style="display:inline-block;padding:0.34rem 0.72rem;'
        f'border-radius:999px;background-color:{bg_color};color:{text_color};'
        f'font-weight:600;font-size:0.88rem;margin:0 0.35rem 0.35rem 0;'
        f'border:1px solid rgba(255,255,255,0.06);">{label}</span>'
    )


def get_next_action(stage: str) -> tuple[str, str]:
    action_map = {
        "To Print": (
            "🖨️ Print mini book",
            "This book should be printed at the next opportunity.",
        ),
        "Printed Not Crafted": (
            "✂️ Craft mini book",
            "This mini book has already been printed and is now waiting to be crafted.",
        ),
        "Completed": (
            "✅ No action needed",
            "This mini book is complete. Great work!",
        ),
    }
    return action_map.get(
        stage,
        (
            "ℹ️ Review mini book status",
            "This book does not currently match one of the expected workflow stages.",
        ),
    )


def get_action_style(action_color: str) -> dict:
    action_style_map = {
        "blue": {
            "bg": "rgba(30, 64, 175, 0.16)",
            "border": "rgba(96, 165, 250, 0.42)",
            "text": "#DBEAFE",
        },
        "amber": {
            "bg": "rgba(146, 64, 14, 0.16)",
            "border": "rgba(251, 191, 36, 0.42)",
            "text": "#FDE68A",
        },
        "green": {
            "bg": "rgba(6, 95, 70, 0.16)",
            "border": "rgba(52, 211, 153, 0.40)",
            "text": "#D1FAE5",
        },
        "gray": {
            "bg": "rgba(55, 65, 81, 0.26)",
            "border": "rgba(156, 163, 175, 0.32)",
            "text": "#E5E7EB",
        },
    }
    return action_style_map.get(action_color, action_style_map["gray"])


def format_display_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        return df

    df["SeriesName"] = df["SeriesName"].fillna("Standalone")
    df["BookNumber"] = df["BookNumber"].fillna("—")
    df["IsPrinted"] = yes_no_map(df["IsPrinted"])
    df["IsCrafted"] = yes_no_map(df["IsCrafted"])
    return df


summary_df = load_summary()
dashboard_df = load_dashboard()
readers_df = load_readers()

if dashboard_df.empty:
    st.info("No mini book data found yet.")
    st.stop()

dashboard_df = build_book_labels(dashboard_df)

all_readers = ["All Readers"] + readers_df["ReaderName"].tolist()
all_stages = ["All Stages", "To Print", "Printed Not Crafted", "Completed"]

filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])

with filter_col1:
    selected_reader = st.selectbox("Reader", all_readers)

with filter_col2:
    selected_stage = st.selectbox("Workflow stage", all_stages)

with filter_col3:
    search_text = st.text_input("Search by title, author, or series")

filtered_df = dashboard_df.copy()

if selected_reader != "All Readers":
    filtered_df = filtered_df[filtered_df["ReaderName"] == selected_reader]

if selected_stage != "All Stages":
    filtered_df = filtered_df[filtered_df["MiniBookStage"] == selected_stage]

if search_text:
    mask = (
        filtered_df["Title"].str.contains(search_text, case=False, na=False)
        | filtered_df["Authors"].str.contains(search_text, case=False, na=False)
        | filtered_df["SeriesName"].fillna("").str.contains(search_text, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

st.subheader("Mini Book Summary")

if selected_reader == "All Readers":
    summary_view = summary_df.copy()
else:
    summary_view = summary_df[summary_df["ReaderName"] == selected_reader].copy()

summary_order = {"To Print": 0, "Printed Not Crafted": 1, "Completed": 2}
summary_view["StageSort"] = summary_view["MiniBookStage"].map(summary_order)
summary_view = summary_view.sort_values(["ReaderName", "StageSort", "MiniBookStage"])

if summary_view.empty:
    st.caption("No summary rows match the current filters.")
else:
    metric_cols = st.columns(max(1, min(len(summary_view), 4)))
    for i, (_, row) in enumerate(summary_view.iterrows()):
        with metric_cols[i % len(metric_cols)]:
            st.metric(
                label=f"{row['ReaderName']} — {row['MiniBookStage']}",
                value=int(row["BookCount"])
            )

st.subheader("Workflow")

display_columns = [
    "ReaderName",
    "Authors",
    "Title",
    "SeriesName",
    "BookNumber",
    "ReadingStatus",
    "IsPrinted",
    "IsCrafted",
]

tab_to_print, tab_printed, tab_completed = st.tabs(
    ["🖨️ To Print", "✂️ Printed Not Crafted", "✅ Completed"]
)

with tab_to_print:
    to_print_df = filtered_df[filtered_df["MiniBookStage"] == "To Print"][display_columns].copy()
    st.caption("Books that are read but still need a mini book printed.")
    st.dataframe(format_display_table(to_print_df), use_container_width=True, hide_index=True)

with tab_printed:
    printed_df = filtered_df[filtered_df["MiniBookStage"] == "Printed Not Crafted"][display_columns].copy()
    st.caption("Mini books that have been printed and still need crafting.")
    st.dataframe(format_display_table(printed_df), use_container_width=True, hide_index=True)

with tab_completed:
    completed_df = filtered_df[filtered_df["MiniBookStage"] == "Completed"][display_columns].copy()
    st.caption("Mini books that are fully complete.")
    st.dataframe(format_display_table(completed_df), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Quick Update")

editable_df = filtered_df.copy()

if editable_df.empty:
    st.info("No books available for update with the current filters.")
    st.stop()

editor_reader_options = sorted(editable_df["ReaderName"].dropna().unique().tolist())
editor_reader = st.selectbox(
    "Choose a reader to update",
    editor_reader_options,
    key="editor_reader"
)

reader_books_df = editable_df[editable_df["ReaderName"] == editor_reader].copy()

stage_order = {
    "To Print": 0,
    "Printed Not Crafted": 1,
    "Completed": 2,
}
reader_books_df["StageSort"] = reader_books_df["MiniBookStage"].map(stage_order).fillna(99)

reader_books_df = reader_books_df.sort_values(
    by=["StageSort", "Authors", "SeriesName", "BookNumber", "Title"]
)

selected_book_label = st.selectbox(
    "Choose a book",
    reader_books_df["BookLabel"].tolist(),
    key="selected_book_label"
)

selected_row = reader_books_df[reader_books_df["BookLabel"] == selected_book_label].iloc[0]

series_name = selected_row["SeriesName"] if pd.notna(selected_row["SeriesName"]) else "Standalone"
book_number = selected_row["BookNumber"] if pd.notna(selected_row["BookNumber"]) else "—"

chips_html = "".join([
    make_status_chip(f"Reading: {selected_row['ReadingStatus']}", "gray"),
    make_status_chip(f"Stage: {selected_row['MiniBookStage']}", get_stage_style(selected_row["MiniBookStage"])),
    make_status_chip(
        f"Printed: {'Yes' if int(selected_row['IsPrinted']) == 1 else 'No'}",
        "green" if int(selected_row["IsPrinted"]) == 1 else "gray",
    ),
    make_status_chip(
        f"Crafted: {'Yes' if int(selected_row['IsCrafted']) == 1 else 'No'}",
        "green" if int(selected_row["IsCrafted"]) == 1 else "gray",
    ),
])

action_title, action_text = get_next_action(selected_row["MiniBookStage"])
action_color = get_stage_style(selected_row["MiniBookStage"])
style = get_action_style(action_color)

card_col1, card_col2 = st.columns([1.18, 1], gap="large")

with card_col1:
    st.markdown(
        f"""
<div style="
    padding: 1.15rem 1.2rem;
    border-radius: 1rem;
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(71, 85, 105, 0.14);
    margin-top: 0.35rem;
">
    <div style="font-size: 1.14rem; font-weight: 700; margin-bottom: 0.35rem;">
        {selected_row['Title']}
    </div>
    <div style="font-size: 0.97rem; opacity: 0.95; margin-bottom: 0.9rem;">
        {selected_row['Authors']}
    </div>
    <div style="margin-bottom: 0.48rem;"><span style="font-weight: 700;">Series:</span> {series_name}</div>
    <div style="margin-bottom: 0.48rem;"><span style="font-weight: 700;">Book Number:</span> {book_number}</div>
    <div style="margin-top: 0.95rem;">{chips_html}</div>
</div>
        """,
        unsafe_allow_html=True,
    )

with card_col2:
    st.markdown(
        f"""
<div style="
    padding: 1.15rem 1.2rem;
    border-radius: 1rem;
    background-color: {style['bg']};
    border: 1px solid {style['border']};
    margin-top: 0.35rem;
    box-shadow: 0 0 0 1px {style['border']}22;
">
    <div style="
        font-size: 0.81rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.72rem;
        color: {style['text']};
        opacity: 0.92;
    ">
        Next Step
    </div>
    <div style="
        font-size: 1.01rem;
        font-weight: 700;
        margin-bottom: 0.48rem;
        color: {style['text']};
    ">
        {action_title}
    </div>
    <div style="
        font-size: 0.96rem;
        line-height: 1.52;
        color: {style['text']};
    ">
        {action_text}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### Quick Actions")
st.caption("Update the selected mini book using the most common workflow actions.")

action_col1, action_col2, action_col3 = st.columns(3)

with action_col1:
    if st.button("🖨️ Mark Printed", use_container_width=True):
        try:
            with st.spinner("Updating mini book status..."):
                execute_procedure(
                    "SetMiniBookStatus",
                    [int(selected_row["BookID"]), editor_reader, 1, 0],
                )
            st.success(f"Marked '{selected_row['Title']}' as printed.")
            refresh_data()
        except Exception as e:
            st.error(f"Could not update mini book status. Error: {e}")

with action_col2:
    if st.button("✅ Mark Completed", use_container_width=True):
        try:
            with st.spinner("Updating mini book status..."):
                execute_procedure(
                    "SetMiniBookStatus",
                    [int(selected_row["BookID"]), editor_reader, 1, 1],
                )
            st.success(f"Marked '{selected_row['Title']}' as completed.")
            refresh_data()
        except Exception as e:
            st.error(f"Could not update mini book status. Error: {e}")

with action_col3:
    if st.button("↺ Reset to Not Started", use_container_width=True):
        try:
            with st.spinner("Updating mini book status..."):
                execute_procedure(
                    "SetMiniBookStatus",
                    [int(selected_row["BookID"]), editor_reader, 0, 0],
                )
            st.success(f"Reset '{selected_row['Title']}' to not started.")
            refresh_data()
        except Exception as e:
            st.error(f"Could not update mini book status. Error: {e}")

st.markdown("### Manual Override")

with st.expander("Show manual checkboxes"):
    current_is_printed = bool(selected_row["IsPrinted"])
    current_is_crafted = bool(selected_row["IsCrafted"])

    with st.form("mini_book_status_form"):
        is_printed = st.checkbox("Printed", value=current_is_printed)
        is_crafted = st.checkbox("Crafted", value=current_is_crafted)

        if is_crafted and not is_printed:
            st.warning("A mini book cannot be crafted unless it has been printed first.")

        submitted = st.form_submit_button("Save Manual Status", use_container_width=True)

        if submitted:
            if is_crafted and not is_printed:
                st.error("Please mark the mini book as printed before marking it crafted.")
            else:
                try:
                    with st.spinner("Updating mini book status..."):
                        execute_procedure(
                            "SetMiniBookStatus",
                            [
                                int(selected_row["BookID"]),
                                editor_reader,
                                int(is_printed),
                                int(is_crafted),
                            ],
                        )
                    st.success(f"Updated mini book status for '{selected_row['Title']}'.")
                    refresh_data()
                except Exception as e:
                    st.error(f"Could not update mini book status. Error: {e}")