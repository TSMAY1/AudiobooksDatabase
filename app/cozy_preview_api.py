"""Web preview for the audiobook library, with opt-in home network access."""
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from ipaddress import IPv4Address
import logging
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote

from PIL import Image
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from db import delete_cover, get_connection, save_book_cover, set_primary_cover
from storage import local_asset_path, normalize_asset_path, read_asset_bytes


ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "cozy-preview"
LOGGER = logging.getLogger("uvicorn.error")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if home_wifi_address := os.getenv("COZY_HOME_WIFI_ADDRESS"):
    ALLOWED_HOSTS.append(str(IPv4Address(home_wifi_address)))
COVER_PATTERN = r"covers/\d+/[\w.-]+\.(?:webp|png|jpe?g)"
COVER_UPLOAD_LIMIT = 8 * 1024 * 1024
COVER_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif"}
STATUSES = {"Unread", "TBR", "Reading", "Read", "DNF"}
EDIT_FIELDS = {"title", "author", "series", "number", "universeOrder", "description", "genre", "tags"}
CATALOG_SQL = """
    SELECT b.BookID, b.Title, b.Authors, b.SeriesName, b.ParentSeriesName, b.BookNumber,
           b.UniverseReadingOrder,
           c.ImageFilePath
    FROM dbo.vw_book_details b
    LEFT JOIN dbo.vw_book_primary_cover c ON c.BookID = b.BookID
    ORDER BY b.DateAdded DESC, b.BookID DESC
"""
DETAIL_SQL = """
    SELECT Description FROM dbo.books WHERE BookID = ?
"""
AUTHOR_CREDITS_SQL = """
    SELECT ba.BookID, a.AuthorID, a.AuthorName
    FROM dbo.book_authors ba JOIN dbo.authors_new a ON a.AuthorID = ba.AuthorID
"""
NARRATOR_CREDITS_SQL = """
    SELECT av.BookID, av.AudiobookVersionID, av.EditionName, av.Publisher,
           av.ReleaseYear, av.DurationMinutes, n.NarratorID, n.NarratorName
    FROM dbo.audiobook_version_narrators avn
    JOIN dbo.narrators n ON n.NarratorID = avn.NarratorID
    JOIN dbo.audiobook_versions av ON av.AudiobookVersionID = avn.AudiobookVersionID
"""
LABEL_SQL = """
    SELECT bg.GenreType, g.GenreName
    FROM dbo.book_genres bg JOIN dbo.genres g ON g.GenreID = bg.GenreID
    WHERE bg.BookID = ?
    ORDER BY g.GenreName
"""
EDITION_SQL = """
    SELECT AudiobookVersionID, EditionName, Narrators, Publisher, ReleaseYear,
           DurationDisplay, DurationMinutes, IsAbridged, IsFullCast, Notes
    FROM dbo.vw_book_audiobooks
    WHERE BookID = ?
    ORDER BY ReleaseYear DESC, AudiobookVersionID
"""
ACTIVITY_SQL = """
    SELECT BookID, ReaderName, ReadingStatus, Rating, CurrentStatusSince, MostRecentReadDate
    FROM dbo.vw_reader_books
"""
COMMENT_SQL = """
    SELECT CommentID, BookID, ReaderName, Title, CommentText, DateAdded
    FROM dbo.vw_reader_book_comments
"""


def activity(row):
    if row is None:
        return {}
    return {
        "rating": float(row.Rating) if row.Rating is not None else None,
        "since": row.CurrentStatusSince.isoformat() if row.CurrentStatusSince else None,
        "finished": row.MostRecentReadDate.isoformat() if row.MostRecentReadDate else None,
    }


def comments(rows):
    return [
        {"id": row.CommentID, "bookId": row.BookID, "reader": row.ReaderName, "title": row.Title,
         "text": row.CommentText, "date": row.DateAdded.isoformat()}
        for row in rows
    ]


def recent_comments(cursor, reader):
    return comments(cursor.execute(
        COMMENT_SQL + " WHERE ReaderName = ? ORDER BY DateAdded DESC, CommentID DESC OFFSET 0 ROWS FETCH NEXT 4 ROWS ONLY",
        reader,
    ))


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
                "authorCredits": [],
                "series": row.SeriesName if row.SeriesName != "Standalone" else None,
                "parentSeries": row.ParentSeriesName,
                "universeOrder": format(row.UniverseReadingOrder.normalize(), "f")
                if row.UniverseReadingOrder is not None else None,
                "number": str(row.BookNumber) if row.BookNumber is not None else "",
                "order": f"Book {row.BookNumber.normalize():f}" if row.BookNumber is not None else None,
                "coverUrl": cover_url(row.ImageFilePath),
                "statuses": {},
                "activity": {},
            }
            for row in cursor.execute(CATALOG_SQL)
        ]
        by_id = {book["id"]: book for book in books}
        for book_id, author_id, author_name in cursor.execute(
            AUTHOR_CREDITS_SQL + " ORDER BY ba.BookID, ba.AuthorOrder, a.AuthorName"
        ):
            if book_id in by_id:
                by_id[book_id]["authorCredits"].append({"id": author_id, "name": author_name})
        readers = [row[0] for row in cursor.execute(
            "SELECT ReaderName FROM dbo.readers ORDER BY ReaderName"
        )]
        for row in cursor.execute(ACTIVITY_SQL):
            if row.BookID in by_id:
                by_id[row.BookID]["statuses"][row.ReaderName] = row.ReadingStatus
                by_id[row.BookID]["activity"][row.ReaderName] = activity(row)
        favorites = {name: book_id for name, book_id in cursor.execute("""
            SELECT r.ReaderName, f.BookID FROM dbo.reader_favorite_books f
            JOIN dbo.readers r ON r.ReaderID = f.ReaderID
        """)}

    return JSONResponse({"books": books, "readers": readers, "editable": True,
                         "adminEditing": True, "coverEditing": True, "editionEditing": True,
                         "bookCreation": True, "favorites": favorites, "readingEdits": True},
                        headers={"Cache-Control": "no-store"})


