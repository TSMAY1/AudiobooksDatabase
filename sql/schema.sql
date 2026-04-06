USE Audiobooks;
GO

CREATE TABLE series (
    SeriesID INT PRIMARY KEY IDENTITY(1,1),
    SeriesName NVARCHAR(255) NOT NULL,
    ParentSeriesID INT NULL,
    FOREIGN KEY (ParentSeriesID) REFERENCES series (SeriesID)
);
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

CREATE TABLE readers (
    ReaderID INT PRIMARY KEY IDENTITY(1,1),
    ReaderName NVARCHAR(255) NOT NULL
);
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