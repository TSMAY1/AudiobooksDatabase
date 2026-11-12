"""Loopback-only web preview for the audiobook library."""
from contextlib import closing
from decimal import Decimal, InvalidOperation
import logging
import mimetypes
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from db import get_connection
from storage import local_asset_path, normalize_asset_path, read_asset_bytes


ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "cozy-preview"
LOGGER = logging.getLogger("uvicorn.error")
COVER_PATTERN = r"covers/\d+/[\w.-]+\.(?:webp|png|jpe?g)"
STATUSES = {"Unread", "TBR", "Reading", "Read", "DNF"}
EDIT_FIELDS = {"title", "author", "series", "number", "description", "genre", "tags"}
CATALOG_SQL = """
    SELECT b.BookID, b.Title, b.Authors, b.SeriesName, b.BookNumber,
           c.ImageFilePath
    FROM dbo.vw_book_details b
    LEFT JOIN dbo.vw_book_primary_cover c ON c.BookID = b.BookID
    ORDER BY b.DateAdded DESC, b.BookID DESC
"""
DETAIL_SQL = """
    SELECT Description FROM dbo.books WHERE BookID = ?
"""
LABEL_SQL = """
    SELECT bg.GenreType, g.GenreName
    FROM dbo.book_genres bg JOIN dbo.genres g ON g.GenreID = bg.GenreID
    WHERE bg.BookID = ?
    ORDER BY g.GenreName
"""
EDITION_SQL = """
    SELECT EditionName, Narrators, Publisher, ReleaseYear, DurationDisplay
    FROM dbo.vw_book_audiobooks
    WHERE BookID = ?
    ORDER BY ReleaseYear DESC, AudiobookVersionID
"""


def cover_url(stored_path):
    if not stored_path:
        return None
    try:
        path = normalize_asset_path(stored_path)
    except ValueError:
        return None
    if re.fullmatch(COVER_PATTERN, path, re.IGNORECASE):
        return "/assets/" + quote(path)
    return None


def catalog(request):
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        books = [
            {
                "id": row.BookID,
                "title": row.Title,
                "author": row.Authors,
                "series": row.SeriesName if row.SeriesName != "Standalone" else None,
                "number": str(row.BookNumber) if row.BookNumber is not None else "",
                "order": f"Book {row.BookNumber.normalize():f}" if row.BookNumber is not None else None,
                "coverUrl": cover_url(row.ImageFilePath),
                "statuses": {},
            }
            for row in cursor.execute(CATALOG_SQL)
        ]
        by_id = {book["id"]: book for book in books}
        readers = [row[0] for row in cursor.execute(
            "SELECT ReaderName FROM dbo.readers ORDER BY ReaderName"
        )]
        for book_id, reader, status in cursor.execute("""
            SELECT rs.BookID, r.ReaderName, rs.ReadingStatus
            FROM dbo.reading_status rs
            JOIN dbo.readers r ON r.ReaderID = rs.ReaderID
        """):
            if book_id in by_id:
                by_id[book_id]["statuses"][reader] = status

    return JSONResponse({"books": books, "readers": readers, "editable": True},
                        headers={"Cache-Control": "no-store"})


def book_details(cursor, book_id):
    book = cursor.execute(DETAIL_SQL, book_id).fetchone()
    if book is None:
        return None
    labels = {"Main": [], "Tag": []}
    for kind, name in cursor.execute(LABEL_SQL, book_id):
        if kind in labels:
            labels[kind].append(name)
    editions = [
        {
            "name": row.EditionName,
            "narrators": row.Narrators,
            "publisher": row.Publisher,
            "year": row.ReleaseYear,
            "duration": row.DurationDisplay,
        }
        for row in cursor.execute(EDITION_SQL, book_id)
    ]
    return {"description": book.Description, "genre": ", ".join(labels["Main"]),
            "tags": labels["Tag"], "editions": editions}


def details(request):
    book_id = request.path_params["book_id"]
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        payload = book_details(cursor, book_id)
    if payload is None:
        return JSONResponse({"error": "Book not found."}, status_code=404)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


async def mutation(request, save):
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        return JSONResponse({"error": "Open The Listening Room locally to save changes."}, status_code=403)
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return JSONResponse({"error": "Expected a JSON request."}, status_code=415)
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("Expected an object.")
        return await run_in_threadpool(save, request.path_params["book_id"], data)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)


def save_status(book_id, data):
    reader, status = data.get("reader"), data.get("status")
    if not isinstance(reader, str) or not reader.strip() or len(reader) > 255:
        raise ValueError("Choose a reader.")
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError("Choose a valid reading status.")
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        if cursor.execute("SELECT 1 FROM dbo.books WHERE BookID = ?", book_id).fetchone() is None:
            return JSONResponse({"error": "Book not found."}, status_code=404)
        if cursor.execute("SELECT 1 FROM dbo.readers WHERE ReaderName = ?", reader).fetchone() is None:
            raise ValueError("Reader not found.")
        cursor.execute("EXEC dbo.SetReadingStatus ?, ?, ?", book_id, reader, status)
        connection.commit()
    return JSONResponse({"status": status})


