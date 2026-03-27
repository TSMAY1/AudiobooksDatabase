import pyodbc
import pandas as pd
import os
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