def editions_for_book(cursor, book_id):
    editions = [
        {
            "id": row.AudiobookVersionID,
            "name": row.EditionName,
            "narrators": row.Narrators,
            "narratorCredits": [],
            "publisher": row.Publisher,
            "year": row.ReleaseYear,
            "duration": row.DurationDisplay,
            "minutes": row.DurationMinutes,
            "abridged": bool(row.IsAbridged),
            "fullCast": bool(row.IsFullCast),
            "notes": row.Notes,
        }
        for row in cursor.execute(EDITION_SQL, book_id)
    ]
    by_edition = {edition["id"]: edition for edition in editions}
    for row in cursor.execute(
        NARRATOR_CREDITS_SQL + " WHERE av.BookID = ? ORDER BY avn.DisplayOrder, n.NarratorName", book_id
    ):
        edition = by_edition.get(row.AudiobookVersionID)
        if edition is not None:
            edition["narratorCredits"].append({"id": row.NarratorID, "name": row.NarratorName})
    return editions


def book_details(cursor, book_id):
    book = cursor.execute(DETAIL_SQL, book_id).fetchone()
    if book is None:
        return None
    labels = {"Main": [], "Tag": []}
    for kind, name in cursor.execute(LABEL_SQL, book_id):
        if kind in labels:
            labels[kind].append(name)
    return {"description": book.Description, "genre": ", ".join(labels["Main"]),
            "tags": labels["Tag"], "editions": editions_for_book(cursor, book_id)}


def details(request):
    book_id = request.path_params["book_id"]
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        payload = book_details(cursor, book_id)
        if payload is not None:
            payload["comments"] = comments(cursor.execute(
                COMMENT_SQL + " WHERE BookID = ? ORDER BY DateAdded DESC, CommentID DESC", book_id
            ))
    if payload is None:
        return JSONResponse({"error": "Book not found."}, status_code=404)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def reader_comments(request):
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        payload = recent_comments(cursor, request.query_params.get("reader", ""))
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def narrator_credits(request):
    narrators = {}
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        for row in cursor.execute(NARRATOR_CREDITS_SQL):
            narrator = narrators.setdefault(
                row.NarratorID, {"id": row.NarratorID, "name": row.NarratorName, "editions": []}
            )
            minutes = row.DurationMinutes
            narrator["editions"].append({
                "id": row.AudiobookVersionID,
                "bookId": row.BookID,
                "name": row.EditionName,
                "publisher": row.Publisher,
                "year": row.ReleaseYear,
                "duration": f"{minutes // 60}h {minutes % 60:02d}m" if minutes is not None else None,
            })
    return JSONResponse(list(narrators.values()), headers={"Cache-Control": "no-store"})


def allowed_origin(request):
    origin = request.headers.get("origin")
    return not origin or origin == f"{request.url.scheme}://{request.url.netloc}"


async def mutation(request, save):
    if not allowed_origin(request):
        return JSONResponse({"error": "Open The Listening Room directly to save changes."}, status_code=403)
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return JSONResponse({"error": "Expected a JSON request."}, status_code=415)
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("Expected an object.")
        return await run_in_threadpool(save, request.path_params.get("book_id", request.path_params.get("release_id")), data)
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
        effective = reading_date(data.get("date"))
        if effective is None:
            cursor.execute("EXEC dbo.SetReadingStatus ?, ?, ?", book_id, reader, status)
        else:
            cursor.execute("EXEC dbo.SetReadingStatus ?, ?, ?, ?", book_id, reader, status, effective)
        saved_activity = activity(cursor.execute(
            ACTIVITY_SQL + " WHERE BookID = ? AND ReaderName = ?", book_id, reader
        ).fetchone())
        connection.commit()
    return JSONResponse({"status": status, "activity": saved_activity})


def reading_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Enter a valid date.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid date.") from None


