USE Audiobooks;
GO

PRINT 'Starting seed data insert...';
GO

--------------------------------------------------
-- Authors
--------------------------------------------------
SET IDENTITY_INSERT authors_new ON;
INSERT INTO authors_new (AuthorID, AuthorName)
VALUES
    (1, N'Brandon Sanderson'),
    (2, N'Alex Aster'),
    (3, N'Andy Weir'),
    (4, N'Amal El-Mohtar'),
    (5, N'Max Gladstone'),
    (6, N'Callie Hart'),
    (7, N'Robin Hobb'),
    (8, N'Carissa Broadbent'),
    (9, N'Sarah J. Maas'),
    (10, N'Leigh Bardugo'),
    (11, N'Lemony Snicket'),
    (12, N'Madeline Miller'),
    (13, N'Olivia Atwater');

SET IDENTITY_INSERT authors_new OFF;
GO

--------------------------------------------------
-- Series
--------------------------------------------------
SET IDENTITY_INSERT series ON;
INSERT INTO series (SeriesID, SeriesName)
VALUES
    (1, N'Mistborn Era 1'),
    (2, N'The Stormlight Archive'),
    (3, N'Lightlark'),
    (4, N'Standalone'),
    (5, N'Fae & Alchemy'),
    (6, N'Liveship Traders Trilogy'),
    (7, N'Crowns of Nyaxia'),
    (8, N'Throne of Glass'),
    (9, N'Six of Crows'),
    (10, N'A Series of Unfortunate Events'),
    (11, N'Regency Faerie Tales');

SET IDENTITY_INSERT series OFF;
GO

--------------------------------------------------
-- Genres
--------------------------------------------------
SET IDENTITY_INSERT genres ON;
INSERT INTO genres (GenreID, GenreName)
VALUES
    (1, N'Fantasy'),
    (2, N'Sci-Fi'),
    (3, N'Romance'),
    (4, N'Politics'),
    (5, N'Adventure'),
    (6, N'LGBT+'),
    (7, N'Retelling'),
    (8, N'Vampires'),
    (9, N'Fae'),
    (10, N'Mystery'),
    (11, N'Regency'),
    (12, N'Heist'),
    (13, N'Mythology');

SET IDENTITY_INSERT genres OFF;
GO

--------------------------------------------------
-- Readers
--------------------------------------------------
SET IDENTITY_INSERT readers ON;

INSERT INTO readers (ReaderID, ReaderName)
VALUES
    (1, N'Angela'),
    (2, N'Tori');

SET IDENTITY_INSERT readers OFF;
GO

--------------------------------------------------
-- Books
--------------------------------------------------
SET IDENTITY_INSERT books ON;
INSERT INTO books
    (BookID, Title, SeriesID, BookNumber, LengthType, Demographic, Full_Cast, Notes)
VALUES
    (1, N'The Final Empire', 1, 1.0, N'Novel', N'Adult', 1, NULL),
    (2, N'The Well of Ascension', 1, 2.0, N'Novel', N'Adult', 1, NULL),
    (3, N'Project Hail Mary', 4, NULL, N'Novel', N'Adult', 0, NULL),
    (4, N'This is How You Lose the Time War', 4, NULL, N'Novella', N'Adult', 0, NULL),
    (5, N'Quicksilver', 5, 1.0, N'Novel', N'Adult', 0, N'Unique audiobook narration style'),
    (6, N'Ship of Magic', 6, 1.0, N'Novel', N'Adult', 0, NULL),
    (7, N'Mad Ship', 6, 2.0, N'Novel', N'Adult', 0, NULL),
    (8, N'Ship of Destiny', 6, 3.0, N'Novel', N'Adult', 0, NULL),
    (9, N'Six Scorched Roses', 7, 1.5, N'Novella', N'Adult', 0, NULL),
    (10, N'The Serpent and the Wings of Night', 7, 1.0, N'Novel', N'Adult', 0, NULL),
    (11, N'The Assassin''s Blade', 8, 0.5, N'Novel', N'Young Adult', 0, NULL),
    (12, N'Six of Crows', 9, 1.0, N'Novel', N'Young Adult', 0, NULL),
    (13, N'The Bad Beginning', 10, 1.0, N'Novel', N'Kids', 0, NULL),
    (14, N'The Reptile Room', 10, 2.0, N'Novel', N'Kids', 0, NULL),
    (15, N'Galatea', 4, NULL, N'Short Story', N'Adult', 0, NULL),
    (16, N'The Way of Kings', 2, 1.0, N'Beast', N'Adult', 1, N'Original audiobook and graphic audio versions'),
    (17, N'Half a Soul', 11, 1.0, N'Novel', N'Young Adult', 0, NULL);

SET IDENTITY_INSERT books OFF;
GO

