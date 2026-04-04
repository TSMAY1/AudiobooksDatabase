USE Audiobooks;

CREATE TABLE books (
	BookID INT PRIMARY KEY IDENTITY(1,1),
	Title NVARCHAR(255) NOT NULL,
	SeriesID INT NULL,
	BookNumber DECIMAL(4, 1),
	UniverseReadingOrder DECIMAL(5,2) NULL,
	LengthType NVARCHAR(50),
	Demographic NVARCHAR(50),
	Full_Cast BIT,
	Notes NVARCHAR(MAX),

	FOREIGN KEY (SeriesID) REFERENCES series(SeriesID)
	);
GO

CREATE TABLE authors_new (
    AuthorID INT PRIMARY KEY IDENTITY(1,1),
    AuthorName NVARCHAR(255) NOT NULL UNIQUE
);
GO

CREATE TABLE book_authors (
	BookID INT NOT NULL,
	AuthorID INT NOT NULL,
	AuthorOrder INT NULL,
	PRIMARY KEY (BookID, AuthorID),
	FOREIGN KEY (BookID) REFERENCES books(BookID),
	FOREIGN KEY (AuthorID) REFERENCES authors_new(AuthorID)
);
GO

CREATE TABLE series (
	SeriesID INT PRIMARY KEY IDENTITY(1,1),
	SeriesName NVARCHAR(255),
	ParentSeriesID INT NULL,
	FOREIGN KEY (ParentSeries) REFERENCES series (SeriesID)
);
GO


CREATE TABLE genres (
	GenreID INT PRIMARY KEY IDENTITY(1,1),
	GenreName NVARCHAR(255) NOT NULL UNIQUE
);
GO

CREATE TABLE book_genres (
	BookID INT,
	GenreID INT,
	GenreType NVARCHAR(50) NOT NULL CHECK (GenreType IN ('Main', 'Secondary')),
	PRIMARY KEY (BookID, GenreID, GenreType),
	FOREIGN KEY (BookID) REFERENCES books(BookID),
	FOREIGN KEY (GenreID) REFERENCES genres(GenreID)
);
GO

CREATE TABLE readers (
	ReaderID INT PRIMARY KEY IDENTITY(1,1),
	ReaderName NVARCHAR(255) NOT NULL
);
GO

CREATE TABLE reading_status (
    ReaderID INT,
    BookID INT,
    ReadingStatus NVARCHAR(20) NOT NULL
        CONSTRAINT CK_reading_status_ReadingStatus
        CHECK (ReadingStatus IN ('Unread', 'TBR', 'Reading', 'Read', 'DNF')),
    Rating DECIMAL(4,2) NULL,
    PRIMARY KEY (ReaderID, BookID),
    FOREIGN KEY (ReaderID) REFERENCES readers(ReaderID),
    FOREIGN KEY (BookID) REFERENCES books(BookID)
);

CREATE TABLE cozy_corner_book_club (
	ClubID int IDENTITY(1, 1) PRIMARY KEY,
	ClubMonth nvarchar(255) NOT NULL, -- E.g. 'January 2025'
	FlyerTheme nvarchar(255) NULL, -- E.g. 'Enemies to Lovers', 'Contemporary Romance', etc.
	FlyerFilePath nvarchar(500) NULL, -- Path to PDF flyer
	Notes nvarchar(MAX) NULL
);
GO

CREATE TABLE bookclub_monthly_books (
	ClubID int NOT NULL,
	BookID int NOT NULL,
	DisplayOrder int NULL, -- Optional column to specify the order of books for the month

	PRIMARY KEY (ClubID, BookID),
	FOREIGN KEY (ClubID) REFERENCES cozy_corner_book_club(ClubID),
	FOREIGN KEY (BookID) REFERENCES books(BookID)
);
GO

CREATE TABLE bookclub_calendars (
	CalendarID int IDENTITY(1, 1) PRIMARY KEY,
	YearNum int NOT NULL,
	CalendarFilePath nvarchar(500) NOT NULL, -- Path to calendar PDF
	Notes NVARCHAR(MAX) NULL
);
GO

CREATE TABLE mini_book_status (
    ReaderID INT NOT NULL,
    BookID INT NOT NULL,
    IsPrinted BIT NOT NULL DEFAULT 0,
    IsCrafted BIT NOT NULL DEFAULT 0 CHECK (IsCrafted >= IsPrinted), -- Can't be crafted if it's not printed

    PRIMARY KEY (ReaderID, BookID),
    FOREIGN KEY (ReaderID) REFERENCES readers(ReaderID),
    FOREIGN KEY (BookID) REFERENCES books(BookID)
);
GO


