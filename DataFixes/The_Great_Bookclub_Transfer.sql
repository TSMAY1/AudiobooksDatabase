USE Audiobooks;
GO

SELECT * 
FROM dbo.bookclub_calendars
ORDER BY bookclub_calendars.YearNum DESC;
GO

-- I need to input the BookID for each book in the bookclub_monthly_books table, but I don't have the BookIDs memorized, so I will run a query to find the BookIDs for each book in the database.
SELECT books.BookID, books.Title, authors.AuthorName, series.SeriesName
FROM books
JOIN authors ON books.AuthorID = authors.AuthorID
JOIN series ON books.SeriesID = series.SeriesID
ORDER BY books.BookID;
GO

-- Let's find out the format of monthly books in the Audiobooks_raw table to help me determine the BookIDs for the bookclub_monthly_books table. I will look for the book titles in the raw table and then find their corresponding BookIDs in the books table.
SELECT DISTINCT Book_Title, Cozy_Corner_Book_Club
FROM dbo.Audiobooks_raw
WHERE Cozy_Corner_Book_Club IS NOT NULL
ORDER BY Cozy_Corner_Book_Club DESC;
GO

-- I need to solve a problem
-- The dates in the Cozy_Corner_Book_Club column of the Audiobooks_raw table are incorrect, due to a formatting issue during the import process.
-- I will run a query to find the incorrect dates and determine the correct dates for each book in the Cozy Corner Book Club, so I can update the bookclub_monthly_books table with the correct dates.
SELECT DISTINCT Cozy_Corner_Book_Club
FROM dbo.Audiobooks_raw
WHERE Cozy_Corner_Book_Club IS NOT NULL
ORDER BY Cozy_Corner_Book_Club DESC;
GO

-- I know that 'One Last Stop' is a book in March 2024, and the date for that book is listed as 2020-03-24, so that's a start.
-- To avoid altering the data in the Audiobooks_raw table, I will create a temporary table to store the incorrect dates and their corresponding correct dates, so I can use that temporary table to update the bookclub_monthly_books table with the correct books.
-- The new format for the months is NVARCHAR(50) and will be in the format of 'Month Year', for example 'March 2024'.
CREATE TABLE #DateCorrections (
	IncorrectDate DATE,
	CorrectMonthYear NVARCHAR(50)
);
GO

-- Let's add in March 2024 for 'One Last Stop' first, and then I will add in the other months as I determine the correct dates for each book in the Cozy Corner Book Club.
INSERT INTO #DateCorrections (IncorrectDate, CorrectMonthYear)
VALUES ('2020-03-24', 'March 2024');
GO

-- Okay, now let's look at what book is labelled 2020-03-25 in the Audiobooks_raw table, since that is the next most recent date in the Cozy_Corner_Book_Club column.
-- I see that Atlas Six is a book with the month 2020-03-25, and I know that Atlas Six is a book for March 2025, so I will add that to the #DateCorrections table.
INSERT INTO #DateCorrections (IncorrectDate, CorrectMonthYear)
VALUES ('2020-03-25', 'March 2025');
GO

-- It looks like the pattern is showing that if there are two dates with the same month but different days, the date with the earlier day is for 2024 and the date with the later day is for 2025. So I will use that pattern to fill in the rest of the #DateCorrections table.
INSERT INTO #DateCorrections (IncorrectDate, CorrectMonthYear)
VALUES 
('2020-01-25', 'January 2025'),
('2020-02-25', 'February 2025'),
('2020-04-24', 'April 2024'),
('2020-04-25', 'April 2025'),
('2020-05-24', 'May 2024'),
('2020-05-25', 'May 2025'),
('2020-06-24', 'June 2024'),
('2020-06-25', 'June 2025'),
('2020-07-24', 'July 2024'),
('2020-07-25', 'July 2025'),
('2020-08-24', 'August 2024'),
('2020-09-24', 'September 2024'),
('2020-09-25', 'September 2025'),
('2020-10-24', 'October 2024'),
('2020-11-24', 'November 2024'),
('2020-12-24', 'December 2024');
GO

