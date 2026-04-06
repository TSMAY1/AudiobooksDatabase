USE Audiobooks;
GO

--------------------------------------------------
-- AddBook
-- Inserts a new book and links its authors and genres
--------------------------------------------------

CREATE OR ALTER PROCEDURE AddBook
	@Title NVARCHAR(255),
	@Authors NVARCHAR(MAX), -- e.g. 'Brandon Sanderson' or 'Brandon Sanderson, Janci Patterson'
	@SeriesName NVARCHAR(255) = NULL, 
	@BookNumber DECIMAL(4,1) = NULL,
	@LengthType NVARCHAR(50) = NULL,
	@Demographic NVARCHAR(50) = NULL,
	@Full_Cast BIT = NULL,
	@Notes NVARCHAR(MAX) = NULL,
	@MainGenres NVARCHAR(MAX) = NULL, -- e.g. 'Fantasy'
	@SecondaryGenres NVARCHAR(MAX) = NULL -- e.g. 'Magic, Politics'
AS
BEGIN
	SET NOCOUNT ON; -- Don't clutter output with row count messages
	SET XACT_ABORT ON; -- If anything goes wrong, immediately stop and rollback everything

	BEGIN TRANSACTION;

	BEGIN TRY
		DECLARE @BookID INT;
		DECLARE @SeriesID INT = NULL;

		-- 1. Ensure series exists if provided
		IF @SeriesName IS NOT NULL AND LTRIM(RTRIM(@SeriesName)) <> '' -- Not NULL, not empty, not just spaces
		BEGIN
			IF NOT EXISTS (
				SELECT 1
				FROM series
				WHERE SeriesName = LTRIM(RTRIM(@SeriesName))
			)
			BEGIN
				INSERT INTO series (SeriesName)
				VALUES (LTRIM(RTRIM(@SeriesName)));
			END;

			SELECT @SeriesID = SeriesID
			FROM series
			WHERE SeriesName = LTRIM(RTRIM(@SeriesName));
		END;

		-- 2. Prevent duplicate book insert
		IF EXISTS (
			SELECT 1
			FROM books
			WHERE Title = LTRIM(RTRIM(@Title))
				AND (
						(@SeriesID IS NULL AND SeriesID IS NULL)
						OR SeriesID = @SeriesID
					)
				AND (
						(@BookNumber IS NULL AND BookNumber IS NULL)
						OR BookNumber = @BookNumber
					)
		)
		BEGIN
			RAISERROR('This book already appears to be in the database.', 16, 1);
		END;

				-- 3. Insert the book
		INSERT INTO books (
			Title,
			SeriesID,
			BookNumber,
			LengthType,
			Demographic,
			Full_Cast,
			Notes
		)
		VALUES (
			LTRIM(RTRIM(@Title)),
			@SeriesID,
			@BookNumber,
			@LengthType,
			@Demographic,
			@Full_Cast,
			@Notes
		);

		SET @BookID = SCOPE_IDENTITY();

		-- Seed default reading status for all readers
		INSERT INTO reading_status (ReaderID, BookID, ReadingStatus, Rating)
		SELECT
			r.ReaderID,
			@BookID,
			'Unread',
			NULL
		FROM readers r;

		-- 4. Split authors into a table variable (author order may not be guaranteed with STRING_SPLIT)
		DECLARE @AuthorTable TABLE (
			AuthorOrder INT IDENTITY(1,1),
			AuthorName NVARCHAR(255)
		);

		INSERT INTO @AuthorTable (AuthorName)
		SELECT DISTINCT LTRIM(RTRIM(value))
		FROM STRING_SPLIT(@Authors, ',')
		WHERE LTRIM(RTRIM(value)) <> '';

		-- 5. Ensure each author exists
		INSERT INTO authors_new (AuthorName)
		SELECT a.AuthorName
		FROM @AuthorTable a
		WHERE NOT EXISTS (
			SELECT 1
			FROM authors_new an
			WHERE an.AuthorName = a.AuthorName
		);

		-- 6. Link authors to book
		INSERT INTO book_authors (BookID, AuthorID, AuthorOrder)
		SELECT
			@BookID,
			an.AuthorID,
			a.AuthorOrder
		FROM @AuthorTable a
		JOIN authors_new an
			ON an.AuthorName = a.AuthorName;

	-- 7. Process main genres
	IF @MainGenres IS NOT NULL AND LTRIM(RTRIM(@MainGenres)) <> ''
	BEGIN
		DECLARE @MainGenreTable TABLE (
			GenreName NVARCHAR(255) PRIMARY KEY
		);

		INSERT INTO @MainGenreTable (GenreName)
		SELECT DISTINCT LTRIM(RTRIM(value))
		FROM STRING_SPLIT(@MainGenres, ',')
		WHERE LTRIM(RTRIM(value)) <> '';

		INSERT INTO genres (GenreName)
		SELECT mg.GenreName
		FROM @MainGenreTable mg
		WHERE NOT EXISTS (
			SELECT 1
			FROM genres g
			WHERE g.GenreName = mg.GenreName
		);

		INSERT INTO book_genres (BookID, GenreID, GenreType)
		SELECT
			@BookID,
			g.GenreID,
			'Main'
		FROM @MainGenreTable mg
		JOIN genres g
			ON g.GenreName = mg.GenreName;
	END;

    -- 8. Process secondary genres
    IF @SecondaryGenres IS NOT NULL AND LTRIM(RTRIM(@SecondaryGenres)) <> ''
    BEGIN
        DECLARE @SecondaryGenreTable TABLE (
            GenreName NVARCHAR(255) PRIMARY KEY
        );

        INSERT INTO @SecondaryGenreTable (GenreName)
        SELECT DISTINCT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(@SecondaryGenres, ',')
        WHERE LTRIM(RTRIM(value)) <> '';

        INSERT INTO genres (GenreName)
        SELECT sg.GenreName
        FROM @SecondaryGenreTable sg
        WHERE NOT EXISTS (
            SELECT 1
            FROM genres g
            WHERE g.GenreName = sg.GenreName
        );

        INSERT INTO book_genres (BookID, GenreID, GenreType)
        SELECT
            @BookID,
            g.GenreID,
            'Secondary'
        FROM @SecondaryGenreTable sg
        JOIN genres g
            ON g.GenreName = sg.GenreName;
    END;

		COMMIT TRANSACTION;
	END TRY
	BEGIN CATCH
		IF @@TRANCOUNT > 0
			ROLLBACK TRANSACTION;

		THROW;
	END CATCH
