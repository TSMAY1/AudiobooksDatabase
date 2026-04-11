USE Audiobooks;
GO

CREATE TABLE series (
    SeriesID INT PRIMARY KEY IDENTITY(1,1),
    SeriesName NVARCHAR(255) NOT NULL,
    ParentSeriesID INT NULL,
    FOREIGN KEY (ParentSeriesID) REFERENCES series (SeriesID)
);
GO

CREATE INDEX IX_series_SeriesName
ON series (SeriesName);
GO

CREATE UNIQUE INDEX UX_series_SeriesName
ON series (SeriesName);
GO

CREATE INDEX IX_series_ParentSeriesID
ON series (ParentSeriesID);
GO

CREATE TABLE books (
    BookID INT PRIMARY KEY IDENTITY(1,1),
    Title NVARCHAR(255) NOT NULL,
    SeriesID INT NULL,
    BookNumber DECIMAL(4,1) NULL,
    UniverseReadingOrder DECIMAL(5,2) NULL,
    LengthType NVARCHAR(50) NULL,
    Demographic NVARCHAR(50) NULL,
    Full_Cast BIT NULL,
    Notes NVARCHAR(MAX) NULL,

    FOREIGN KEY (SeriesID) REFERENCES series(SeriesID)
);
GO

CREATE INDEX IX_books_SeriesID_BookNumber
ON books (SeriesID, BookNumber);
GO

CREATE INDEX IX_books_Title
ON books (Title);
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

CREATE INDEX IX_book_authors_AuthorID_BookID
ON book_authors (AuthorID, BookID);
GO

CREATE TABLE genres (
    GenreID INT PRIMARY KEY IDENTITY(1,1),
    GenreName NVARCHAR(255) NOT NULL UNIQUE
);
GO

CREATE TABLE book_genres (
    BookID INT NOT NULL,
    GenreID INT NOT NULL,
    GenreType NVARCHAR(50) NOT NULL
        CHECK (GenreType IN ('Main', 'Secondary')),

    PRIMARY KEY (BookID, GenreID, GenreType),
    FOREIGN KEY (BookID) REFERENCES books(BookID),
    FOREIGN KEY (GenreID) REFERENCES genres(GenreID)
);
GO

CREATE INDEX IX_book_genres_GenreID_BookID
ON book_genres (GenreID, BookID);
GO

CREATE TABLE readers (
    ReaderID INT PRIMARY KEY IDENTITY(1,1),
    ReaderName NVARCHAR(255) NOT NULL
);
GO

CREATE UNIQUE INDEX UX_readers_ReaderName
ON readers (ReaderName);
GO

CREATE TABLE reading_status (
    ReaderID INT NOT NULL,
    BookID INT NOT NULL,
    ReadingStatus NVARCHAR(20) NOT NULL
        CONSTRAINT CK_reading_status_ReadingStatus
        CHECK (ReadingStatus IN ('Unread', 'TBR', 'Reading', 'Read', 'DNF')),
    Rating DECIMAL(4,2) NULL,

    PRIMARY KEY (ReaderID, BookID),
    FOREIGN KEY (ReaderID) REFERENCES readers(ReaderID),
    FOREIGN KEY (BookID) REFERENCES books(BookID)
);
GO

CREATE INDEX IX_reading_status_BookID
ON reading_status (BookID);
GO

CREATE INDEX IX_reading_status_ReaderID_ReadingStatus_BookID
ON reading_status (ReaderID, ReadingStatus, BookID)
INCLUDE (Rating);
GO

CREATE INDEX IX_reading_status_ReadingStatus_BookID
ON reading_status (ReadingStatus, BookID)
INCLUDE (ReaderID, Rating);
GO


CREATE TABLE bookclub_calendars (
    CalendarID INT IDENTITY(1,1) PRIMARY KEY,
    YearNum INT NOT NULL,
    CalendarFilePath NVARCHAR(500) NOT NULL,
    Notes NVARCHAR(MAX) NULL,

    CONSTRAINT UQ_bookclub_calendars_YearNum UNIQUE (YearNum)
);
GO

