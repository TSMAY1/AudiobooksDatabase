/*
    Creates one baseline event for each existing reader/book status.

    EffectiveDate is intentionally NULL because the current database does not
    contain enough information to infer when the status actually took effect.
    The future manual-history UI can supply those dates later.

    Run AddReaderBookStatusHistory.sql before this migration.
*/

SET XACT_ABORT ON;
GO

IF OBJECT_ID('dbo.reader_book_status_history', 'U') IS NULL
BEGIN
    THROW 50001, 'reader_book_status_history does not exist. Run AddReaderBookStatusHistory.sql first.', 1;
END;
GO

BEGIN TRANSACTION;

INSERT INTO dbo.reader_book_status_history (
    ReaderID,
    BookID,
    FromStatus,
    ToStatus,
    EffectiveDate,
    EventSource,
    Notes
)
SELECT
    rs.ReaderID,
    rs.BookID,
    NULL,
    rs.ReadingStatus,
    NULL,
    'Migration',
    'Baseline event created from the current reading status; effective date unknown.'
FROM dbo.reading_status rs
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.reader_book_status_history history WITH (UPDLOCK, HOLDLOCK)
    WHERE history.ReaderID = rs.ReaderID
      AND history.BookID = rs.BookID
);

COMMIT TRANSACTION;
GO
