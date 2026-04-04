USE Audiobooks;
GO

-- Total books read by reader
SELECT
    ReaderName,
    COUNT(*) AS TotalBooksRead
FROM vw_reader_books
WHERE ReadingStatus = 'Read'
GROUP BY ReaderName
ORDER BY TotalBooksRead DESC;
GO

-- How many books two readers share in common
DECLARE @Reader1ID INT = 1; -- UserID of Reader 1
DECLARE @Reader2ID INT = 2; -- UserID of Reader 2

SELECT 
    rd1.ReaderName AS Reader1,
    rd2.ReaderName AS Reader2,
    COUNT(*) AS BooksReadInCommon
FROM reading_status r1
JOIN reading_status r2
    ON r1.BookID = r2.BookID
JOIN readers rd1
    ON rd1.ReaderID = r1.ReaderID
JOIN readers rd2
    ON rd2.ReaderID = r2.ReaderID
WHERE r1.ReaderID = @Reader1ID
  AND r2.ReaderID = @Reader2ID
  AND r1.ReadingStatus = 'Read'
  AND r2.ReadingStatus = 'Read'
GROUP BY rd1.ReaderName, rd2.ReaderName;
GO

-- Average rating by reader, including number of rated books
SELECT
    ReaderName,
    CAST(AVG(Rating) AS DECIMAL(4,2)) AS AverageRating,
    COUNT(Rating) AS NumberOfRatedBooks
FROM vw_reader_books
WHERE ReadingStatus = 'Read'
  AND Rating IS NOT NULL
GROUP BY ReaderName
ORDER BY AverageRating DESC;
GO

-- Most read main genres
SELECT
    g.GenreName, 
    COUNT(*) AS NumReads
FROM book_genres bg
JOIN genres g
    ON bg.GenreID = g.GenreID
JOIN reading_status rs
    ON rs.BookID = bg.BookID
WHERE rs.ReadingStatus = 'Read'
    AND bg.GenreType = 'Main'
GROUP BY g.GenreName
ORDER BY NumReads DESC;
GO

-- Most read secondary genres
SELECT
    g.GenreName, 
    COUNT(*) AS NumReads
FROM book_genres bg
JOIN genres g
    ON bg.GenreID = g.GenreID
JOIN reading_status rs
    ON rs.BookID = bg.BookID
WHERE rs.ReadingStatus = 'Read'
    AND bg.GenreType = 'Secondary'
GROUP BY g.GenreName
ORDER BY NumReads DESC;
GO

-- Count of books by demographic
SELECT 
    b.Demographic, 
    COUNT(*) AS NumBooks
FROM books b
GROUP BY b.Demographic
ORDER BY NumBooks DESC;
GO

-- Count of books per series
SELECT
    s.SeriesName,
    COUNT(b.BookID) AS NumBooks
FROM series s
JOIN books b
    ON b.SeriesID = s.SeriesID
WHERE s.SeriesName <> 'Standalone' -- Not including standalone books
GROUP BY s.SeriesName
ORDER BY s.SeriesName;
GO

-- Count of books that are not a part of a series (standalone)
SELECT
    s.SeriesName,
    COUNT(b.BookID) AS NumBooks
FROM series s
JOIN books b
    ON b.SeriesID = s.SeriesID
WHERE s.SeriesName = 'Standalone'
GROUP BY s.SeriesName
ORDER BY s.SeriesName;
GO

-- Highest rated books by average rating
WITH BookRatings AS (
    SELECT
        BookID,
        CAST(AVG(Rating) AS DECIMAL(4,2)) AS AverageRating,
        COUNT(Rating) AS NumRatings
    FROM reading_status
    WHERE Rating IS NOT NULL
    GROUP BY BookID
)
SELECT
    bd.BookID,
    bd.Title,
    bd.Authors,
    br.AverageRating,
    br.NumRatings
FROM vw_book_details bd
JOIN BookRatings br
    ON bd.BookID = br.BookID
ORDER BY br.AverageRating DESC, br.NumRatings DESC, bd.Title;
GO

-- Count of books by length type
SELECT
    LengthType,
    COUNT(*) AS NumBooks
FROM books
GROUP BY LengthType
ORDER BY NumBooks DESC;
GO

-- Tori's highest rated books
SELECT TOP 50
    BookID,
    Title,
    Authors,
    Rating
FROM vw_tori_read_books
WHERE Rating IS NOT NULL
ORDER BY Rating DESC, Title;
GO


-- Angela's highest rated books
SELECT TOP 50
    BookID,
    Title,
    Authors,
    Rating
FROM vw_angela_read_books
WHERE Rating IS NOT NULL
ORDER BY Rating DESC, Title;
GO

-- Mini book workflow
SELECT *
FROM vw_reader_mini_books_dashboard
ORDER BY ReaderName, MiniBookStage, Authors, SeriesName, BookNumber, Title;


-- Mini books by status & reader
SELECT *
FROM vw_reader_mini_books_dashboard_summary
ORDER BY ReaderName, MiniBookStage;
