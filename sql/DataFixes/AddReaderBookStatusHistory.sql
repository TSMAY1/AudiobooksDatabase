/*
    Adds status-history storage to an existing Audiobooks database.

    This migration creates the table and supporting indexes only. It does not
    create baseline events or change SetReadingStatus; those are later steps.
*/

SET XACT_ABORT ON;
GO

BEGIN TRANSACTION;

IF OBJECT_ID('dbo.reader_book_status_history', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.reader_book_status_history (
        StatusHistoryID BIGINT IDENTITY(1,1) PRIMARY KEY,
        ReaderID INT NOT NULL,
        BookID INT NOT NULL,
        FromStatus NVARCHAR(20) NULL,
        ToStatus NVARCHAR(20) NOT NULL,
        ChangedAtUtc DATETIME2(7) NOT NULL
            CONSTRAINT DF_reader_book_status_history_ChangedAtUtc
            DEFAULT SYSUTCDATETIME(),
        EffectiveDate DATE NULL,
        EventSource NVARCHAR(20) NOT NULL
            CONSTRAINT DF_reader_book_status_history_EventSource
            DEFAULT ('App'),
        Notes NVARCHAR(500) NULL,

        CONSTRAINT FK_reader_book_status_history_ReaderID
            FOREIGN KEY (ReaderID) REFERENCES dbo.readers(ReaderID),
        CONSTRAINT FK_reader_book_status_history_BookID
            FOREIGN KEY (BookID) REFERENCES dbo.books(BookID),
        CONSTRAINT CK_reader_book_status_history_FromStatus
            CHECK (FromStatus IS NULL OR FromStatus IN ('Unread', 'TBR', 'Reading', 'Read', 'DNF')),
        CONSTRAINT CK_reader_book_status_history_ToStatus
            CHECK (ToStatus IN ('Unread', 'TBR', 'Reading', 'Read', 'DNF')),
        CONSTRAINT CK_reader_book_status_history_StatusChanged
            CHECK (FromStatus IS NULL OR FromStatus <> ToStatus),
        CONSTRAINT CK_reader_book_status_history_EventSource
            CHECK (EventSource IN ('App', 'Migration', 'Manual'))
    );
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.reader_book_status_history')
      AND name = 'IX_reader_book_status_history_ReaderID_BookID_Date'
)
BEGIN
    CREATE INDEX IX_reader_book_status_history_ReaderID_BookID_Date
    ON dbo.reader_book_status_history (ReaderID, BookID, EffectiveDate DESC, ChangedAtUtc DESC)
    INCLUDE (FromStatus, ToStatus, EventSource);
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.reader_book_status_history')
      AND name = 'IX_reader_book_status_history_ReaderID_ToStatus_Date'
)
BEGIN
    CREATE INDEX IX_reader_book_status_history_ReaderID_ToStatus_Date
    ON dbo.reader_book_status_history (ReaderID, ToStatus, EffectiveDate DESC)
    INCLUDE (BookID, FromStatus, ChangedAtUtc, EventSource);
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.reader_book_status_history')
      AND name = 'IX_reader_book_status_history_BookID'
)
BEGIN
    CREATE INDEX IX_reader_book_status_history_BookID
    ON dbo.reader_book_status_history (BookID)
    INCLUDE (ReaderID, ToStatus, EffectiveDate);
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.reader_book_status_history')
      AND name = 'IX_reader_book_status_history_ReaderID_BookID_ChangedAtUtc'
)
BEGIN
    CREATE INDEX IX_reader_book_status_history_ReaderID_BookID_ChangedAtUtc
    ON dbo.reader_book_status_history (ReaderID, BookID, ChangedAtUtc DESC)
    INCLUDE (ToStatus, EffectiveDate);
END;

COMMIT TRANSACTION;
GO
