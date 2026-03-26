USE Audiobooks;
GO

-- I need to fix the way authors are currently organized, due to rows with multiple authors listed
-- First, I will backup my current data in the authors, books, reading_status and bookclub_monthly_books tables just in case

SELECT * INTO authors_backup FROM authors;
SELECT * INTO books_backup FROM books;
SELECT * INTO reading_status_backup FROM reading_status;
SELECT * INTO bookclub_monthly_books_backup FROM bookclub_monthly_books;
GO

-- Now, I will create a new joining table for book authors

CREATE TABLE book_authors (
	BookID INT NOT NULL,
	AuthorID INT NOT NULL,
	AuthorOrder INT NULL,
	PRIMARY KEY (BookID, AuthorID),
	FOREIGN KEY (BookID) REFERENCES books(BookID),
	FOREIGN KEY (AuthorID) REFERENCES authors_new(AuthorID)
);
GO

-- Let's find all rows that likely contain multiple authors

SELECT AuthorID, AuthorName
FROM authors
WHERE AuthorName LIKE '%,%'
   OR AuthorName LIKE '%&%'
   OR AuthorName LIKE '%;%'
ORDER BY AuthorName;
GO

-- I'll create a clean staging table for split authors

CREATE TABLE author_migration_map (
	OldAuthorID INT NOT NULL,
	OldAuthorName NVARCHAR(255) NOT NULL,
	NewAuthorName NVARCHAR(255) NOT NULL,
	AuthorOrder INT NOT NULL
);
GO

-- I'll map the already single author rows to the table first

INSERT INTO author_migration_map (OldAuthorID, OldAuthorName, NewAuthorName, AuthorOrder)
SELECT 
    AuthorID,
    AuthorName,
    AuthorName,
    1
FROM authors
WHERE AuthorName NOT LIKE '%,%'
  AND AuthorName NOT LIKE '%&%'
  AND AuthorName NOT LIKE '%;%';
GO

INSERT INTO author_migration_map (OldAuthorID, OldAuthorName, NewAuthorName, AuthorOrder)
VALUES
(5, 'A.R. Capetta, Cory McCarthy', 'A.R. Capetta', 1),
(5, 'A.R. Capetta, Cory McCarthy', 'Cory McCarthy', 2),

(17, 'Amal El-Mohtar, Max Gladstone', 'Amal El-Mohtar', 1),
(17, 'Amal El-Mohtar, Max Gladstone', 'Max Gladstone', 2),

(38, 'Brandon Sanderson & Janci Patterson', 'Brandon Sanderson', 1),
(38, 'Brandon Sanderson & Janci Patterson', 'Janci Patterson', 2),

(47, 'Cece Rose, G. Bailey', 'Cece Rose', 1),
(47, 'Cece Rose, G. Bailey', 'G. Bailey', 2),

(108, 'Homer, W. H. D. Rouse (Translator)', 'Homer', 1),
(108, 'Homer, W. H. D. Rouse (Translator)', 'W. H. D. Rouse', 2),

(119, 'Jane Washington, Jaymin Eve', 'Jane Washington', 1),
(119, 'Jane Washington, Jaymin Eve', 'Jaymin Eve', 2),

(127, 'Jeremy Taggart; Jonathan Torrens', 'Jeremy Taggart', 1),
(127, 'Jeremy Taggart; Jonathan Torrens', 'Jonathan Torrens', 2),

(134, 'Joseph Fink, Jeffrey Cranor', 'Joseph Fink', 1),
(134, 'Joseph Fink, Jeffrey Cranor', 'Jeffrey Cranor', 2),

(164, 'Leigh Bardugo, Anthology (Various Authors)', 'Leigh Bardugo', 1),
(164, 'Leigh Bardugo, Anthology (Various Authors)', 'Anthology (Various Authors)', 2),

(213, 'Paulo Coelho; Yvonne Morrison; Charles Dickens', 'Paulo Coelho', 1),
(213, 'Paulo Coelho; Yvonne Morrison; Charles Dickens', 'Yvonne Morrison', 2),
(213, 'Paulo Coelho; Yvonne Morrison; Charles Dickens', 'Charles Dickens', 3),

(219, 'Rachel Caine, Ann Aguirre', 'Rachel Caine', 1),
(219, 'Rachel Caine, Ann Aguirre', 'Ann Aguirre', 2),

