import streamlit as st
import pandas as pd

from db import run_query, load_cover_image_bytes, execute_non_query


st.set_page_config(page_title="Recommendations", layout="wide")

st.title("📚 Book Recommendations")

st.markdown("""
<style>
div.stButton > button {
    width: 100%;
    border-radius: 0.5rem;
    min-height: 38.4px;
    padding: 0.25rem 0.75rem;
    background-color: rgba(75,85,99,0.9);
    border: 1px solid rgba(156,163,175,0.35);
    color: white;
    font-size: 1rem;
    font-weight: 400;
    line-height: 1.6;
}

div.stButton > button:hover {
    background-color: rgba(107,114,128,0.95);
    border: 1px solid rgba(209,213,219,0.45);
    color: white;
}

div.stButton > button:disabled {
    background-color: rgba(75,85,99,0.35);
    border: 1px solid rgba(156,163,175,0.2);
    color: rgba(255,255,255,0.55);
}
</style>
""", unsafe_allow_html=True)

st.caption("Pick a reader and a book they liked, then find similar unread books.")


def format_book_number(value):
    if pd.isna(value):
        return ""
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return str(value)

def add_to_tbr(reader_id, book_id):
    execute_non_query("""
        UPDATE reading_status
        SET ReadingStatus = 'TBR'
        WHERE ReaderID = ?
          AND BookID = ?
          AND ReadingStatus = 'Unread';
    """, params=[reader_id, book_id])

    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def get_readers():
    return run_query("""
        SELECT ReaderID, ReaderName
        FROM readers
        ORDER BY ReaderName;
    """)


@st.cache_data(show_spinner=False)
def get_source_books(reader_id):
    return run_query("""
        SELECT
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.BookNumber,
            rs.Rating
        FROM reading_status rs
        JOIN vw_book_details bd
            ON bd.BookID = rs.BookID
        WHERE rs.ReaderID = ?
          AND rs.ReadingStatus = 'Read'
        ORDER BY
            CASE WHEN rs.Rating IS NULL THEN 1 ELSE 0 END,
            rs.Rating DESC,
            bd.Title;
    """, params=[reader_id])


