USE Audiobooks;
GO

-- See all books with author, title, series and book number
SELECT
    Authors,
    Title,
    SeriesName,
    BookNumber
FROM vw_book_details
ORDER BY Authors, SeriesName, BookNumber;
GO



-- See all books that Angela has read, including Angela's rating
SELECT
    Authors,
    Title,
    SeriesName,
    BookNumber,
    Rating
FROM vw_angela_read_books
ORDER BY Authors, SeriesName, BookNumber;
GO


-- See all books that Tori has read, including Tori's rating
SELECT
    Authors,
    Title,
    SeriesName,
    BookNumber,
    Rating
FROM vw_tori_read_books
ORDER BY Authors, SeriesName, BookNumber;
GO

-- See all unread books by reader
SELECT
    bd.Authors,
    rb.Title,
    bd.SeriesName,
    bd.BookNumber,
    rb.ReaderName
FROM vw_reader_books rb
JOIN vw_book_details bd
    ON rb.BookID = bd.BookID
WHERE rb.ReadingStatus = 'Unread'
ORDER BY rb.ReaderName, bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- See all to be read (TBR) books by reader
SELECT
    bd.Authors,
    rb.Title,
    bd.SeriesName,
    bd.BookNumber,
    rb.ReaderName
FROM vw_reader_books rb
JOIN vw_book_details bd
    ON rb.BookID = bd.BookID
WHERE rb.ReadingStatus = 'TBR'
ORDER BY rb.ReaderName, bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- See all currently reading books by reader
SELECT
    bd.Authors,
    rb.Title,
    bd.SeriesName,
    bd.BookNumber,
    rb.ReaderName
FROM vw_reader_books rb
JOIN vw_book_details bd
    ON rb.BookID = bd.BookID
WHERE rb.ReadingStatus = 'Reading'
ORDER BY rb.ReaderName, bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- See all did not finish (DNF) books by reader
SELECT
    bd.Authors,
    rb.Title,
    bd.SeriesName,
    bd.BookNumber,
    rb.ReaderName
FROM vw_reader_books rb
JOIN vw_book_details bd
    ON rb.BookID = bd.BookID
WHERE rb.ReadingStatus = 'DNF'
ORDER BY rb.ReaderName, bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- Find books in a certain genre
SELECT
    bd.BookID,
    bd.Authors,
    bd.Title,
    bd.SeriesName,
    bd.BookNumber,
    STRING_AGG(CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END, ', ') AS MainGenre,
    STRING_AGG(CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END, ', ') AS SecondaryGenres
FROM vw_book_details bd
JOIN book_genres bg
    ON bg.BookID = bd.BookID
JOIN genres g
    ON g.GenreID = bg.GenreID
WHERE EXISTS (
    SELECT 1
    FROM book_genres bg2
    JOIN genres g2
        ON g2.GenreID = bg2.GenreID
    WHERE bg2.BookID = bd.BookID
      AND g2.GenreName LIKE N'%Retelling%' -- Change search term here
)
GROUP BY bd.BookID, bd.Authors, bd.Title, bd.SeriesName, bd.BookNumber
ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- See all books in a specific series
SELECT 
	STRING_AGG(a.AuthorName, ', ') AS Authors,
	b.Title, 
	s.SeriesName, 
	b.BookNumber
FROM books b
JOIN book_authors ba ON b.BookID = ba.BookID
JOIN authors_new a ON ba.AuthorID = a.AuthorID
JOIN series s ON b.SeriesID = s.SeriesID
WHERE s.SeriesName LIKE N'%Atlas%' -- Change search term here
GROUP BY b.BookID, b.Title, s.SeriesName, b.BookNumber
ORDER BY Authors, s.SeriesName, b.BookNumber;
GO


-- Look up books by title, including genre information
SELECT
    bd.BookID,
    bd.Authors,
    bd.Title,
    bd.SeriesName,
    bd.BookNumber,
    STRING_AGG(CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END, ', ') AS MainGenre,
    STRING_AGG(CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END, ', ') AS SecondaryGenres
FROM vw_book_details bd
JOIN book_genres bg
    ON bg.BookID = bd.BookID
JOIN genres g
    ON g.GenreID = bg.GenreID
WHERE bd.Title LIKE N'%Coraline%' -- Change search term here
GROUP BY bd.BookID, bd.Authors, bd.Title, bd.SeriesName, bd.BookNumber
ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- Look up books by author, including genre information
SELECT
    bd.BookID,
    bd.Authors,
    bd.Title,
    bd.SeriesName,
    bd.BookNumber,
    STRING_AGG(CASE WHEN bg.GenreType = 'Main' THEN g.GenreName END, ', ') AS MainGenre,
    STRING_AGG(CASE WHEN bg.GenreType = 'Secondary' THEN g.GenreName END, ', ') AS SecondaryGenres
FROM vw_book_details bd
JOIN book_genres bg
    ON bg.BookID = bd.BookID
JOIN genres g
    ON g.GenreID = bg.GenreID
WHERE bd.Authors LIKE N'%Lemony%' -- Change search term here
GROUP BY bd.BookID, bd.Authors, bd.Title, bd.SeriesName, bd.BookNumber
ORDER BY bd.Authors, bd.SeriesName, bd.BookNumber;
GO

-- View all book club months and their respective books, including title and author name
SELECT
    ClubID,
    ClubMonth,
    FlyerTheme,
    DisplayOrder,
    BookID,
    Title,
    Authors
FROM vw_bookclub_books
ORDER BY ClubID, ClubMonth, DisplayOrder, BookID, Title;
GO

-- View all books selected for a given book club month
SELECT
    BookID,
    Title,
    Authors
FROM vw_bookclub_books
WHERE ClubMonth = N'June 2024' -- Change month here
ORDER BY DisplayOrder;
GO