def reading_history(request):
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        events = [
            {"id": str(row.StatusHistoryID), "from": row.FromStatus, "to": row.ToStatus,
             "date": row.EffectiveDate.isoformat() if row.EffectiveDate else None, "notes": row.Notes}
            for row in cursor.execute("""
                SELECT h.StatusHistoryID, h.FromStatus, h.ToStatus, h.EffectiveDate, h.Notes
                FROM dbo.reader_book_status_history h JOIN dbo.readers r ON r.ReaderID = h.ReaderID
                WHERE h.BookID = ? AND r.ReaderName = ?
                ORDER BY h.ChangedAtUtc DESC, h.StatusHistoryID DESC
            """, request.path_params["book_id"], request.query_params.get("reader", ""))
        ]
    return JSONResponse({"events": events}, headers={"Cache-Control": "no-store"})


def save_reading_edit(book_id, data, kind, event_id=None):
    reader = data.get("reader")
    if not isinstance(reader, str) or not reader.strip() or len(reader) > 255:
        raise ValueError("Choose a reader.")
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        person = cursor.execute("""
            SELECT ReaderID FROM dbo.readers WITH (UPDLOCK, HOLDLOCK) WHERE ReaderName = ?
        """, reader).fetchone()
        if person is None:
            raise ValueError("Reader not found.")
        reader_id = person[0]
        if cursor.execute("SELECT 1 FROM dbo.books WHERE BookID = ?", book_id).fetchone() is None:
            return JSONResponse({"error": "Book not found."}, status_code=404)
        if kind == "history":
            effective = reading_date(data.get("date"))
            notes = data.get("notes", "")
            if not isinstance(notes, str) or len(notes.strip().encode("utf-16-le")) > 1000:
                raise ValueError("Keep notes to 500 characters.")
            if cursor.execute("""
                SELECT 1 FROM dbo.reader_book_status_history WITH (UPDLOCK, HOLDLOCK)
                WHERE StatusHistoryID = ? AND BookID = ? AND ReaderID = ?
            """, event_id, book_id, reader_id).fetchone() is None:
                return JSONResponse({"error": "Reading history entry not found."}, status_code=404)
            cursor.execute("EXEC dbo.UpdateStatusHistoryEvent ?, ?, ?", event_id, effective, notes)
        elif kind == "rating":
            raw = data.get("rating")
            if not isinstance(raw, str):
                raise ValueError("Enter a rating from 0 to 5 with up to two decimal places, or leave it blank.")
            rating = book_position(raw, "0.01", "5", "Enter a rating from 0 to 5 with up to two decimal places.")
            if rating is not None and rating < 0:
                raise ValueError("Enter a rating from 0 to 5.")
            if rating is not None or cursor.execute("""
                SELECT 1 FROM dbo.reading_status WHERE BookID = ? AND ReaderID = ?
            """, book_id, reader_id).fetchone():
                if rating is not None:
                    ensure_reader_book(cursor, book_id, reader_id)
                cursor.execute("EXEC dbo.SetReaderRating ?, ?, ?", book_id, reader, rating)
        else:
            favorite = data.get("favorite")
            expected = data.get("expected")
            if type(favorite) is not bool or (expected is not None and type(expected) is not int):
                raise ValueError("Choose a valid favourite action.")
            existing = cursor.execute("""
                SELECT BookID FROM dbo.reader_favorite_books WITH (UPDLOCK, HOLDLOCK) WHERE ReaderID = ?
            """, reader_id).fetchone()
            current = existing[0] if existing else None
            if current != expected:
                return JSONResponse({"error": "Your favourite changed. Refresh and try again."}, status_code=409)
            if favorite and current != book_id:
                ensure_reader_book(cursor, book_id, reader_id)
                cursor.execute("EXEC dbo.SetReaderFavoriteBook ?, ?", reader, book_id)
                current = book_id
            elif not favorite and current == book_id:
                cursor.execute("EXEC dbo.ClearReaderFavoriteBook ?", reader)
                current = None
            connection.commit()
            return JSONResponse({"favorite": current})
        saved = activity(cursor.execute(
            ACTIVITY_SQL + " WHERE BookID = ? AND ReaderName = ?", book_id, reader
        ).fetchone())
        connection.commit()
    return JSONResponse({"activity": saved})


def ensure_reader_book(cursor, book_id, reader_id):
    cursor.execute("""
        INSERT INTO dbo.reading_status (BookID, ReaderID, ReadingStatus)
        SELECT ?, ?, 'Unread' WHERE NOT EXISTS (
            SELECT 1 FROM dbo.reading_status WITH (UPDLOCK, HOLDLOCK) WHERE BookID = ? AND ReaderID = ?
        )
    """, book_id, reader_id, book_id, reader_id)


async def edit_reading(request):
    kind = request.path_params.get("kind", "history")
    if kind not in {"rating", "favorite", "history"} or (kind == "history" and "event_id" not in request.path_params):
        return JSONResponse({"error": "Reading action not found."}, status_code=404)
    return await mutation(request, lambda book_id, data: save_reading_edit(
        book_id, data, kind, request.path_params.get("event_id")
    ))


