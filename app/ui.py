import streamlit as st


def inject_global_styles():
    st.markdown(
        """
        <style>
        .book-title-link,
        .book-title-link:visited,
        .book-title-link:active {
            color: inherit !important;
            text-decoration: none !important;
            font-weight: 700;
        }

        .book-title-link:hover {
            color: inherit !important;
            text-decoration: underline !important;
            text-decoration-thickness: 1px;
            text-underline-offset: 4px;
            opacity: 0.9;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def configure_page(title: str, page_title: str | None = None, icon: str | None = None):
    kwargs = {
        "page_title": page_title or title,
        "layout": "wide",
    }

    if icon:
        kwargs["page_icon"] = icon

    st.set_page_config(**kwargs)
    inject_global_styles()