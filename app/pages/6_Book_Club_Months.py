import streamlit as st
from db import run_query, render_pdf_to_images

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

selected_label = st.selectbox("📚 Select Book Club Month", list(month_options.keys()))
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
    st.dataframe(display_books, width='stretch', hide_index=True)

st.divider()

# Flyer preview
st.subheader("Flyer Preview")

if flyer_path:
    try:
        flyer_images = render_pdf_to_images(flyer_path)
        for i, image_bytes in enumerate(flyer_images, start=1):
            st.image(image_bytes, caption=f"Flyer Page {i}", width='content')
    except FileNotFoundError:
        st.warning(f"Flyer file not found: {flyer_path}")
    except Exception as e:
        st.error(f"Could not render flyer PDF: {e}")
else:
    st.info("No flyer file path is saved for this month.")