def save_comment(book_id, data):
    reader, text = data.get("reader"), data.get("text")
    if not isinstance(reader, str) or not reader.strip() or len(reader) > 255:
        raise ValueError("Choose a reader.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Write a comment before saving.")
    if len(text.encode("utf-16-le")) > 8000:
        raise ValueError("Keep the comment to 4,000 characters.")
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        if cursor.execute("SELECT 1 FROM dbo.books WHERE BookID = ?", book_id).fetchone() is None:
            return JSONResponse({"error": "Book not found."}, status_code=404)
        if cursor.execute("SELECT 1 FROM dbo.readers WHERE ReaderName = ?", reader).fetchone() is None:
            raise ValueError("Reader not found.")
        cursor.execute("EXEC dbo.AddReaderBookComment ?, ?, ?", book_id, reader, text.strip())
        saved = comments(cursor.execute(
            COMMENT_SQL + " WHERE BookID = ? ORDER BY DateAdded DESC, CommentID DESC", book_id
        ))
        connection.commit()
    return JSONResponse({"comments": saved}, status_code=201)


def book_position(raw, increment, limit, error):
    if not raw:
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite() or abs(value) > Decimal(limit) or value != value.quantize(Decimal(increment)):
            raise InvalidOperation
        return value
    except InvalidOperation:
        raise ValueError(error) from None


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
    number = book_position(data.get("number"), "0.1", "999.9",
                           "Enter a book number between -999.9 and 999.9 with up to one decimal place.")
    universe_order = book_position(data.get("universeOrder"), "0.01", "999.99",
                                   "Enter a universe position between -999.99 and 999.99 with up to two decimal places.")

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
        if data.keys() & {"title", "series", "number", "universeOrder", "description"}:
            cursor.execute(
                "EXEC dbo.UpdateBookCoreDetails ?, ?, ?, ?, ?, ?, ?, ?",
                book_id, data.get("title", current.Title), data.get("series", current.SeriesName or "Standalone"),
                number if "number" in data else current.BookNumber,
                universe_order if "universeOrder" in data else current.UniverseReadingOrder,
                current.LengthType, current.Demographic,
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
            SELECT Title, Authors, SeriesName, ParentSeriesName, BookNumber, UniverseReadingOrder
            FROM dbo.vw_book_details WHERE BookID = ?
        """, book_id).fetchone()
        payload = book_details(cursor, book_id)
        payload["book"] = {
            "title": row.Title, "author": row.Authors,
            "series": row.SeriesName if row.SeriesName != "Standalone" else None,
            "parentSeries": row.ParentSeriesName,
            "universeOrder": format(row.UniverseReadingOrder.normalize(), "f")
            if row.UniverseReadingOrder is not None else None,
            "number": str(row.BookNumber) if row.BookNumber is not None else "",
            "order": f"Book {row.BookNumber.normalize():f}" if row.BookNumber is not None else None,
            "authorCredits": [
                {"id": author_id, "name": name}
                for _, author_id, name in cursor.execute(
                    AUTHOR_CREDITS_SQL + " WHERE ba.BookID = ? ORDER BY ba.AuthorOrder, a.AuthorName", book_id
                )
            ],
        }
        connection.commit()
    return JSONResponse(payload)


async def update_status(request):
    return await mutation(request, save_status)


async def update_book(request):
    return await mutation(request, save_book)


async def add_comment(request):
    return await mutation(request, save_comment)


def cover_gallery(book_id):
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        if cursor.execute("SELECT 1 FROM dbo.books WHERE BookID = ?", book_id).fetchone() is None:
            return JSONResponse({"error": "Book not found."}, status_code=404)
        covers = [
            {"id": row.CoverID, "label": row.CoverLabel, "url": cover_url(row.ImageFilePath),
             "primary": bool(row.IsPrimary)}
            for row in cursor.execute("""
                SELECT CoverID, CoverLabel, ImageFilePath, IsPrimary
                FROM dbo.book_covers WHERE BookID = ?
                ORDER BY IsPrimary DESC, SortOrder, CoverID
            """, book_id)
        ]
    return JSONResponse({"covers": covers}, headers={"Cache-Control": "no-store"})


def book_covers(request):
    return cover_gallery(request.path_params["book_id"])


def store_cover(book_id, data, label, primary, notes=""):
    try:
        with Image.open(data, formats=["JPEG", "PNG", "WEBP", "AVIF"]) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Choose an image with at most 20 megapixels.")
        save_book_cover(book_id, data, cover_label=label, source_notes=notes,
                        make_primary=primary, deduplicate=True)
    except (OSError, Image.DecompressionBombError):
        raise ValueError("Choose a valid JPEG, PNG, WebP, or AVIF image.") from None
    return cover_gallery(book_id)


async def upload_cover(request):
    if not allowed_origin(request):
        return JSONResponse({"error": "Open The Listening Room directly to save changes."}, status_code=403)
    if request.headers.get("content-type", "").split(";")[0].strip().lower() not in COVER_IMAGE_TYPES:
        return JSONResponse({"error": "Choose a JPEG, PNG, WebP, or AVIF image."}, status_code=415)
    label = request.query_params.get("label", "").strip()
    notes = request.query_params.get("notes", "").strip()
    if len(label.encode("utf-16-le")) > 200:
        return JSONResponse({"error": "Keep the cover label to 100 characters."}, status_code=400)
    if len(notes.encode("utf-16-le")) > 1000:
        return JSONResponse({"error": "Keep cover source notes to 500 characters."}, status_code=400)
    with BytesIO() as data:
        async for chunk in request.stream():
            if data.tell() + len(chunk) > COVER_UPLOAD_LIMIT:
                return JSONResponse({"error": "Choose an image no larger than 8 MB."}, status_code=413)
            data.write(chunk)
        try:
            data.seek(0)
            return await run_in_threadpool(
                store_cover, request.path_params["book_id"], data, label,
                request.query_params.get("primary") == "true", notes,
            )
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=400)


def choose_primary_cover(book_id, data):
    cover_id = data.get("coverId")
    if type(cover_id) is not int or not 0 < cover_id <= 2_147_483_647:
        raise ValueError("Choose a cover.")
    set_primary_cover(cover_id, expected_book_id=book_id)
    return cover_gallery(book_id)


async def update_primary_cover(request):
    return await mutation(request, choose_primary_cover)


def remove_cover(book_id, data):
    cover_id = data.get("coverId")
    if type(cover_id) is not int or not 0 < cover_id <= 2_147_483_647:
        raise ValueError("Choose a cover.")
    delete_cover(cover_id, expected_book_id=book_id)
    return cover_gallery(book_id)


async def delete_book_cover(request):
    return await mutation(request, remove_cover)


def edition_fields(data):
    values = []
    for key in ("name", "publisher"):
        value = data.get(key, "")
        if not isinstance(value, str) or len(value.strip().encode("utf-16-le")) > 510:
            raise ValueError("Keep the edition name and publisher to 255 characters.")
        values.append(value.strip() or None)
    for key, minimum, label in (("year", 0, "Release year"), ("minutes", 1, "Runtime")):
        value = data.get(key)
        if value is not None and (type(value) is not int or not minimum <= value <= 2_147_483_647):
            raise ValueError(f"{label} must be a whole number of at least {minimum}.")
        values.append(value)
    for key in ("abridged", "fullCast"):
        value = data.get(key, False)
        if type(value) is not bool:
            raise ValueError("Choose valid edition flags.")
        values.append(value)
    notes, names = data.get("notes", ""), data.get("narrators", [])
    if not isinstance(notes, str) or not isinstance(names, list) or any(
        not isinstance(name, str) or len(name.strip().encode("utf-16-le")) > 510 for name in names
    ):
        raise ValueError("Use one narrator per line, up to 255 characters per name.")
    return (*values, notes.strip() or None), [name.strip() for name in names if name.strip()]


def insert_edition(cursor, book_id, fields, names):
    edition_id = cursor.execute("""
        INSERT INTO dbo.audiobook_versions
            (BookID, EditionName, Publisher, ReleaseYear, DurationMinutes, IsAbridged, IsFullCast, Notes)
        OUTPUT INSERTED.AudiobookVersionID
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, book_id, *fields).fetchone()[0]
    save_edition_narrators(cursor, edition_id, names)