(227, 'Rhys Wakefield, William Day Frank', 'Rhys Wakefield', 1),
(227, 'Rhys Wakefield, William Day Frank', 'William Day Frank', 2),

(241, 'Sarah Wallace & S.O. Callahan', 'Sarah Wallace', 1),
(241, 'Sarah Wallace & S.O. Callahan', 'S.O. Callahan', 2),

(246, 'Shannon Mayer, Kelly St. Clare', 'Shannon Mayer', 1),
(246, 'Shannon Mayer, Kelly St. Clare', 'Kelly St. Clare', 2);
GO

-- Create a new clean authors table

CREATE TABLE authors_new (
    AuthorID INT PRIMARY KEY IDENTITY(1,1),
    AuthorName NVARCHAR(255) NOT NULL UNIQUE
);
GO

-- Insert distinct values into the new table

INSERT INTO authors_new (AuthorName)
SELECT DISTINCT NewAuthorName
FROM author_migration_map
ORDER BY NewAuthorName;
GO

-- Create a mapping from old authors to new authors

CREATE TABLE author_id_bridge (
    OldAuthorID INT NOT NULL,
    OldAuthorName NVARCHAR(255) NOT NULL,
    NewAuthorID INT NOT NULL,
    NewAuthorName NVARCHAR(255) NOT NULL,
    AuthorOrder INT NOT NULL
);
GO

-- Populate the mapping table

INSERT INTO author_id_bridge (OldAuthorID, OldAuthorName, NewAuthorID, NewAuthorName, AuthorOrder)
SELECT
    amm.OldAuthorID,
    amm.OldAuthorName,
    an.AuthorID,
    an.AuthorName,
    amm.AuthorOrder
FROM author_migration_map amm
JOIN authors_new an
    ON amm.NewAuthorName = an.AuthorName;
GO

-- Populate the book_authors table

INSERT INTO book_authors (BookID, AuthorID, AuthorOrder)
SELECT
    b.BookID,
    aib.NewAuthorID,
    aib.AuthorOrder
FROM books b
JOIN author_id_bridge aib
    ON b.AuthorID = aib.OldAuthorID;
GO

-- Lets do some checks

SELECT b.BookID, b.Title
FROM books b
LEFT JOIN book_authors ba
    ON b.BookID = ba.BookID
WHERE ba.BookID IS NULL;
GO

SELECT 
    b.BookID,
    b.Title,
    COUNT(*) AS AuthorCount
FROM books b
JOIN book_authors ba
    ON b.BookID = ba.BookID
GROUP BY b.BookID, b.Title
HAVING COUNT(*) > 1
ORDER BY AuthorCount DESC, b.Title;
GO

SELECT
    b.Title,
    an.AuthorName,
    ba.AuthorOrder
FROM book_authors ba
JOIN books b
    ON ba.BookID = b.BookID
JOIN authors_new an
    ON ba.AuthorID = an.AuthorID
ORDER BY b.Title, ba.AuthorOrder;
GO

-- I've updated all of my queries to use the new tables
-- Now I need to replace the old authors table

SELECT 
    fk.name AS ForeignKeyName,
    OBJECT_NAME(fk.parent_object_id) AS ChildTable,
    c1.name AS ChildColumn,
    OBJECT_NAME(fk.referenced_object_id) AS ReferencedTable
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc
    ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns c1
    ON fkc.parent_object_id = c1.object_id
   AND fkc.parent_column_id = c1.column_id
WHERE OBJECT_NAME(fk.parent_object_id) = 'books'
  AND c1.name = 'AuthorID';
GO

ALTER TABLE dbo.books
DROP CONSTRAINT FK__books__Notes__628FA481;
GO

ALTER TABLE dbo.books
DROP COLUMN AuthorID;
GO

-- Lets test

SELECT TOP 20
    b.Title,
    a.AuthorName,
    ba.AuthorOrder
FROM dbo.book_authors ba
JOIN dbo.books b
    ON ba.BookID = b.BookID
JOIN dbo.authors_new a
    ON ba.AuthorID = a.AuthorID
ORDER BY b.Title, ba.AuthorOrder;
GO

SELECT 
    b.Title,
    COUNT(ba.AuthorID) AS AuthorCount
FROM dbo.books b
JOIN dbo.book_authors ba
    ON b.BookID = ba.BookID
GROUP BY b.Title
ORDER BY AuthorCount DESC;
GO