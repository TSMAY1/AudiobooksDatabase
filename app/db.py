import pyodbc
import pandas as pd
import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
import fitz # PyMuPDF


load_dotenv()

conn_str = (
    f"DRIVER={{{os.getenv('DB_DRIVER')}}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"Trusted_Connection={os.getenv('DB_TRUSTED_CONNECTION')};"
)


def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-ACE2DSF\\SQLEXPRESS;"
        "DATABASE=Audiobooks;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def run_query(query, params=None):
    with get_connection() as conn:
        return pd.read_sql(query, conn, params=params)


def execute_non_query(sql, params=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()


def execute_procedure(proc_name, params):
    placeholders = ", ".join(["?"] * len(params))
    sql = f"EXEC {proc_name} {placeholders}"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()


fitz.TOOLS.mupdf_display_warnings(False)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_asset_path(stored_path: str) -> Path:
    """
    Convert a database-stored relative path like
    'assets\\Flyers\\2024-71\\file.pdf'
    into an absolute path under the project root.
    """
    if not stored_path:
        raise ValueError("No file path provided.")

    normalized = stored_path.replace("\\", "/")
    return PROJECT_ROOT / normalized


@st.cache_data(show_spinner=False)
def render_pdf_to_images(pdf_path: str):
    pdf_file = resolve_asset_path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"PDF not found. Stored path: '{pdf_path}' | Resolved path: '{pdf_file}'"
        )

    images = []

    with fitz.open(pdf_file) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            images.append(pix.tobytes("png"))

    return images

@st.cache_data(show_spinner=False)
def get_pdf_page_count(pdf_path: str) -> int:
    pdf_file = resolve_asset_path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"PDF not found. Stored path: '{pdf_path}' | Resolved path: '{pdf_file}'"
        )

    with fitz.open(pdf_file) as doc:
        return len(doc)


@st.cache_data(show_spinner=False)
def render_pdf_page(pdf_path: str, page_number: int):
    """
    Render a single PDF page to PNG bytes.
    page_number is 1-based for easier use in the UI.
    """
    pdf_file = resolve_asset_path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"PDF not found. Stored path: '{pdf_path}' | Resolved path: '{pdf_file}'"
        )

    with fitz.open(pdf_file) as doc:
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Page {page_number} is out of range for this PDF.")

        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        return pix.tobytes("png")