def new_book_options(request):
    options = {}
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        for kind, value in cursor.execute("""
            SELECT 'series' AS Kind, SeriesName AS Value FROM dbo.series WHERE SeriesName <> 'Standalone'
            UNION SELECT 'author', AuthorName FROM dbo.authors_new
            UNION SELECT 'length', LengthType FROM dbo.books
            UNION SELECT 'demographic', Demographic FROM dbo.books
            UNION SELECT 'edition', EditionName FROM dbo.audiobook_versions
            UNION SELECT 'publisher', Publisher FROM dbo.audiobook_versions
            UNION SELECT bg.GenreType, g.GenreName
            FROM dbo.genres g JOIN dbo.book_genres bg ON bg.GenreID = g.GenreID
            ORDER BY Kind, Value
        """):
            if value:
                options.setdefault(kind, []).append(value)
    return JSONResponse(options, headers={"Cache-Control": "no-store"})


def create_book(_, data):
    values = {}
    for key, limit in (("title", 255), ("series", 255), ("length", 50), ("demographic", 50),
                       ("number", None), ("universeOrder", None), ("description", None),
                       ("author", None), ("genre", None), ("tags", None)):
        value = data.get(key, "")
        if not isinstance(value, str) or (limit and len(value.strip().encode("utf-16-le")) > limit * 2):
            raise ValueError(f"Enter a valid value for {key}.")
        values[key] = value.strip()
    if not values["title"] or not values["series"] or not any(part.strip() for part in values["author"].split(",")):
        raise ValueError("Enter a title, at least one author, and a series or Standalone.")
    for key in ("author", "genre", "tags"):
        if any(len(name.strip().encode("utf-16-le")) > 510 for name in values[key].split(",")):
            raise ValueError("Keep individual author, genre, and tag names to 255 characters.")
    standalone = values["series"].casefold() == "standalone"
    number = None if standalone else book_position(values["number"], "0.1", "999.9", "Enter a valid book number.")
    universe = None if standalone else book_position(values["universeOrder"], "0.01", "999.99", "Enter a valid universe reading order.")
    edition = data.get("edition")
    if not isinstance(edition, dict):
        raise ValueError("Include the audiobook edition.")
    fields, names = edition_fields(edition)
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("BEGIN TRANSACTION")
        book_id = cursor.execute(
            "EXEC dbo.AddBook ?, ?, ?, ?, ?, ?, ?, ?, ?",
            values["title"], values["author"], "Standalone" if standalone else values["series"], number,
            values["length"] or None, values["demographic"] or None, values["description"] or None,
            values["genre"] or None, values["tags"] or None,
        ).fetchone()[0]
        if universe is not None:
            cursor.execute("UPDATE dbo.books SET UniverseReadingOrder = ? WHERE BookID = ?", universe, book_id)
        insert_edition(cursor, book_id, fields, names)
        connection.commit()
    return JSONResponse({"bookId": book_id}, status_code=201)


