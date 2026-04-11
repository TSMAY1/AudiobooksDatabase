import pyodbc
import pandas as pd
import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
import fitz # PyMuPDF
import hashlib
import uuid
from io import BytesIO
from PIL import Image, ImageOps


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
    
def get_cover_storage_dir(book_id: int) -> Path:
    """
    Returns the absolute folder path for a book's cover images.
    Example: assets/covers/123/
    """
    relative_dir = Path("assets") / "covers" / str(book_id)
    absolute_dir = resolve_asset_path(str(relative_dir).replace("/", "\\"))
    absolute_dir.mkdir(parents=True, exist_ok=True)
    return absolute_dir


def process_cover_image(uploaded_file, target_size=(400, 600), quality=85):
    """
    Convert an uploaded image into a standardized WEBP file on a fixed canvas.

    Returns:
        image_bytes, width_px, height_px, file_size_kb, image_hash
    """
    uploaded_file.seek(0)

    with Image.open(uploaded_file) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")

        canvas_width, canvas_height = target_size
        img.thumbnail((canvas_width, canvas_height))

        canvas = Image.new("RGB", (canvas_width, canvas_height), "white")

        offset_x = (canvas_width - img.width) // 2
        offset_y = (canvas_height - img.height) // 2
        canvas.paste(img, (offset_x, offset_y))

        buffer = BytesIO()
        canvas.save(buffer, format="WEBP", quality=quality, method=6)
        image_bytes = buffer.getvalue()

    width_px, height_px = target_size
    file_size_kb = round(len(image_bytes) / 1024, 2)
    image_hash = hashlib.sha256(image_bytes).hexdigest()

    return image_bytes, width_px, height_px, file_size_kb, image_hash


@st.cache_data(show_spinner=False)
def get_book_covers(book_id: int) -> pd.DataFrame:
    query = """
    SELECT
        CoverID,
        BookID,
        CoverLabel,
        ImageFilePath,
        ImageFormat,
        WidthPx,
        HeightPx,
        FileSizeKB,
        ImageHash,
        SortOrder,
        IsPrimary,
        SourceNotes,
        DateAdded
    FROM book_covers
    WHERE BookID = ?
    ORDER BY IsPrimary DESC, SortOrder ASC, CoverID ASC;
    """
    return run_query(query, params=[book_id])


def save_book_cover(
    book_id: int,
    uploaded_file,
    cover_label: str = None,
    source_notes: str = None,
    make_primary: bool = False,
    target_size=(400, 600)
):
    """
    Process an uploaded image, save it to disk, and insert its metadata into SQL Server.
    """
    image_bytes, width_px, height_px, file_size_kb, image_hash = process_cover_image(
        uploaded_file,
        target_size=target_size
    )

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ISNULL(MAX(SortOrder), 0) + 1
            FROM book_covers
            WHERE BookID = ?
        """, book_id)
        next_sort_order = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM book_covers
            WHERE BookID = ? AND IsPrimary = 1
        """, book_id)
        has_primary = cursor.fetchone()[0] > 0

        should_be_primary = make_primary or not has_primary

        if should_be_primary:
            cursor.execute("""
                UPDATE book_covers
                SET IsPrimary = 0
                WHERE BookID = ?
            """, book_id)

        storage_dir = get_cover_storage_dir(book_id)
        filename = f"cover_{uuid.uuid4().hex[:8]}.webp"
        absolute_file_path = storage_dir / filename
        absolute_file_path.write_bytes(image_bytes)

        relative_file_path = Path("assets") / "covers" / str(book_id) / filename
        db_file_path = str(relative_file_path).replace("/", "\\")

        cursor.execute("""
            INSERT INTO book_covers (
                BookID,
                CoverLabel,
                ImageFilePath,
                ImageFormat,
                WidthPx,
                HeightPx,
                FileSizeKB,
                ImageHash,
                SortOrder,
                IsPrimary,
                SourceNotes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            book_id,
            cover_label if cover_label else None,
            db_file_path,
            "webp",
            width_px,
            height_px,
            file_size_kb,
            image_hash,
            next_sort_order,
            1 if should_be_primary else 0,
            source_notes if source_notes else None
        ))

        conn.commit()


def set_primary_cover(cover_id: int):
    """
    Mark one cover as the primary cover for its book.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT BookID
            FROM book_covers
            WHERE CoverID = ?
        """, cover_id)

        row = cursor.fetchone()
        if not row:
            raise ValueError("Cover not found.")

        book_id = row[0]

        cursor.execute("""
            UPDATE book_covers
            SET IsPrimary = 0
            WHERE BookID = ?
        """, book_id)

        cursor.execute("""
            UPDATE book_covers
            SET IsPrimary = 1
            WHERE CoverID = ?
        """, cover_id)

        conn.commit()


def delete_cover(cover_id: int):
    """
    Delete a cover record and its image file.
    If the deleted cover was primary, promote the next available cover.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT BookID, ImageFilePath, IsPrimary
            FROM book_covers
            WHERE CoverID = ?
        """, cover_id)

        row = cursor.fetchone()
        if not row:
            raise ValueError("Cover not found.")

        book_id, image_file_path, was_primary = row

        cursor.execute("""
            DELETE FROM book_covers
            WHERE CoverID = ?
        """, cover_id)

        if was_primary:
            cursor.execute("""
                SELECT TOP 1 CoverID
                FROM book_covers
                WHERE BookID = ?
                ORDER BY SortOrder ASC, CoverID ASC
            """, book_id)

            replacement = cursor.fetchone()
            if replacement:
                cursor.execute("""
                    UPDATE book_covers
                    SET IsPrimary = 1
                    WHERE CoverID = ?
                """, replacement[0])

        conn.commit()

    try:
        absolute_file_path = resolve_asset_path(image_file_path)
        if absolute_file_path.exists():
            absolute_file_path.unlink()
    except Exception:
        pass

@st.cache_data(show_spinner=False)
def load_cover_image_bytes(image_file_path: str) -> bytes:
    absolute_file_path = resolve_asset_path(image_file_path)

    if not absolute_file_path.exists():
        raise FileNotFoundError(f"Cover image not found: {absolute_file_path}")

    return absolute_file_path.read_bytes()