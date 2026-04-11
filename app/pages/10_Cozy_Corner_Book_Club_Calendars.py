import streamlit as st
from db import run_query, render_pdf_to_images

st.title("🗓️ Book Club Calendars")
st.markdown("View yearly Cozy Corner Book Club calendar PDFs.")

calendars_df = run_query("""
SELECT
    CalendarID,
    YearNum,
    CalendarFilePath,
    Notes
FROM bookclub_calendars
ORDER BY YearNum DESC;
""")

if calendars_df.empty:
    st.info("No calendars found.")
    st.stop()

calendar_options = {
    str(row["YearNum"]): row["CalendarID"]
    for _, row in calendars_df.iterrows()
}

selected_year = st.selectbox("📅 Select Calendar Year", list(calendar_options.keys()))
selected_calendar_id = calendar_options[selected_year]

selected_calendar = calendars_df[calendars_df["CalendarID"] == selected_calendar_id].iloc[0]
calendar_path = selected_calendar["CalendarFilePath"]
notes = selected_calendar["Notes"] if selected_calendar["Notes"] else ""

st.subheader(f"{selected_year} Calendar")

if notes:
    st.caption(notes)

if calendar_path:
    try:
        calendar_images = render_pdf_to_images(calendar_path)
        for i, image_bytes in enumerate(calendar_images, start=1):
            st.image(image_bytes, caption=f"Calendar Page {i}", width='content')
    except FileNotFoundError:
        st.warning(f"Calendar file not found: {calendar_path}")
    except Exception as e:
        st.error(f"Could not render calendar PDF: {e}")
else:
    st.info("No calendar file path is saved for this year.")