async def add_book(request):
    return await mutation(request, create_book)


def save_edition(book_id, data, edition_id=None, delete=False):
    if not delete:
        fields, names = edition_fields(data)
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        if cursor.execute(
            "SELECT 1 FROM dbo.books WITH (UPDLOCK, HOLDLOCK) WHERE BookID = ?", book_id
        ).fetchone() is None:
            return JSONResponse({"error": "Book not found."}, status_code=404)
        if edition_id is not None and cursor.execute("""
            SELECT 1 FROM dbo.audiobook_versions WITH (UPDLOCK, HOLDLOCK)
            WHERE BookID = ? AND AudiobookVersionID = ?
        """, book_id, edition_id).fetchone() is None:
            return JSONResponse({"error": "Edition not found for this book."}, status_code=404)
        if delete:
            cursor.execute("EXEC dbo.DeleteAudiobookVersion ?", edition_id)
        else:
            if edition_id is None:
                insert_edition(cursor, book_id, fields, names)
            else:
                cursor.execute("""
                    UPDATE dbo.audiobook_versions
                    SET EditionName = ?, Publisher = ?, ReleaseYear = ?, DurationMinutes = ?,
                        IsAbridged = ?, IsFullCast = ?, Notes = ?
                    WHERE BookID = ? AND AudiobookVersionID = ?
                """, *fields, book_id, edition_id)
                save_edition_narrators(cursor, edition_id, names)
        editions = editions_for_book(cursor, book_id)
        connection.commit()
    return JSONResponse({"editions": editions})


def save_edition_narrators(cursor, edition_id, names):
    current = dict(cursor.execute("""
        SELECT NarratorID, NarratorRole FROM dbo.audiobook_version_narrators
        WHERE AudiobookVersionID = ? ORDER BY DisplayOrder, NarratorID
    """, edition_id).fetchall())
    credits = {}
    for name in names:
        row = cursor.execute("""
            SELECT NarratorID FROM dbo.narrators WITH (UPDLOCK, HOLDLOCK) WHERE NarratorName = ?
        """, name).fetchone()
        if row is None:
            row = cursor.execute("""
                INSERT INTO dbo.narrators (NarratorName) OUTPUT INSERTED.NarratorID VALUES (?)
            """, name).fetchone()
        credits[row[0]] = current.get(row[0])
    if list(credits) == list(current):
        return
    cursor.execute("DELETE FROM dbo.audiobook_version_narrators WHERE AudiobookVersionID = ?", edition_id)
    for order, (narrator_id, role) in enumerate(credits.items(), start=1):
        cursor.execute("""
            INSERT INTO dbo.audiobook_version_narrators
                (AudiobookVersionID, NarratorID, NarratorRole, DisplayOrder)
            VALUES (?, ?, ?, ?)
        """, edition_id, narrator_id, role, order)


async def write_book_edition(request):
    edition_id = request.path_params.get("edition_id")
    delete = request.method == "DELETE"
    return await mutation(request, lambda book_id, data: save_edition(book_id, data, edition_id, delete))