END;
GO


--------------------------------------------------
-- SetReaderRating
-- Inserts a specified reader's rating for a book
-- Marks the book as read if not already set
--------------------------------------------------

CREATE OR ALTER PROCEDURE SetReaderRating
    @BookID INT,
    @ReaderName NVARCHAR(255),
    @Rating DECIMAL(4,2)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        DECLARE @ReaderID INT;

        -- Validate book exists
        IF NOT EXISTS (
            SELECT 1
            FROM books
            WHERE BookID = @BookID
        )
        BEGIN
            RAISERROR('Book not found.', 16, 1);
        END;

        -- Find reader
        SELECT @ReaderID = ReaderID
        FROM readers
        WHERE ReaderName = LTRIM(RTRIM(@ReaderName));

        IF @ReaderID IS NULL
        BEGIN
            RAISERROR('Reader not found.', 16, 1);
        END;

        -- Validate rating
        IF @Rating < 0 OR @Rating > 5
        BEGIN
            RAISERROR('Rating must be between 0 and 5.', 16, 1);
        END;

        -- Update existing row only
        UPDATE reading_status
        SET Rating = @Rating
        WHERE ReaderID = @ReaderID
          AND BookID = @BookID;

        IF @@ROWCOUNT = 0
        BEGIN
            RAISERROR('Reading status row not found for this reader and book.', 16, 1);
        END;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH
END;
GO


--------------------------------------------------
-- SetReadingStatus
-- Marks the current read status of a book for the specified reader
--------------------------------------------------

CREATE OR ALTER PROCEDURE SetReadingStatus
    @BookID INT,
    @ReaderName NVARCHAR(255),
    @ReadingStatus NVARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        DECLARE @ReaderID INT;

        IF @ReadingStatus NOT IN ('Unread', 'TBR', 'Reading', 'Read', 'DNF')
        BEGIN
            RAISERROR('ReadingStatus must be Unread, TBR, Reading, Read, or DNF.', 16, 1);
        END;

        -- Validate book exists
        IF NOT EXISTS (
            SELECT 1
            FROM books
            WHERE BookID = @BookID
        )
        BEGIN
            RAISERROR('Book not found.', 16, 1);
        END;

        -- Find reader
        SELECT @ReaderID = ReaderID
        FROM readers
        WHERE ReaderName = LTRIM(RTRIM(@ReaderName));

        IF @ReaderID IS NULL
        BEGIN
            RAISERROR('Reader not found.', 16, 1);
        END;

        IF EXISTS (
            SELECT 1
            FROM reading_status
            WHERE ReaderID = @ReaderID
              AND BookID = @BookID
        )
        BEGIN
            UPDATE reading_status
            SET ReadingStatus = @ReadingStatus,
                Rating = CASE
                            WHEN @ReadingStatus IN ('Unread', 'TBR', 'Reading') THEN NULL
                            ELSE Rating
                         END
            WHERE ReaderID = @ReaderID
              AND BookID = @BookID;
        END
        ELSE
        BEGIN
            INSERT INTO reading_status (ReaderID, BookID, ReadingStatus, Rating)
            VALUES (@ReaderID, @BookID, @ReadingStatus, NULL);
        END;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO


