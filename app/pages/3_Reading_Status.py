import streamlit as st
from db import run_query, execute_procedure

st.title("📖 Update Reading Progress")

st.markdown("Update whether a reader has finished a book and optionally provide a rating.")

# Load books
books = run_query("""
SELECT BookID, Title, Authors
FROM vw_book_details
ORDER BY Authors, Title;
""")

book_options = {
    f"{row['Title']} — {row['Authors']}": (row["Title"], row["Authors"])
    for _, row in books.iterrows()
}

selected_label = st.selectbox("📚 Select Book", list(book_options.keys()))
selected_title, selected_authors = book_options[selected_label]

reader = st.selectbox("👤 Select Reader", ["Angela", "Tori"])

st.divider()

# Main form
read_status = st.toggle("Mark as Read")

rating = None
if read_status:
    rating = st.slider("⭐ Rating", 0.0, 5.0, 4.0, 0.1)
    st.caption("Optional: Leave as-is if you don't want to update rating.")

st.divider()

# ✅ Primary action
if st.button("💾 Save Reading Update", width='stretch'):
    try:
        execute_procedure(
            "SetReadStatus",
            [
                selected_title,
                selected_authors.split(",")[0].strip(),
                reader,
                int(read_status),
            ],
        )

        if read_status and rating is not None:
            execute_procedure(
                "SetReaderRating",
                [
                    selected_title,
                    selected_authors.split(",")[0].strip(),
                    reader,
                    rating,
                ],
            )

        st.success("Reading progress updated.")

    except Exception as e:
        st.error(f"Error: {e}")

# 🔻 Secondary actions section
st.divider()
st.subheader("⚙️ Additional Actions")

col1, col2 = st.columns(2)

# ↩️ Mark as Unread
with col1:
    if st.button("↩️ Mark as Unread", width='stretch'):
        try:
            execute_procedure(
                "SetReadStatus",
                [
                    selected_title,
                    selected_authors.split(",")[0].strip(),
                    reader,
                    0,
                ],
            )

            st.warning("Marked as unread.")

        except Exception as e:
            st.error(f"Error: {e}")

# 🧹 Clear Rating
with col2:
    if st.button("🧹 Clear Rating", width='stretch'):
        try:
            execute_procedure(
                "SetReaderRating",
                [
                    selected_title,
                    selected_authors.split(",")[0].strip(),
                    reader,
                    None,  # assumes your proc supports NULL
                ],
            )

            st.warning("Rating cleared.")

        except Exception as e:
            st.error(f"Error: {e}")