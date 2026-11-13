import base64
from contextlib import suppress
import html
import pyodbc
import pandas as pd
import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
import fitz # PyMuPDF
import hashlib
import time
import uuid
from io import BytesIO
from PIL import Image, ImageOps
from storage import delete_asset, local_asset_path, read_asset_bytes, write_asset_bytes


load_dotenv()


def build_connection_string() -> str:
    auth_mode = os.getenv("DB_AUTH_MODE", "trusted").strip().lower()
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("DB_SERVER", "").strip()
    database = os.getenv("DB_NAME", "").strip()

    if not server or not database:
        raise ValueError("DB_SERVER and DB_NAME must be configured.")

    common = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"

    if auth_mode == "azure_cli":
        return common + "Encrypt=yes;TrustServerCertificate=no;"

    if auth_mode == "managed_identity":
        return (
            common
            + "Authentication=ActiveDirectoryMsi;"
            + "Encrypt=yes;TrustServerCertificate=no;"
        )

    if auth_mode == "trusted":
        trusted = os.getenv("DB_TRUSTED_CONNECTION", "yes")
        return common + f"Trusted_Connection={trusted};"

    raise ValueError("DB_AUTH_MODE must be 'trusted', 'managed_identity', or 'azure_cli'.")


TRANSIENT_SQL_ERROR_CODES = (
    "40197",  # Azure SQL encountered a temporary service error.
    "40501",  # Azure SQL is temporarily busy.
    "40613",  # A paused/serverless database is waking up.
    "49918",
    "49919",
    "49920",  # Azure SQL temporarily cannot accept more requests.
)


def get_connection(max_attempts: int = 5):
    connection_string = build_connection_string()

    for attempt in range(max_attempts):
        try:
            if os.getenv("DB_AUTH_MODE", "trusted").strip().lower() == "azure_cli":
                import struct
                from azure.identity import AzureCliCredential

                token = AzureCliCredential().get_token("https://database.windows.net/.default")
                encoded = token.token.encode("utf-16-le")
                access_token = struct.pack("<I", len(encoded)) + encoded
                return pyodbc.connect(
                    connection_string, attrs_before={1256: access_token}, timeout=30
                )
            return pyodbc.connect(connection_string, timeout=30)
        except pyodbc.Error as exc:
            is_transient = any(code in str(exc) for code in TRANSIENT_SQL_ERROR_CODES)
            if not is_transient or attempt == max_attempts - 1:
                raise

            # Give a paused Azure SQL database time to wake up without making
            # readers manually refresh through several temporary failures.
            time.sleep(2 ** (attempt + 1))


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

def execute_procedure_returning_id(proc_name, params, id_column="BookID"):
    placeholders = ", ".join(["?"] * len(params))
    sql = f"EXEC {proc_name} {placeholders}"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)

        row = cursor.fetchone()

        if row is None:
            conn.commit()
            return None

        returned_id = getattr(row, id_column, None)

        conn.commit()
        return int(returned_id) if returned_id is not None else None


fitz.TOOLS.mupdf_display_warnings(False)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_asset_path(stored_path: str) -> Path:
    """
    Convert a database-stored relative path like
    'assets\\Flyers\\2024-71\\file.pdf'
    into an absolute path under the project root.
    """
    return local_asset_path(stored_path)


@st.cache_data(show_spinner=False)
def render_pdf_to_images(pdf_path: str):
    images = []
    pdf_bytes = read_asset_bytes(pdf_path)

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            images.append(pix.tobytes("png"))

    return images

@st.cache_data(show_spinner=False)
def get_pdf_page_count(pdf_path: str) -> int:
    pdf_bytes = read_asset_bytes(pdf_path)

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return len(doc)