def library_stats(request):
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        summary = cursor.execute("""
            SELECT (SELECT COUNT(*) FROM dbo.books) AS Books, COUNT(*) AS Editions,
                   COALESCE(SUM(CAST(DurationMinutes AS BIGINT)), 0) AS Minutes,
                   COUNT(DurationMinutes) AS TimedEditions,
                   COUNT(CASE WHEN IsFullCast = 1 THEN 1 END) AS FullCast
            FROM dbo.audiobook_versions
        """).fetchone()
        genres = [{"name": row.GenreName, "count": row.BookCount} for row in cursor.execute("""
            SELECT TOP (8) g.GenreName, COUNT(DISTINCT bg.BookID) AS BookCount
            FROM dbo.book_genres bg JOIN dbo.genres g ON g.GenreID = bg.GenreID
            WHERE bg.GenreType = 'Main'
            GROUP BY g.GenreName ORDER BY BookCount DESC, g.GenreName
        """)]
        history = {}
        for row in cursor.execute("""
            SELECT r.ReaderName, YEAR(h.EffectiveDate) AS FinishYear,
                   MONTH(h.EffectiveDate) AS FinishMonth, COUNT(*) AS Finishes
            FROM dbo.reader_book_status_history h
            JOIN dbo.readers r ON r.ReaderID = h.ReaderID
            WHERE h.ToStatus = 'Read' AND h.EffectiveDate IS NOT NULL
            GROUP BY r.ReaderName, YEAR(h.EffectiveDate), MONTH(h.EffectiveDate)
        """):
            months = history.setdefault(row.ReaderName, {}).setdefault(row.FinishYear, [0] * 12)
            months[row.FinishMonth - 1] = row.Finishes
    return JSONResponse({
        "books": summary.Books, "editions": summary.Editions, "minutes": summary.Minutes,
        "timedEditions": summary.TimedEditions, "fullCast": summary.FullCast,
        "genres": genres, "history": history,
    }, headers={"Cache-Control": "no-store"})


def releases(request):
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        entries = [
            {
                "id": row.ReleaseID, "title": row.Title, "authors": row.Authors,
                "seriesId": row.SeriesID, "series": row.SeriesName, "universe": row.ParentSeriesName,
                "number": str(row.BookNumber) if row.BookNumber is not None else "",
                "date": row.ExpectedReleaseDate.isoformat() if row.ExpectedReleaseDate else None,
                "precision": row.ReleaseDatePrecision, "publisher": row.Publisher,
                "narrators": row.Narrators, "status": row.WatchStatus,
                "checked": row.LastChecked.isoformat() if row.LastChecked else None,
            }
            for row in cursor.execute("""
                SELECT ReleaseID, Title, Authors, SeriesID, SeriesName, ParentSeriesName, BookNumber,
                       ExpectedReleaseDate, ReleaseDatePrecision, Publisher, Narrators, WatchStatus, LastChecked
                FROM dbo.vw_upcoming_releases
                ORDER BY CASE WHEN ExpectedReleaseDate IS NULL THEN 1 ELSE 0 END, ExpectedReleaseDate, Title, ReleaseID
            """)
        ]
        series = [{"id": row.SeriesID, "name": row.SeriesName, "universe": row.ParentSeriesName}
                  for row in cursor.execute("""
                      SELECT s.SeriesID, s.SeriesName, p.SeriesName AS ParentSeriesName
                      FROM dbo.series s LEFT JOIN dbo.series p ON p.SeriesID = s.ParentSeriesID
                      WHERE s.SeriesName <> 'Standalone' ORDER BY s.SeriesName
                  """)]
    return JSONResponse({"releases": entries, "series": series}, headers={"Cache-Control": "no-store"})


def release_fields(data):
    fields = {}
    for key in ("title", "authors", "publisher", "narrators"):
        value = data.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"Enter a valid value for {key}.")
        fields[key] = value.strip() or None
    if not fields["title"] or any(
        fields[key] and len(fields[key].encode("utf-16-le")) > 510 for key in ("title", "publisher")
    ):
        raise ValueError("Enter a title and keep the title and publisher to 255 characters.")
    series_id, number = data.get("seriesId"), data.get("number", "")
    if series_id is not None and (type(series_id) is not int or not 0 < series_id <= 2_147_483_647):
        raise ValueError("Choose a valid series.")
    if not isinstance(number, str):
        raise ValueError("Enter a valid book number.")
    position = book_position(number, "0.1", "999.9", "Enter a valid book number.") if series_id else None
    precision = data.get("precision")
    patterns = {"Year": r"[0-9]{4}", "Month": r"[0-9]{4}-[0-9]{2}", "Exact": r"[0-9]{4}-[0-9]{2}-[0-9]{2}"}
    if not isinstance(precision, str) or precision not in (*patterns, "Unknown"):
        raise ValueError("Choose how precisely the release date is known.")
    expected = None
    if precision != "Unknown":
        raw = data.get("date")
        if not isinstance(raw, str) or not re.fullmatch(patterns[precision], raw):
            raise ValueError("Enter an expected release date that matches the selected precision.")
        try:
            expected = date.fromisoformat(raw + {"Year": "-01-01", "Month": "-01", "Exact": ""}[precision])
        except ValueError:
            raise ValueError("Enter a valid expected release date.") from None
    return (fields["title"], fields["authors"], series_id, position, expected, precision,
            fields["publisher"], fields["narrators"])