@st.cache_data(show_spinner=False)
def get_recommendations(reader_id, source_book_id, include_tbr=False, limit=10):
    allowed_statuses = "('Unread', 'TBR')" if include_tbr else "('Unread')"

    query = f"""
    WITH source_book AS (
        SELECT
            b.BookID,
            b.SeriesID,
            s.ParentSeriesID,
            COALESCE(s.ParentSeriesID, s.SeriesID) AS UniverseID,
            b.Demographic,
            av.DurationMinutes,
            av.IsFullCast
        FROM books b
        JOIN series s
            ON s.SeriesID = b.SeriesID
        OUTER APPLY (
            SELECT TOP 1
                av.DurationMinutes,
                av.IsFullCast
            FROM audiobook_versions av
            WHERE av.BookID = b.BookID
            ORDER BY av.AudiobookVersionID
        ) av
        WHERE b.BookID = ?
    ),
    candidate_books AS (
        SELECT
            bd.BookID,
            bd.Title,
            bd.Authors,
            bd.SeriesName,
            bd.ParentSeriesName,
            bd.UniverseName,
            bd.BookNumber,
            bd.Demographic,
            bd.UniverseReadingOrder,
            rs.ReadingStatus,
            pc.ImageFilePath,
            av.DurationMinutes,
            av.DurationDisplay,
            av.IsFullCast,
            av.Narrators
        FROM reading_status rs
        JOIN vw_book_details bd
            ON bd.BookID = rs.BookID
        LEFT JOIN vw_book_primary_cover pc
            ON pc.BookID = bd.BookID
        OUTER APPLY (
            SELECT TOP 1
                bav.DurationMinutes,
                bav.DurationDisplay,
                bav.IsFullCast,
                bav.Narrators
            FROM vw_book_audiobooks bav
            WHERE bav.BookID = bd.BookID
            ORDER BY bav.AudiobookVersionID
        ) av
        WHERE rs.ReaderID = ?
          AND rs.ReadingStatus IN {allowed_statuses}
          AND bd.BookID <> ?
    ),
    scored AS (
        SELECT
            cb.*,

            CASE WHEN EXISTS (
                SELECT 1
                FROM book_genres sg
                JOIN book_genres cg
                    ON cg.GenreID = sg.GenreID
                   AND cg.GenreType = 'Main'
                WHERE sg.BookID = ?
                  AND sg.GenreType = 'Main'
                  AND cg.BookID = cb.BookID
            ) THEN 25 ELSE 0 END AS MainGenreScore,

            CASE WHEN EXISTS (
                SELECT 1
                FROM book_genres sg
                JOIN book_genres cg
                    ON cg.GenreID = sg.GenreID
                   AND cg.GenreType = 'Secondary'
                WHERE sg.BookID = ?
                  AND sg.GenreType = 'Secondary'
                  AND cg.BookID = cb.BookID
            ) THEN 10 ELSE 0 END AS SecondaryGenreScore,

            CASE WHEN EXISTS (
                SELECT 1
                FROM book_authors sa
                JOIN book_authors ca
                    ON ca.AuthorID = sa.AuthorID
                WHERE sa.BookID = ?
                  AND ca.BookID = cb.BookID
            ) THEN 20 ELSE 0 END AS AuthorScore,

            CASE WHEN EXISTS (
                SELECT 1
                FROM source_book sb
                JOIN books cb_books
                    ON cb_books.BookID = cb.BookID
                JOIN series cs
                    ON cs.SeriesID = cb_books.SeriesID
                WHERE COALESCE(cs.ParentSeriesID, cs.SeriesID) = sb.UniverseID
            ) THEN 15 ELSE 0 END AS UniverseScore,

            CASE WHEN EXISTS (
                SELECT 1
                FROM source_book sb
                JOIN books cb_books
                    ON cb_books.BookID = cb.BookID
                JOIN series cs
                    ON cs.SeriesID = cb_books.SeriesID
                WHERE
                    COALESCE(cs.ParentSeriesID, cs.SeriesID) = sb.UniverseID
                    AND cs.SeriesName = 'Standalone'
            ) THEN 1 ELSE 0 END AS StandaloneUniverseMatch,

            CASE WHEN EXISTS (
                SELECT 1
                FROM audiobook_versions sav
                JOIN audiobook_version_narrators san
                    ON san.AudiobookVersionID = sav.AudiobookVersionID
                JOIN audiobook_versions cav
                    ON cav.BookID = cb.BookID
                JOIN audiobook_version_narrators canr
                    ON canr.AudiobookVersionID = cav.AudiobookVersionID
                   AND canr.NarratorID = san.NarratorID
                WHERE sav.BookID = ?
            ) THEN 20 ELSE 0 END AS NarratorScore,

            CASE WHEN cb.Demographic = (SELECT Demographic FROM source_book)
                      AND cb.Demographic IS NOT NULL
                 THEN 8 ELSE 0 END AS DemographicScore,

            CASE WHEN cb.IsFullCast = (SELECT IsFullCast FROM source_book)
                      AND cb.IsFullCast IS NOT NULL
                 THEN 5 ELSE 0 END AS FullCastScore,

            CASE WHEN cb.DurationMinutes IS NOT NULL
                      AND (SELECT DurationMinutes FROM source_book) IS NOT NULL
                      AND ABS(cb.DurationMinutes - (SELECT DurationMinutes FROM source_book)) <= 120
                 THEN 10 ELSE 0 END AS LengthScore

        FROM candidate_books cb
    )
    SELECT TOP (?)
        *,
        (
            MainGenreScore
            + SecondaryGenreScore
            + AuthorScore
            + UniverseScore
            + NarratorScore
            + DemographicScore
            + FullCastScore
            + LengthScore
        ) AS RecommendationScore
    FROM scored
    WHERE (
            MainGenreScore
            + SecondaryGenreScore
            + AuthorScore
            + UniverseScore
            + NarratorScore
            + DemographicScore
            + FullCastScore
            + LengthScore
        ) > 0
    ORDER BY
        RecommendationScore DESC,
        Title;
    """

    return run_query(
        query,
        params=[
            source_book_id,
            reader_id,
            source_book_id,
            source_book_id,
            source_book_id,
            source_book_id,
            source_book_id,
            limit,
        ],
    )


def build_reason_tags(row):
    reasons = []

    if row["MainGenreScore"] > 0:
        reasons.append("Main genre match")
    if row["SecondaryGenreScore"] > 0:
        reasons.append("Secondary genre match")
    if row["AuthorScore"] > 0:
        reasons.append("Same author")
    if row["UniverseScore"] > 0:
        if row["StandaloneUniverseMatch"] == 1:
            reasons.append("Similar standalone")
        else:
            reasons.append("Same universe/series family")
    if row["NarratorScore"] > 0:
        reasons.append("Same narrator")
    if row["DemographicScore"] > 0:
        reasons.append("Same demographic")
    if row["FullCastScore"] > 0:
        reasons.append("Similar cast style")
    if row["LengthScore"] > 0:
        reasons.append("Similar audiobook length")

    return reasons


readers = get_readers()

if readers.empty:
    st.warning("No readers found.")
    st.stop()

reader_name = st.selectbox(
    "Choose a reader",
    readers["ReaderName"].tolist()
)

reader_id = int(readers.loc[readers["ReaderName"] == reader_name, "ReaderID"].iloc[0])

source_books = get_source_books(reader_id)

if source_books.empty:
    st.warning(f"No read books found for {reader_name}.")
    st.stop()

source_books["DisplayName"] = source_books.apply(
    lambda row: (
        f"{row['Title']} — {row['Authors']}"
        + (
            f" ({row['SeriesName']} #{format_book_number(row['BookNumber'])})"
            if pd.notna(row["SeriesName"]) and row["SeriesName"] != "Standalone"
            else ""
        )
        + (
            f" ⭐ {row['Rating']}"
            if pd.notna(row["Rating"])
            else ""
        )
    ),
    axis=1
)