CREATE TABLE cozy_corner_book_club (
    ClubID INT IDENTITY(1,1) PRIMARY KEY,
    ClubMonth NVARCHAR(255) NOT NULL,      -- e.g. 'January 2025'
    YearNum INT NOT NULL,
    MonthNum INT NOT NULL
        CONSTRAINT CK_cozy_corner_book_club_MonthNum
        CHECK (MonthNum BETWEEN 1 AND 12),
    FlyerTheme NVARCHAR(255) NULL,
    FlyerFilePath NVARCHAR(500) NULL,
    Notes NVARCHAR(MAX) NULL,

    CONSTRAINT UQ_cozy_corner_book_club_YearMonth UNIQUE (YearNum, MonthNum),
    CONSTRAINT FK_cozy_corner_book_club_calendar_year
        FOREIGN KEY (YearNum) REFERENCES bookclub_calendars(YearNum)
);
GO

CREATE TABLE bookclub_monthly_books (
    ClubID INT NOT NULL,
    BookID INT NOT NULL,
    DisplayOrder INT NULL,

    PRIMARY KEY (ClubID, BookID),
    FOREIGN KEY (ClubID) REFERENCES cozy_corner_book_club(ClubID),
    FOREIGN KEY (BookID) REFERENCES books(BookID)
);
GO

CREATE INDEX IX_bookclub_monthly_books_BookID
ON bookclub_monthly_books (BookID);
GO

CREATE TABLE mini_book_status (
    ReaderID INT NOT NULL,
    BookID INT NOT NULL,
    IsPrinted BIT NOT NULL DEFAULT 0,
    IsCrafted BIT NOT NULL DEFAULT 0,

    PRIMARY KEY (ReaderID, BookID),
    FOREIGN KEY (ReaderID) REFERENCES readers(ReaderID),
    FOREIGN KEY (BookID) REFERENCES books(BookID),
    CONSTRAINT CK_mini_book_status_CraftedPrinted
        CHECK (
            IsCrafted = 0
            OR (IsCrafted = 1 AND IsPrinted = 1)
        )
);
GO

CREATE INDEX IX_mini_book_status_BookID
ON mini_book_status (BookID);
GO

CREATE TABLE book_covers (
    CoverID INT IDENTITY(1,1) PRIMARY KEY,
    BookID INT NOT NULL,
    CoverLabel NVARCHAR(100) NULL,
    ImageFilePath NVARCHAR(500) NOT NULL,
    ImageFormat NVARCHAR(20) NOT NULL,
    WidthPx INT NOT NULL,
    HeightPx INT NOT NULL,
    FileSizeKB DECIMAL(10,2) NULL,
    ImageHash NVARCHAR(64) NULL,
    SortOrder INT NOT NULL
        CONSTRAINT DF_book_covers_SortOrder DEFAULT 1,
    IsPrimary BIT NOT NULL
        CONSTRAINT DF_book_covers_IsPrimary DEFAULT 0,
    SourceNotes NVARCHAR(500) NULL,
    DateAdded DATETIME2 NOT NULL
        CONSTRAINT DF_book_covers_DateAdded DEFAULT SYSDATETIME(),

    FOREIGN KEY (BookID) REFERENCES books(BookID),
    CONSTRAINT CK_book_covers_WidthPx
        CHECK (WidthPx > 0),
    CONSTRAINT CK_book_covers_HeightPx
        CHECK (HeightPx > 0),
    CONSTRAINT CK_book_covers_FileSizeKB
        CHECK (FileSizeKB IS NULL OR FileSizeKB > 0)
);
GO

CREATE UNIQUE INDEX UX_book_covers_one_primary_per_book
ON book_covers (BookID)
WHERE IsPrimary = 1;
GO

CREATE INDEX IX_book_covers_BookID_SortOrder
ON book_covers (BookID, SortOrder, CoverID);
GO

CREATE INDEX IX_book_covers_ImageHash
ON book_covers (ImageHash)
WHERE ImageHash IS NOT NULL;
GO