--------------------------------------------------
-- Book / author relationships
--------------------------------------------------
INSERT INTO book_authors (BookID, AuthorID, AuthorOrder)
VALUES
    (1, 1, 1),
    (2, 1, 1),
    (3, 3, 1),
    (4, 4, 1),
    (4, 5, 2),
    (5, 6, 1),
    (6, 7, 1),
    (7, 7, 1),
    (8, 7, 1),
    (9, 8, 1),
    (10, 8, 1),
    (11, 9, 1),
    (12, 10, 1),
    (13, 11, 1),
    (14, 11, 1),
    (15, 12, 1),
    (16, 1, 1),
    (17, 13, 1);
GO

--------------------------------------------------
-- Book / genre relationships  
--------------------------------------------------
INSERT INTO book_genres (BookID, GenreID, GenreType)
VALUES
    (1, 1, N'Main'),
    (1, 4, N'Secondary'),
    (2, 1, N'Main'),
    (2, 4, N'Secondary'),
    (3, 2, N'Main'),
    (3, 5, N'Secondary'),
    (4, 2, N'Main'),
    (4, 3, N'Secondary'),
    (4, 6, N'Secondary'),
    (5, 1, N'Main'),
    (5, 3, N'Secondary'),
    (6, 1, N'Main'),
    (6, 4, N'Secondary'),
    (6, 5, N'Secondary'),
    (7, 1, N'Main'),
    (7, 4, N'Secondary'),
    (7, 5, N'Secondary'),
    (8, 1, N'Main'),
    (8, 4, N'Secondary'),
    (8, 5, N'Secondary'),
    (9, 1, N'Main'),
    (9, 3, N'Secondary'),
    (9, 8, N'Secondary'),
    (10, 1, N'Main'),
    (10, 3, N'Secondary'),
    (10, 8, N'Secondary'),
    (11, 1, N'Main'),
    (11, 3, N'Secondary'),
    (11, 9, N'Secondary'),
    (12, 1, N'Main'),
    (12, 4, N'Secondary'),
    (12, 12, N'Secondary'),
    (12, 6, N'Secondary'),
    (13, 5, N'Main'),
    (13, 10, N'Secondary'),
    (14, 5, N'Main'),
    (14, 10, N'Secondary'),
    (15, 1, N'Main'),
    (15, 13, N'Secondary'),
    (15, 7, N'Secondary'),
    (16, 1, N'Main'),
    (16, 4, N'Secondary'),
    (17, 3, N'Main'),
    (17, 11, N'Secondary'),
    (17, 9, N'Secondary');
GO

--------------------------------------------------
-- Reading status
--------------------------------------------------
INSERT INTO reading_status (ReaderID, BookID, ReadStatus, Rating)
VALUES
    (1, 1, 1, 5.00),
    (1, 2, 1, 4.00),
    (1, 3, 0, NULL),
    (1, 4, 0, NULL),
    (1, 5, 1, 4.00),
    (1, 6, 0, NULL),
    (1, 7, 0, NULL),
    (1, 8, 0, NULL),
    (1, 9, 1, 5.00),
    (1, 10, 1, 4.00),
    (1, 11, 1, 4.00),
    (1, 12, 1, 5.00),
    (1, 13, 0, NULL),
    (1, 14, 0, NULL),
    (1, 15, 1, 4.50),
    (1, 16, 1, 5.00),
    (1, 17, 1, 5.00),
    (2, 1, 1, 4.50),
    (2, 2, 1, 4.50),
    (2, 3, 1, 5.00),
    (2, 4, 1, 4.00),
    (2, 5, 0, NULL),
    (2, 6, 1, 4.80),
    (2, 7, 1, 4.50),
    (2, 8, 1, 5.00),
    (2, 9, 1, 4.50),
    (2, 10, 0, NULL),
    (2, 11, 0, NULL),
    (2, 12, 1, 5.00),
    (2, 13, 1, 3.80),
    (2, 14, 1, 3.50),
    (2, 15, 1, 4.00),
    (2, 16, 1, 5.00),
    (2, 17, 1, 5.00);
GO

--------------------------------------------------
-- Cozy Corner Book Club
--------------------------------------------------
SET IDENTITY_INSERT cozy_corner_book_club ON;
INSERT INTO cozy_corner_book_club
    (ClubID, ClubMonth, FlyerTheme, FlyerFilePath, Notes)
VALUES
    (1, N'April 2024', N'Fae & Fairy Tales', NULL, N'The first month of the cozy corner book club!'),
    (2, N'May 2024', N'Brandon Sanderson Showcase', NULL, N'Tori''s pick!');
SET IDENTITY_INSERT cozy_corner_book_club OFF;
GO

--------------------------------------------------
-- Book club monthly books
--------------------------------------------------
INSERT INTO bookclub_monthly_books (ClubID, BookID, DisplayOrder)
VALUES
    (1, 5, 1),
    (1, 11, 2),
    (1, 17, 3),
    (2, 1, 1),
    (2, 2, 2),
    (2, 16, 3);
GO

PRINT 'Seed data insert complete!';
GO