def save_release(release_id, data, delete=False):
    actions = {
        "checked": "UPDATE dbo.upcoming_releases SET LastChecked = SYSDATETIME() WHERE ReleaseID = ?",
        "released": "UPDATE dbo.upcoming_releases SET WatchStatus = 'Released', LastChecked = SYSDATETIME() WHERE ReleaseID = ? AND WatchStatus = 'Watching'",
        "watching": "UPDATE dbo.upcoming_releases SET WatchStatus = 'Watching' WHERE ReleaseID = ?",
    }
    action = data.get("action")
    with closing(get_connection()) as connection, closing(connection.cursor()) as cursor:
        if release_id is not None and cursor.execute("""
            SELECT 1 FROM dbo.upcoming_releases WITH (UPDLOCK, HOLDLOCK) WHERE ReleaseID = ?
        """, release_id).fetchone() is None:
            return JSONResponse({"error": "Release not found."}, status_code=404)
        if delete:
            cursor.execute("DELETE FROM dbo.upcoming_releases WHERE ReleaseID = ?", release_id)
        elif action is not None:
            if release_id is None or not isinstance(action, str) or action not in actions:
                raise ValueError("Choose a valid release action.")
            cursor.execute(actions[action], release_id)
        else:
            fields = release_fields(data)
            if fields[2] is not None and cursor.execute(
                "SELECT 1 FROM dbo.series WHERE SeriesID = ?", fields[2]
            ).fetchone() is None:
                raise ValueError("That series is no longer available.")
            if release_id is None:
                cursor.execute("""
                    INSERT INTO dbo.upcoming_releases
                        (Title, Authors, SeriesID, BookNumber, ExpectedReleaseDate, ReleaseDatePrecision, Publisher, Narrators)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, *fields)
            else:
                cursor.execute("""
                    UPDATE dbo.upcoming_releases SET Title = ?, Authors = ?, SeriesID = ?, BookNumber = ?,
                        ExpectedReleaseDate = ?, ReleaseDatePrecision = ?, Publisher = ?, Narrators = ?
                    WHERE ReleaseID = ?
                """, *fields, release_id)
        connection.commit()
    return JSONResponse({"saved": True}, status_code=201 if release_id is None else 200)


async def write_release(request):
    return await mutation(request, lambda release_id, data: save_release(release_id, data, request.method == "DELETE"))


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
    return FileResponse(PREVIEW / "index.html", headers={"Cache-Control": "no-cache"})


def static_file(request):
    name = request.path_params["name"]
    if name not in {"app.js", "books.js", "styles.css", "releases.js", "stats.js"}:
        return Response(status_code=404)
    return FileResponse(PREVIEW / name, headers={"Cache-Control": "no-cache"})


async def api_error(request, error):
    LOGGER.error("Library API %s failed (%s): %s", request.url.path, type(error).__name__, error)
    message = "The live library could not be loaded."
    if request.method in {"PATCH", "POST", "DELETE"}:
        message = "The database could not confirm this save. Refresh to check the current values."
    if "Another book already exists with this title, series, and book number." in str(error):
        return JSONResponse({"error": "Another book already uses that title, series, and book number."}, status_code=409)
    if "This book already appears to be in the database." in str(error):
        return JSONResponse({"error": "A book with that title, series, and book number already exists."}, status_code=409)
    return JSONResponse({"error": message}, status_code=503)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/index.html", index),
        Route("/api/library", catalog),
        Route("/api/stats", library_stats),
        Route("/api/releases", releases),
        Route("/api/releases", write_release, methods=["POST"]),
        Route("/api/releases/{release_id:int}", write_release, methods=["PATCH", "DELETE"]),
        Route("/api/books/options", new_book_options),
        Route("/api/books", add_book, methods=["POST"]),
        Route("/api/reader-comments", reader_comments),
        Route("/api/narrator-credits", narrator_credits),
        Route("/api/books/{book_id:int}", details),
        Route("/api/books/{book_id:int}", update_book, methods=["PATCH"]),
        Route("/api/books/{book_id:int}/status", update_status, methods=["PATCH"]),
        Route("/api/books/{book_id:int}/history", reading_history),
        Route("/api/books/{book_id:int}/history/{event_id:int}", edit_reading, methods=["PATCH"]),
        Route("/api/books/{book_id:int}/reading/{kind}", edit_reading, methods=["PATCH"]),
        Route("/api/books/{book_id:int}/comments", add_comment, methods=["POST"]),
        Route("/api/books/{book_id:int}/covers", book_covers),
        Route("/api/books/{book_id:int}/covers", upload_cover, methods=["POST"]),
        Route("/api/books/{book_id:int}/covers", delete_book_cover, methods=["DELETE"]),
        Route("/api/books/{book_id:int}/covers/primary", update_primary_cover, methods=["PATCH"]),
        Route("/api/books/{book_id:int}/editions", write_book_edition, methods=["POST"]),
        Route("/api/books/{book_id:int}/editions/{edition_id:int}", write_book_edition, methods=["PATCH", "DELETE"]),
        Route("/assets/{path:path}", cover_image),
        Route("/{name}", static_file),
    ],
    middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)],
    exception_handlers={Exception: api_error},
)

