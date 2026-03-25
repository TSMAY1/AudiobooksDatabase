USE Audiobooks;
GO

-- Count how often secondary genres appear in the database, ordered by most common to least common
SELECT genres.GenreName, COUNT(*) AS GenreCount
FROM book_genres
JOIN genres ON book_genres.GenreID = genres.GenreID
WHERE book_genres.GenreType = 'Secondary'
GROUP BY genres.GenreName
ORDER BY GenreCount DESC;

-- Noticed one book had Romantasy as a secondary genre, but I don't think Romantasy should be considered a secondary genre for any book, so I want to find out which book it is and remove that secondary genre from the database
Select genres.GenreName, book_genres.BookID
FROM book_genres
JOIN genres ON book_genres.GenreID = genres.GenreID
WHERE GenreName = 'Romantasy' AND GenreType = 'Secondary';
GO

-- Find the title, author, series, and genre of the book that has Romantasy as a secondary genre
SELECT books.Title, authors.AuthorName, series.SeriesName, genres.GenreName
FROM books
JOIN authors ON books.AuthorID = authors.AuthorID
JOIN series ON books.SeriesID = series.SeriesID
JOIN book_genres ON books.BookID = book_genres.BookID
JOIN genres ON book_genres.GenreID = genres.GenreID
WHERE genres.GenreName = 'Romantasy' AND book_genres.GenreType = 'Secondary';
GO

-- I confirmed it was "Can't Spell Treason Without Tea", but it should not be considered a secondary Romantasy book, so I will delete that secondary genre from the database. 
-- I will wrap this in a transaction in case there are any issues with the delete statement, and I will print an error message if there is an issue and roll back the transaction.
BEGIN TRANSACTION;
BEGIN TRY
DELETE FROM book_genres
WHERE GenreID IN (SELECT GenreID FROM genres WHERE GenreName = 'Romantasy') AND GenreType = 'Secondary';
END TRY
BEGIN CATCH
ROLLBACK TRANSACTION;
PRINT 'Error occurred while deleting secondary Romantasy genres. Transaction rolled back.';
END CATCH
GO
