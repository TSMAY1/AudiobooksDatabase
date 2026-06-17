import streamlit as st
import html


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

def chip(label, kind="gray"):
    colors = {
        "green": ("#dcfce7", "#166534"),
        "blue": ("#dbeafe", "#1d4ed8"),
        "amber": ("#fef3c7", "#92400e"),
        "red": ("#fee2e2", "#991b1b"),
        "gray": ("#f3f4f6", "#374151"),
        "purple": ("#ede9fe", "#6d28d9"),
    }
    bg, fg = colors.get(kind, colors["gray"])
    safe_label = html.escape(str(label))
    return (
        f"<span style='display:inline-block;padding:3px 8px;"
        f"border-radius:999px;background:{bg};color:{fg};"
        f"font-size:0.78rem;font-weight:600;margin:0 4px 4px 0;'>"
        f"{safe_label}</span>"
    )


def render_chips(items):
    if items:
        st.markdown(" ".join(items), unsafe_allow_html=True)


def status_chip(status):
    mapping = {
        "Read": "green",
        "Reading": "blue",
        "TBR": "amber",
        "DNF": "red",
        "Unread": "gray",
    }
    return chip(status, mapping.get(status, "gray"))


def yes_no_chip(label, value):
    return chip(label, "green" if value else "gray")