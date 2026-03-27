USE Audiobooks;
GO

-- I want to add new options to ReadingStatus!!


-- Add the new column
ALTER TABLE reading_status
ADD ReadingStatus NVARCHAR(20) NULL;
GO

-- Specify the allowed values
ALTER TABLE reading_status
ADD CONSTRAINT CK_reading_status_ReadingStatus
CHECK (ReadingStatus IN ('Unread', 'TBR', 'Reading', 'Read', 'DNF'));
GO

-- Migrate existing values
-- ReadStatus = 1  -> Read
-- ReadStatus = 0  -> TBR
-- NULL            -> TBR
UPDATE reading_status
SET ReadingStatus =
    CASE
        WHEN ReadStatus = 1 THEN 'Read'
        WHEN ReadStatus = 0 THEN 'Unread'
        ELSE 'Unread'
    END;
GO

-- The new column should be required
ALTER TABLE reading_status
ALTER COLUMN ReadingStatus NVARCHAR(20) NOT NULL;
GO

-- Default unread
ALTER TABLE reading_status
ADD CONSTRAINT DF_reading_status_ReadingStatus
DEFAULT ('Unread') FOR ReadingStatus;
GO

-- Make sure anything that isn't read or DNF doesn't have a rating
UPDATE reading_status
SET Rating = NULL
WHERE ReadingStatus IN ('Unread', 'TBR', 'Reading');
GO

-- Drop old column
ALTER TABLE reading_status
DROP COLUMN ReadStatus;
GO

SELECT *
FROM reading_status