--------------------------------------------------
-- UpdateBookGenres
-- Updates the Main and Secondary genres for a specified book
-- Note that it will replace previous genre entries for this book, it does not add to the existing genres listed.
--------------------------------------------------

CREATE OR ALTER PROCEDURE UpdateBookGenres
    @BookID INT,
    @MainGenres NVARCHAR(MAX) = NULL,
    @SecondaryGenres NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        -- Validate book exists
        IF NOT EXISTS (
            SELECT 1
            FROM books
            WHERE BookID = @BookID
        )
        BEGIN
            RAISERROR('Book not found.', 16, 1);
        END;

        -- Remove existing genre links
        DELETE FROM book_genres
        WHERE BookID = @BookID;

        DECLARE @AllGenres TABLE (
            GenreName NVARCHAR(255) PRIMARY KEY
        );

        IF @MainGenres IS NOT NULL AND LTRIM(RTRIM(@MainGenres)) <> ''
        BEGIN
            INSERT INTO @AllGenres (GenreName)
            SELECT DISTINCT LTRIM(RTRIM(value))
            FROM STRING_SPLIT(@MainGenres, ',')
            WHERE LTRIM(RTRIM(value)) <> '';
        END;

        IF @SecondaryGenres IS NOT NULL AND LTRIM(RTRIM(@SecondaryGenres)) <> ''
        BEGIN
            INSERT INTO @AllGenres (GenreName)
            SELECT DISTINCT LTRIM(RTRIM(value))
            FROM STRING_SPLIT(@SecondaryGenres, ',')
            WHERE LTRIM(RTRIM(value)) <> ''
              AND NOT EXISTS (
                    SELECT 1
                    FROM @AllGenres ag
                    WHERE ag.GenreName = LTRIM(RTRIM(value))
              );
        END;

        INSERT INTO genres (GenreName)
        SELECT ag.GenreName
        FROM @AllGenres ag
        WHERE NOT EXISTS (
            SELECT 1
            FROM genres g
            WHERE g.GenreName = ag.GenreName
        );

        IF @MainGenres IS NOT NULL AND LTRIM(RTRIM(@MainGenres)) <> ''
        BEGIN
            INSERT INTO book_genres (BookID, GenreID, GenreType)
            SELECT DISTINCT
                @BookID,
                g.GenreID,
                'Main'
            FROM STRING_SPLIT(@MainGenres, ',') s
            JOIN genres g
                ON g.GenreName = LTRIM(RTRIM(s.value))
            WHERE LTRIM(RTRIM(s.value)) <> '';
        END;

        IF @SecondaryGenres IS NOT NULL AND LTRIM(RTRIM(@SecondaryGenres)) <> ''
        BEGIN
            INSERT INTO book_genres (BookID, GenreID, GenreType)
            SELECT DISTINCT
                @BookID,
                g.GenreID,
                'Secondary'
            FROM STRING_SPLIT(@SecondaryGenres, ',') s
            JOIN genres g
                ON g.GenreName = LTRIM(RTRIM(s.value))
            WHERE LTRIM(RTRIM(s.value)) <> '';
        END;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH
END;
GO


--------------------------------------------------
-- SetMiniBookStatus
-- Updates the IsPrinted and IsCrafted status for a mini book for a specified reader
--------------------------------------------------

CREATE OR ALTER PROCEDURE SetMiniBookStatus
    @BookID INT,
    @ReaderName NVARCHAR(255),
    @IsPrinted BIT,
    @IsCrafted BIT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        DECLARE @ReaderID INT;

        -- Validate book exists
        IF NOT EXISTS (
            SELECT 1
            FROM books
            WHERE BookID = @BookID
        )
        BEGIN
            RAISERROR('Book not found.', 16, 1);
        END;

        -- Find reader
        SELECT @ReaderID = ReaderID
        FROM readers
        WHERE ReaderName = LTRIM(RTRIM(@ReaderName));

        IF @ReaderID IS NULL
        BEGIN
            RAISERROR('Reader not found.', 16, 1);
        END;

        -- Prevent impossible state
        IF @IsCrafted = 1 AND @IsPrinted = 0
        BEGIN
            RAISERROR('A mini book cannot be crafted unless it has been printed.', 16, 1);
        END;

        -- Update if row already exists
        IF EXISTS (
            SELECT 1
            FROM mini_book_status
            WHERE ReaderID = @ReaderID
              AND BookID = @BookID
        )
        BEGIN
            UPDATE mini_book_status
            SET IsPrinted = @IsPrinted,
                IsCrafted = @IsCrafted
            WHERE ReaderID = @ReaderID
              AND BookID = @BookID;
        END
        ELSE
        BEGIN
            INSERT INTO mini_book_status (
                ReaderID,
                BookID,
                IsPrinted,
                IsCrafted
            )
            VALUES (
                @ReaderID,
                @BookID,
                @IsPrinted,
                @IsCrafted
            );
        END;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH
END;
GO