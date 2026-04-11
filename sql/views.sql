-- Read books per user

CREATE OR ALTER VIEW vw_angela_read_books AS

SELECT 
	b.BookID,
	b.Title, 
	STRING_AGG(a.AuthorName, ', ') AS Authors, 
	s.SeriesName, 
	b.BookNumber, 
	rs.Rating
FROM reading_status rs
JOIN books b ON rs.BookID = b.BookID
JOIN book_authors ba ON b.BookID = ba.BookID
JOIN authors_new a ON ba.AuthorID = a.AuthorID
JOIN series s ON b.SeriesID = s.SeriesID
WHERE rs.ReadingStatus = 'Read' 
	AND rs.ReaderID = 1
GROUP BY b.BookID, b.Title, s.SeriesName, b.BookNumber, rs.Rating;
GO

CREATE OR ALTER VIEW vw_tori_read_books AS

SELECT 
	b.BookID,
	b.Title, 
	STRING_AGG(a.AuthorName, ', ') AS Authors, 
	s.SeriesName, 
	b.BookNumber, 
	rs.Rating
FROM reading_status rs
JOIN books b 
	ON rs.BookID = b.BookID
JOIN book_authors ba 
	ON b.BookID = ba.BookID
JOIN authors_new a 
	ON ba.AuthorID = a.AuthorID
JOIN series s 
	ON b.SeriesID = s.SeriesID
WHERE rs.ReadingStatus = 'Read'
	AND rs.ReaderID = 2
GROUP BY b.BookID, b.Title, s.SeriesName, b.BookNumber, rs.Rating;
GO


-- Book details view

CREATE OR ALTER VIEW vw_book_details AS

SELECT
    b.BookID,
    STRING_AGG(a.AuthorName, ', ') AS Authors,
    b.Title,
    s.SeriesID,
    s.SeriesName,
    p.SeriesName AS ParentSeriesName,
    COALESCE(p.SeriesName, s.SeriesName) AS UniverseName,
    b.BookNumber,
    b.UniverseReadingOrder,
    b.Full_Cast
FROM books b
JOIN book_authors ba
    ON ba.BookID = b.BookID
JOIN authors_new a
    ON a.AuthorID = ba.AuthorID
JOIN series s
    ON s.SeriesID = b.SeriesID
LEFT JOIN series p
    ON p.SeriesID = s.ParentSeriesID
GROUP BY
    b.BookID,
    b.Title,
    s.SeriesID,
    s.SeriesName,
    p.SeriesName,
    b.BookNumber,
    b.UniverseReadingOrder,
    b.Full_Cast;
GO

-- Reader activity view

CREATE OR ALTER VIEW vw_reader_books AS

SELECT 
	b.BookID,
	r.ReaderName, 
	b.Title, 
	rs.ReadingStatus, 
	rs.Rating
FROM reading_status rs
JOIN books b
	ON b.BookID = rs.BookID
JOIN readers r
	ON r.ReaderID = rs.ReaderID;
GO

-- book club view

CREATE OR ALTER VIEW vw_bookclub_books AS
SELECT 
    c.ClubID,
    c.ClubMonth,
    c.YearNum,
    c.MonthNum,
    c.FlyerTheme,
    c.FlyerFilePath,
    cal.CalendarFilePath,
    bcm.DisplayOrder,
    b.BookID,
    b.Title,
    STRING_AGG(a.AuthorName, ', ') WITHIN GROUP (ORDER BY ba.AuthorOrder, a.AuthorName) AS Authors
FROM cozy_corner_book_club c
JOIN bookclub_monthly_books bcm 
    ON c.ClubID = bcm.ClubID
JOIN books b 
    ON b.BookID = bcm.BookID
JOIN book_authors ba 
    ON b.BookID = ba.BookID
JOIN authors_new a 
    ON ba.AuthorID = a.AuthorID
LEFT JOIN bookclub_calendars cal
    ON c.YearNum = cal.YearNum
GROUP BY 
    c.ClubID,
    c.ClubMonth,
    c.YearNum,
    c.MonthNum,
    c.FlyerTheme,
    c.FlyerFilePath,
    cal.CalendarFilePath,
    bcm.DisplayOrder,
    b.BookID,
    b.Title;
GO

-- View what mini books need to be printed for each reader

CREATE OR ALTER VIEW vw_reader_mini_books_to_print AS
SELECT
    r.ReaderID,
    r.ReaderName,
    b.BookID,
    bd.Authors,
    b.Title,
    bd.SeriesName,
    bd.BookNumber,
    rs.ReadingStatus,
    ISNULL(mbs.IsPrinted, 0) AS IsPrinted,
    ISNULL(mbs.IsCrafted, 0) AS IsCrafted
FROM reading_status rs
JOIN readers r
    ON r.ReaderID = rs.ReaderID
JOIN books b
    ON b.BookID = rs.BookID
JOIN vw_book_details bd
    ON bd.BookID = b.BookID
LEFT JOIN mini_book_status mbs
    ON mbs.ReaderID = rs.ReaderID
   AND mbs.BookID = rs.BookID
WHERE rs.ReadingStatus = 'Read'
  AND (
        mbs.BookID IS NULL
        OR mbs.IsPrinted = 0
      );