-- Now that I have the #DateCorrections table filled in with the incorrect dates and their corresponding correct month and year, I can use that table to update the bookclub_monthly_books table with the correct month and year for each book in the Cozy Corner Book Club.

-- Insert all distinct months into cozy_corner_book_club
INSERT INTO cozy_corner_book_club (ClubMonth)
SELECT DISTINCT dc.CorrectMonthYear
FROM dbo.Audiobooks_raw ar
JOIN #DateCorrections dc
	ON ar.Cozy_Corner_Book_Club = dc.IncorrectDate
WHERE ar.Cozy_Corner_Book_Club IS NOT NULL
  AND NOT EXISTS (
		SELECT 1
		FROM cozy_corner_book_club c
		WHERE c.ClubMonth = dc.CorrectMonthYear
  );
GO

-- Preview the month-to-book mapping
SELECT DISTINCT
	dc.CorrectMonthYear,
	c.ClubID,
	b.BookID,
	b.Title
FROM dbo.Audiobooks_raw ar
JOIN #DateCorrections dc
	ON ar.Cozy_Corner_Book_Club = dc.IncorrectDate
JOIN cozy_corner_book_club c
	ON c.ClubMonth = dc.CorrectMonthYear
JOIN books b
	ON b.Title = ar.Book_Title
WHERE ar.Cozy_Corner_Book_Club IS NOT NULL
ORDER BY dc.CorrectMonthYear, b.Title;
GO

-- Check how many books each month will get
SELECT
	dc.CorrectMonthYear,
	COUNT(DISTINCT b.BookID) AS BookCount
FROM dbo.Audiobooks_raw ar
JOIN #DateCorrections dc
	ON ar.Cozy_Corner_Book_Club = dc.IncorrectDate
JOIN books b
	ON b.Title = ar.Book_Title
WHERE ar.Cozy_Corner_Book_Club IS NOT NULL
GROUP BY dc.CorrectMonthYear
ORDER BY MIN(dc.CorrectMonthYear);
GO

-- Insert all month/book pairs into bookclub_monthly_books
INSERT INTO bookclub_monthly_books (ClubID, BookID)
SELECT DISTINCT
	c.ClubID,
	b.BookID
FROM dbo.Audiobooks_raw ar
JOIN #DateCorrections dc
	ON ar.Cozy_Corner_Book_Club = dc.IncorrectDate
JOIN cozy_corner_book_club c
	ON c.ClubMonth = dc.CorrectMonthYear
JOIN books b
	ON b.Title = ar.Book_Title
WHERE ar.Cozy_Corner_Book_Club IS NOT NULL
  AND NOT EXISTS (
		SELECT 1
		FROM bookclub_monthly_books bmb
		WHERE bmb.ClubID = c.ClubID
		  AND bmb.BookID = b.BookID
  );
GO

-- Validate by month
SELECT
	c.ClubMonth,
	b.BookID,
	b.Title
FROM bookclub_monthly_books bmb
JOIN cozy_corner_book_club c
	ON bmb.ClubID = c.ClubID
JOIN books b
	ON bmb.BookID = b.BookID
ORDER BY c.ClubMonth, b.Title;
GO

-- Validate counts per month
SELECT
	c.ClubMonth,
	COUNT(*) AS NumberOfBooks
FROM bookclub_monthly_books bmb
JOIN cozy_corner_book_club c
	ON bmb.ClubID = c.ClubID
GROUP BY c.ClubMonth
ORDER BY c.ClubMonth;
GO

-- I noticed some books are missing from September 2025. I will input them now.
INSERT INTO bookclub_monthly_books (ClubID, BookID)
SELECT
	c.ClubID,
	b.BookID
FROM cozy_corner_book_club c
JOIN books b ON b.Title IN (
		'Hyperion', 
		'The Midnight Library', 
		'All Systems Red', 
		'Dungeon Crawler Carl', 
		'Hitchhikers Guide to the Galaxy'
	)
WHERE c.ClubMonth = 'September 2025';
GO