def save_book(book_id, data):
    if not data or data.keys() - EDIT_FIELDS or any(not isinstance(value, str) for value in data.values()):
        raise ValueError("Supply the book fields you want to change.")
    data = {key: value.strip() for key, value in data.items()}
    for key in {"title", "author", "series"} & data.keys():
        if not data[key] or (key != "author" and len(data[key].encode("utf-16-le")) > 510):
            raise ValueError("Enter a title, at least one author, and a series or Standalone.")
    for key in {"author", "genre", "tags"} & data.keys():
        names = [name.strip() for name in data[key].split(",") if name.strip()]
        if (key == "author" and not names) or any(len(name.encode("utf-16-le")) > 510 for name in names):
            raise ValueError("Use comma-separated names of up to 255 characters each.")
    number = None
    if data.get("number"):
        try:
            number = Decimal(data["number"])
            if not number.is_finite() or abs(number) > Decimal("999.9") or number != number.quantize(Decimal("0.1")):
                raise InvalidOperation
        except InvalidOperation:
            raise ValueError("Enter a book number between -999.9 and 999.9 with up to one decimal place.") from None

    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        current = cursor.execute("""
            SELECT b.Title, s.SeriesName, b.BookNumber, b.UniverseReadingOrder,
                   b.LengthType, b.Demographic, b.Description
            FROM dbo.books b WITH (UPDLOCK, HOLDLOCK)
            LEFT JOIN dbo.series s ON s.SeriesID = b.SeriesID
            WHERE b.BookID = ?
        """, book_id).fetchone()
        if current is None:
            return JSONResponse({"error": "Book not found."}, status_code=404)
        if data.keys() & {"title", "series", "number", "description"}:
            cursor.execute(
                "EXEC dbo.UpdateBookCoreDetails ?, ?, ?, ?, ?, ?, ?, ?",
                book_id, data.get("title", current.Title), data.get("series", current.SeriesName or "Standalone"),
                number if "number" in data else current.BookNumber,
                current.UniverseReadingOrder, current.LengthType, current.Demographic,
                data.get("description", current.Description),
            )
        if "author" in data:
            cursor.execute("EXEC dbo.UpdateBookAuthors ?, ?", book_id, data["author"])
        if data.keys() & {"genre", "tags"}:
            labels = {"Main": [], "Tag": []}
            for kind, name in cursor.execute(LABEL_SQL, book_id):
                if kind in labels:
                    labels[kind].append(name)
            cursor.execute(
                "EXEC dbo.UpdateBookGenres ?, ?, ?", book_id,
                data.get("genre", ", ".join(labels["Main"])),
                data.get("tags", ", ".join(labels["Tag"])),
            )
        row = cursor.execute("""
            SELECT Title, Authors, SeriesName, BookNumber FROM dbo.vw_book_details WHERE BookID = ?
        """, book_id).fetchone()
        payload = book_details(cursor, book_id)
        payload["book"] = {
            "title": row.Title, "author": row.Authors,
            "series": row.SeriesName if row.SeriesName != "Standalone" else None,
            "number": str(row.BookNumber) if row.BookNumber is not None else "",
            "order": f"Book {row.BookNumber.normalize():f}" if row.BookNumber is not None else None,
        }
        connection.commit()
    return JSONResponse(payload)


async def update_status(request):
    return await mutation(request, save_status)


async def update_book(request):
    return await mutation(request, save_book)


def cover_image(request):
    path = request.path_params["path"]
    if not re.fullmatch(COVER_PATTERN, path, re.IGNORECASE):
        return Response(status_code=404)
    headers = {"Cache-Control": "public, max-age=86400"}
    local = local_asset_path(path)
    if local.is_file():
        return FileResponse(local, headers=headers)
    try:
        data = read_asset_bytes(path)
    except FileNotFoundError:
        return Response(status_code=404)
    except Exception as error:
        if getattr(error, "status_code", None) == 404:
            return Response(status_code=404)
        LOGGER.warning("Cover lookup failed for %s (%s)", PurePosixPath(path).name, type(error).__name__)
        return Response(status_code=503)
    return Response(data, media_type=mimetypes.guess_type(path)[0], headers=headers)


def index(request):
    return FileResponse(PREVIEW / "index.html")


def static_file(request):
    name = request.path_params["name"]
    if name not in {"app.js", "books.js", "styles.css"}:
        return Response(status_code=404)
    return FileResponse(PREVIEW / name)


async def api_error(request, error):
    LOGGER.error("Library API %s failed (%s): %s", request.url.path, type(error).__name__, error)
    message = "The live library could not be loaded."
    if request.method == "PATCH":
        message = "The database could not confirm this save. Reopen the book to check its current values."
    if "Another book already exists with this title, series, and book number." in str(error):
        return JSONResponse({"error": "Another book already uses that title, series, and book number."}, status_code=409)
    return JSONResponse({"error": message}, status_code=503)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/index.html", index),
        Route("/api/library", catalog),
        Route("/api/books/{book_id:int}", details),
        Route("/api/books/{book_id:int}", update_book, methods=["PATCH"]),
        Route("/api/books/{book_id:int}/status", update_status, methods=["PATCH"]),
        Route("/assets/{path:path}", cover_image),
        Route("/{name}", static_file),
    ],
    middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])],
    exception_handlers={Exception: api_error},
)

