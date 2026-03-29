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
    b.UniverseReadingOrder
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
    b.UniverseReadingOrder;
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
    c.FlyerTheme,
	bcm.DisplayOrder,
	b.BookID,
    b.Title,
    STRING_AGG(a.AuthorName, ', ') AS Authors
FROM cozy_corner_book_club c
JOIN bookclub_monthly_books bcm 
    ON c.ClubID = bcm.ClubID
JOIN books b 
    ON b.BookID = bcm.BookID
JOIN book_authors ba 
    ON b.BookID = ba.BookID
JOIN authors_new a 
    ON ba.AuthorID = a.AuthorID
GROUP BY c.ClubID, c.ClubMonth, c.FlyerTheme, bcm.DisplayOrder, b.BookID, b.Title;
GO