selected_source = st.selectbox(
    "Recommend books similar to:",
    source_books["DisplayName"].tolist()
)

source_book_id = int(
    source_books.loc[
        source_books["DisplayName"] == selected_source,
        "BookID"
    ].iloc[0]
)

col1, col2 = st.columns([1, 1])

with col1:
    include_tbr = st.checkbox("Include books already on TBR", value=False)

with col2:
    limit = st.slider("Number of recommendations", 5, 25, 10)

recommendations = get_recommendations(
    reader_id=reader_id,
    source_book_id=source_book_id,
    include_tbr=include_tbr,
    limit=limit
)

st.divider()

if recommendations.empty:
    st.info("No recommendations found yet. Try including TBR books or choosing a different source book.")
    st.stop()

st.subheader(f"Top recommendations for {reader_name}")

for _, row in recommendations.iterrows():
    with st.container(border=True):
        cover_col, info_col = st.columns([1, 4])

        with cover_col:
            if pd.notna(row.get("ImageFilePath")):
                try:
                    cover_bytes = load_cover_image_bytes(row["ImageFilePath"])
                    st.image(cover_bytes, width=180)
                except Exception:
                    st.caption("No cover")
            else:
                st.caption("No cover")

        with info_col:
            title_line = row["Title"]

            formatted_number = format_book_number(row["BookNumber"])
            if pd.notna(row["SeriesName"]) and row["SeriesName"] != "Standalone":
                if formatted_number:
                    title_line += f" — {row['SeriesName']} #{formatted_number}"
                else:
                    title_line += f" — {row['SeriesName']}"

            st.markdown(f"### {title_line}")
            st.caption(row["Authors"])

            meta_bits = []

            if pd.notna(row.get("UniverseName")):
                meta_bits.append(f"Universe: {row['UniverseName']}")

            if pd.notna(row.get("DurationDisplay")):
                meta_bits.append(f"Length: {row['DurationDisplay']}")

            if pd.notna(row.get("Narrators")):
                meta_bits.append(f"Narrated by: {row['Narrators']}")

            if meta_bits:
                st.caption(" • ".join(meta_bits))

            st.markdown(f"**Recommendation score:** {int(row['RecommendationScore'])}")

            reasons = build_reason_tags(row)

            if reasons:
                tag_html = " ".join(
                    [
                        f"<span style='display:inline-block; padding:4px 8px; margin:3px; "
                        f"border-radius:999px; background-color:rgba(128,128,128,0.18); "
                        f"font-size:0.85rem;'>{reason}</span>"
                        for reason in reasons
                    ]
                )
                st.markdown(tag_html, unsafe_allow_html=True)
            
            action_col1, action_col2, action_col3 = st.columns([1, 1, 2])

            button_style = """
                width:100%;
                box-sizing:border-box;
                padding:0.25rem 0.75rem;
                border-radius:0.5rem;
                border:1px solid rgba(156,163,175,0.35);
                background-color:rgba(75,85,99,0.9);
                color:white;
                text-align:center;
                font-size:1rem;
                font-weight:400;
                line-height:1.6;
                min-height:38.4px;
                display:flex;
                align-items:center;
                justify-content:center;
            """

            disabled_button_style = """
                width:100%;
                box-sizing:border-box;
                padding:0.45rem 0.6rem;
                border-radius:0.5rem;
                border:1px solid rgba(156,163,175,0.25);
                background-color:rgba(75,85,99,0.35);
                color:rgba(255,255,255,0.55);
                text-align:center;
                font-size:0.85rem;
                line-height:1.2;
                min-height:38px;
            """

            with action_col1:
                if row["ReadingStatus"] == "TBR":
                    st.markdown(
                        f"""
                        <div style="{disabled_button_style}">
                            On TBR
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    if st.button(
                        "Add to TBR",
                        key=f"add_tbr_{reader_id}_{row['BookID']}",
                        use_container_width=True
                    ):
                        add_to_tbr(reader_id, int(row["BookID"]))
                        st.success(f"Added {row['Title']} to {reader_name}'s TBR!")
                        st.rerun()

            with action_col2:
                book_id = int(row["BookID"])
                details_url = f"/Book_Details?book_id={book_id}"

                st.markdown(
                    f"""
                    <a href="{details_url}" target="_blank" style="text-decoration:none;">
                        <div style="{button_style}">
                            Open details
                        </div>
                    </a>
                    """,
                    unsafe_allow_html=True
                )

            with action_col3:
                st.markdown(
                    f"""
                    <div style="
                        text-align:right;
                        padding-top:0.45rem;
                        opacity:0.75;
                        font-size:0.9rem;
                    ">
                        Recommendation Score: <strong>{int(row['RecommendationScore'])}</strong>
                    </div>
                    """,
                    unsafe_allow_html=True
                )