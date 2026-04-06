import streamlit as st
from db import run_query, get_pdf_page_count, render_pdf_page

st.title("💌 Cozy Corner Book Club")
st.markdown("Browse monthly flyers and view the books selected for each month.")

# Load available months
months_df = run_query("""
SELECT
    ClubID,
    ClubMonth,
    FlyerTheme,
    FlyerFilePath,
    Notes
FROM cozy_corner_book_club
ORDER BY ClubID ASC;
""")

if months_df.empty:
    st.info("No book club months found.")
    st.stop()

month_options = {
    f"{row['ClubMonth']} — {row['FlyerTheme'] if row['FlyerTheme'] else 'No Theme'}": row["ClubID"]
    for _, row in months_df.iterrows()
}

selected_label = st.selectbox(
    "📚 Select Book Club Month",
    ["— Select a month —"] + list(month_options.keys())
)

if selected_label == "— Select a month —":
    st.info("Select a month to view its books and flyer preview.")
    st.stop()

selected_club_id = month_options[selected_label]
selected_month = months_df[months_df["ClubID"] == selected_club_id].iloc[0]

club_month = selected_month["ClubMonth"]
flyer_theme = selected_month["FlyerTheme"] if selected_month["FlyerTheme"] else "—"
flyer_path = selected_month["FlyerFilePath"]
notes = selected_month["Notes"] if selected_month["Notes"] else ""

st.subheader(club_month)
st.write(f"**Theme:** {flyer_theme}")

if notes:
    st.caption(notes)

st.divider()

# Books for selected month
books_df = run_query("""
SELECT
    DisplayOrder,
    Title,
    Authors
FROM vw_bookclub_books
WHERE ClubID = ?
ORDER BY DisplayOrder, Title;
""", params=[selected_club_id])

st.subheader("Books for This Month")

if books_df.empty:
    st.info("No books found for this month.")
else:
    display_books = books_df.copy()
    display_books["DisplayOrder"] = display_books["DisplayOrder"].fillna("")
    st.dataframe(display_books, width="stretch", hide_index=True)

st.divider()

# Flyer preview
st.subheader("Flyer Preview")

if flyer_path:
    try:
        total_pages = get_pdf_page_count(flyer_path)

        page_key = f"flyer_page_{selected_club_id}"

        # Initialize page state for this flyer
        if page_key not in st.session_state:
            st.session_state[page_key] = 1

        # Keep page in valid range
        if st.session_state[page_key] < 1:
            st.session_state[page_key] = 1
        if st.session_state[page_key] > total_pages:
            st.session_state[page_key] = total_pages

        prev_col, info_col, next_col = st.columns([1, 2, 1])

        with prev_col:
            if st.button("⬅ Previous", key=f"prev_{selected_club_id}", width='stretch'):
                if st.session_state[page_key] > 1:
                    st.session_state[page_key] -= 1


        with next_col:
            if st.button("Next ➡", key=f"next_{selected_club_id}", width='stretch'):
                if st.session_state[page_key] < total_pages:
                    st.session_state[page_key] += 1

        selected_page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            step=1,
            key=page_key
        )

        with st.spinner("Loading flyer page..."):
            page_image = render_pdf_page(flyer_path, selected_page)

        st.image(page_image, caption=f"Flyer Page {selected_page}", width="stretch")

    except FileNotFoundError:
        st.warning(f"Flyer file not found: {flyer_path}")
    except Exception as e:
        st.error(f"Could not render flyer PDF: {e}")
else:
    st.info("No flyer file path is saved for this month.")