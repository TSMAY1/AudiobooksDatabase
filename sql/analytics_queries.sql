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


-- Total owned audiobook hours
SELECT
    SUM(DurationMinutes) AS TotalMinutes,
    CAST(SUM(DurationMinutes) / 60.0 AS DECIMAL(10,2)) AS TotalHours
FROM audiobook_versions
WHERE DurationMinutes IS NOT NULL;
GO


-- Average audiobook length
SELECT
    COUNT(*) AS AudiobookVersionsWithDuration,
    CAST(AVG(DurationMinutes) AS DECIMAL(10,2)) AS AverageMinutes,
    CAST(AVG(DurationMinutes) / 60.0 AS DECIMAL(10,2)) AS AverageHours
FROM audiobook_versions
WHERE DurationMinutes IS NOT NULL;
GO


-- Longest audiobooks
SELECT TOP 25
    avd.Title,
    avd.Narrators,
    avd.Publisher,
    avd.ReleaseYear,
    avd.DurationMinutes,
    avd.DurationDisplay
FROM vw_audiobook_version_details avd
WHERE avd.DurationMinutes IS NOT NULL
ORDER BY avd.DurationMinutes DESC;
GO


-- Shortest audiobooks
SELECT TOP 25
    avd.Title,
    avd.Narrators,
    avd.Publisher,
    avd.ReleaseYear,
    avd.DurationMinutes,
    avd.DurationDisplay
FROM vw_audiobook_version_details avd
WHERE avd.DurationMinutes IS NOT NULL
ORDER BY avd.DurationMinutes ASC;
GO


-- Narrator frequency rankings
SELECT
    n.NarratorName,
    COUNT(DISTINCT avn.AudiobookVersionID) AS AudiobookVersionCount,
    COUNT(DISTINCT av.BookID) AS BookCount,
    SUM(av.DurationMinutes) AS TotalNarratedMinutes,
    CAST(SUM(av.DurationMinutes) / 60.0 AS DECIMAL(10,2)) AS TotalNarratedHours
FROM narrators n
JOIN audiobook_version_narrators avn
    ON avn.NarratorID = n.NarratorID
JOIN audiobook_versions av
    ON av.AudiobookVersionID = avn.AudiobookVersionID
GROUP BY n.NarratorName
ORDER BY AudiobookVersionCount DESC, n.NarratorName;
GO


-- Average series length
-- Excludes Standalone
WITH SeriesCounts AS (
    SELECT
        s.SeriesID,
        s.SeriesName,
        COUNT(b.BookID) AS BookCount
    FROM series s
    JOIN books b
        ON b.SeriesID = s.SeriesID
    WHERE s.SeriesName <> 'Standalone'
    GROUP BY s.SeriesID, s.SeriesName
)
SELECT
    COUNT(*) AS SeriesCount,
    CAST(AVG(BookCount * 1.0) AS DECIMAL(10,2)) AS AverageBooksPerSeries,
    MIN(BookCount) AS ShortestSeriesLength,
    MAX(BookCount) AS LongestSeriesLength
FROM SeriesCounts;
GO


-- Full-cast vs single/multi narrator ratios
WITH VersionNarratorCounts AS (
    SELECT
        av.AudiobookVersionID,
        av.IsFullCast,
        COUNT(avn.NarratorID) AS NarratorCount
    FROM audiobook_versions av
    LEFT JOIN audiobook_version_narrators avn
        ON avn.AudiobookVersionID = av.AudiobookVersionID
    GROUP BY av.AudiobookVersionID, av.IsFullCast
)
SELECT
    CASE
        WHEN IsFullCast = 1 THEN 'Full Cast'
        WHEN NarratorCount = 1 THEN 'Single Narrator'
        WHEN NarratorCount > 1 THEN 'Multiple Narrators'
        ELSE 'No Narrator Listed'
    END AS NarrationType,
    COUNT(*) AS VersionCount,
    CAST(
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()
        AS DECIMAL(5,2)
    ) AS PercentOfCollection
FROM VersionNarratorCounts
GROUP BY
    CASE
        WHEN IsFullCast = 1 THEN 'Full Cast'
        WHEN NarratorCount = 1 THEN 'Single Narrator'
        WHEN NarratorCount > 1 THEN 'Multiple Narrators'
        ELSE 'No Narrator Listed'
    END
ORDER BY VersionCount DESC;
GO


-- Yearly audiobook publication trends
SELECT
    ReleaseYear,
    COUNT(*) AS AudiobookVersionCount,
    COUNT(DISTINCT BookID) AS UniqueBookCount,
    SUM(DurationMinutes) AS TotalMinutes,
    CAST(SUM(DurationMinutes) / 60.0 AS DECIMAL(10,2)) AS TotalHours
FROM audiobook_versions
WHERE ReleaseYear IS NOT NULL
GROUP BY ReleaseYear
ORDER BY ReleaseYear;
GO