@st.cache_data(show_spinner=False)
def render_pdf_page(pdf_path: str, page_number: int):
    """
    Render a single PDF page to PNG bytes.
    page_number is 1-based for easier use in the UI.
    """
    pdf_bytes = read_asset_bytes(pdf_path)

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
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
    target_size=(400, 600),
    deduplicate=False,
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
        if not cursor.execute("SELECT 1 FROM books WITH (UPDLOCK, HOLDLOCK) WHERE BookID = ?", book_id).fetchone():
            raise ValueError("Book not found.")
        if deduplicate:
            existing = cursor.execute("""
                SELECT TOP 1 CoverID FROM book_covers WHERE BookID = ? AND ImageHash = ?
                ORDER BY IsPrimary DESC, SortOrder, CoverID
            """, book_id, image_hash).fetchone()
            if existing:
                if make_primary:
                    mark_primary_cover(cursor, book_id, existing[0])
                conn.commit()
                return

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

        filename = f"cover_{uuid.uuid4().hex[:8]}.webp"
        relative_file_path = Path("assets") / "covers" / str(book_id) / filename
        db_file_path = str(relative_file_path).replace("/", "\\")

        write_asset_bytes(db_file_path, image_bytes)

        try:
            cursor.execute("""
                INSERT INTO book_covers (
                    BookID, CoverLabel, ImageFilePath, ImageFormat, WidthPx, HeightPx,
                    FileSizeKB, ImageHash, SortOrder, IsPrimary, SourceNotes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book_id, cover_label or None, db_file_path, "webp", width_px, height_px,
                file_size_kb, image_hash, next_sort_order, int(should_be_primary), source_notes or None
            ))
        except Exception:
            with suppress(Exception):
                delete_asset(db_file_path)
            raise

        conn.commit()


def mark_primary_cover(cursor, book_id, cover_id):
    cursor.execute("UPDATE book_covers SET IsPrimary = 0 WHERE BookID = ? AND IsPrimary = 1", book_id)
    cursor.execute("UPDATE book_covers SET IsPrimary = 1 WHERE BookID = ? AND CoverID = ?", book_id, cover_id)
    if cursor.rowcount == 0:
        raise ValueError("Cover not found for this book.")


def set_primary_cover(cover_id: int, expected_book_id=None):
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
        if expected_book_id is not None and expected_book_id != book_id:
            raise ValueError("Cover not found for this book.")
        cursor.execute("SELECT 1 FROM books WITH (UPDLOCK, HOLDLOCK) WHERE BookID = ?", book_id).fetchone()
        mark_primary_cover(cursor, book_id, cover_id)
        conn.commit()


def delete_cover(cover_id: int, expected_book_id=None):
    """
    Delete a cover record and its image file.
    If the deleted cover was primary, promote the next available cover.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        book_id = expected_book_id
        if book_id is None:
            row = cursor.execute("SELECT BookID FROM book_covers WHERE CoverID = ?", cover_id).fetchone()
            if not row:
                raise ValueError("Cover not found.")
            book_id = row[0]

        cursor.execute("SELECT 1 FROM books WITH (UPDLOCK, HOLDLOCK) WHERE BookID = ?", book_id).fetchone()
        row = cursor.execute("""
            SELECT ImageFilePath, IsPrimary FROM book_covers WHERE BookID = ? AND CoverID = ?
        """, book_id, cover_id).fetchone()
        if not row:
            raise ValueError("Cover not found for this book.")
        image_file_path, was_primary = row
        cursor.execute("DELETE FROM book_covers WHERE BookID = ? AND CoverID = ?", book_id, cover_id)

        if was_primary:
            replacement = cursor.execute("""
                SELECT TOP 1 CoverID
                FROM book_covers
                WHERE BookID = ?
                ORDER BY SortOrder ASC, CoverID ASC
            """, book_id).fetchone()
            if replacement:
                mark_primary_cover(cursor, book_id, replacement[0])

        shared_asset = cursor.execute(
            "SELECT TOP 1 1 FROM book_covers WHERE ImageFilePath = ?", image_file_path
        ).fetchone()
        conn.commit()

    if not shared_asset:
        with suppress(Exception):
            delete_asset(image_file_path)

@st.cache_data(show_spinner=False)
def load_cover_image_bytes(image_file_path: str) -> bytes:
    return read_asset_bytes(image_file_path)

def format_book_number(num):
    if pd.isna(num):
        return ""

    try:
        num = float(num)
        if num.is_integer():
            return str(int(num))
        return f"{num:.1f}".rstrip("0").rstrip(".")
    except Exception:
        return str(num)


def format_duration(minutes):
    if pd.isna(minutes):
        return ""

    try:
        minutes = int(minutes)
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins:02d}m"
    except Exception:
        return ""


def format_series(series, num):
    if pd.notna(series) and series:
        formatted_num = format_book_number(num)
        return f"{series} #{formatted_num}" if formatted_num else str(series)
    return "Standalone"


def detail_link(book_id):
    return f"/Book_Details?book_id={int(book_id)}"


def render_clickable_cover(image_bytes, book_id, title, width="100%", max_width=None):
    """Render cover bytes as an accessible link to the book details page."""
    if image_bytes:
        if image_bytes.startswith(b"\x89PNG"):
            mime_type = "image/png"
        elif image_bytes.startswith((b"GIF87a", b"GIF89a")):
            mime_type = "image/gif"
        elif image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"

        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        safe_title = html.escape(str(title))
        css_width = f"{width}px" if isinstance(width, int) else str(width)
        max_width_style = (
            f"max-width:{max_width}px;" if max_width is not None else ""
        )
        cover_markup = (
            f'<img src="data:{mime_type};base64,{encoded_image}" '
            f'alt="{safe_title}" '
            f'style="width:{css_width};{max_width_style}height:auto;'
            'border-radius:0.5rem;display:block;cursor:pointer;" />'
        )
    else:
        safe_title = html.escape(str(title))
        cover_markup = (
            '<div style="aspect-ratio:2/3;width:100%;border-radius:0.5rem;'
            'display:flex;align-items:center;justify-content:center;'
            'background:rgba(128,128,128,0.12);font-size:2rem;">📖</div>'
        )

    st.markdown(
        f'<a href="{detail_link(book_id)}" target="_blank" '
        f'aria-label="Open {safe_title}" '
        f'style="display:inline-block;width:100%;">{cover_markup}</a>',
        unsafe_allow_html=True,
    )


def bump_cache_key(key: str):
    st.session_state[key] = st.session_state.get(key, 0) + 1


def bump_book_related_caches():
    for key in [
        "library_cache_buster",
        "book_details_cache_buster",
        "manage_audiobooks_cache_buster",
        "upcoming_releases_cache_buster",
    ]:
        bump_cache_key(key)