GO

-- View what mini books have been printed, but not yet crafted, for each reader

CREATE OR ALTER VIEW vw_reader_mini_books_printed_not_crafted AS
SELECT
    r.ReaderID,
    r.ReaderName,
    b.BookID,
    bd.Authors,
    b.Title,
    bd.SeriesName,
    bd.BookNumber,
    rs.ReadingStatus,
    mbs.IsPrinted,
    mbs.IsCrafted
FROM mini_book_status mbs
JOIN readers r
    ON r.ReaderID = mbs.ReaderID
JOIN books b
    ON b.BookID = mbs.BookID
JOIN vw_book_details bd
    ON bd.BookID = b.BookID
LEFT JOIN reading_status rs
    ON rs.ReaderID = mbs.ReaderID
   AND rs.BookID = mbs.BookID
WHERE mbs.IsPrinted = 1
  AND mbs.IsCrafted = 0;
GO

-- Completed mini books view

CREATE OR ALTER VIEW vw_reader_mini_books_crafted_complete AS
SELECT
    r.ReaderID,
    r.ReaderName,
    b.BookID,
    bd.Authors,
    b.Title,
    bd.SeriesName,
    bd.BookNumber,
    rs.ReadingStatus,
    mbs.IsPrinted,
    mbs.IsCrafted
FROM mini_book_status mbs
JOIN readers r
    ON r.ReaderID = mbs.ReaderID
JOIN books b
    ON b.BookID = mbs.BookID
JOIN vw_book_details bd
    ON bd.BookID = b.BookID
LEFT JOIN reading_status rs
    ON rs.ReaderID = mbs.ReaderID
   AND rs.BookID = mbs.BookID
WHERE mbs.IsPrinted = 1
  AND mbs.IsCrafted = 1;
GO

-- mini books dashboard view with buckets

CREATE OR ALTER VIEW vw_reader_mini_books_dashboard AS
SELECT
    r.ReaderID,
    r.ReaderName,
    b.BookID,
    bd.Authors,
    b.Title,
    bd.SeriesName,
    bd.BookNumber,
    rs.ReadingStatus,
    ISNULL(mbs.IsPrinted, 0) AS IsPrinted,
    ISNULL(mbs.IsCrafted, 0) AS IsCrafted,
    CASE
        WHEN rs.ReadingStatus = 'Read'
             AND (mbs.BookID IS NULL OR ISNULL(mbs.IsPrinted, 0) = 0)
            THEN 'To Print'
        WHEN ISNULL(mbs.IsPrinted, 0) = 1
             AND ISNULL(mbs.IsCrafted, 0) = 0
            THEN 'Printed Not Crafted'
        WHEN ISNULL(mbs.IsPrinted, 0) = 1
             AND ISNULL(mbs.IsCrafted, 0) = 1
            THEN 'Completed'
        ELSE NULL
    END AS MiniBookStage
FROM reading_status rs
JOIN readers r
    ON r.ReaderID = rs.ReaderID
JOIN books b
    ON b.BookID = rs.BookID
JOIN vw_book_details bd
    ON bd.BookID = b.BookID
LEFT JOIN mini_book_status mbs
    ON mbs.ReaderID = rs.ReaderID
   AND mbs.BookID = rs.BookID
WHERE
    (
        rs.ReadingStatus = 'Read'
        AND (mbs.BookID IS NULL OR ISNULL(mbs.IsPrinted, 0) = 0)
    )
    OR (
        ISNULL(mbs.IsPrinted, 0) = 1
        AND ISNULL(mbs.IsCrafted, 0) = 0
    )
    OR (
        ISNULL(mbs.IsPrinted, 0) = 1
        AND ISNULL(mbs.IsCrafted, 0) = 1
    );
GO

-- mini books dashboard summary with counts

CREATE OR ALTER VIEW vw_reader_mini_books_dashboard_summary AS
SELECT
    ReaderName,
    MiniBookStage,
    COUNT(*) AS BookCount
FROM vw_reader_mini_books_dashboard
GROUP BY ReaderName, MiniBookStage;
GO

-- primary book covers view

CREATE OR ALTER VIEW vw_book_primary_cover AS
SELECT
    bc.BookID,
    bc.CoverID,
    bc.CoverLabel,
    bc.ImageFilePath,
    bc.ImageFormat,
    bc.WidthPx,
    bc.HeightPx,
    bc.FileSizeKB,
    bc.ImageHash,
    bc.SortOrder,
    bc.DateAdded
FROM book_covers bc
WHERE bc.IsPrimary = 1;
GO

-- all cover options view

CREATE OR ALTER VIEW vw_book_covers AS
SELECT
    bc.CoverID,
    bc.BookID,
    b.Title,
    bc.CoverLabel,
    bc.ImageFilePath,
    bc.ImageFormat,
    bc.WidthPx,
    bc.HeightPx,
    bc.FileSizeKB,
    bc.ImageHash,
    bc.SortOrder,
    bc.IsPrimary,
    bc.SourceNotes,
    bc.DateAdded
FROM book_covers bc
JOIN books b
    ON b.BookID = bc.BookID;
GO


