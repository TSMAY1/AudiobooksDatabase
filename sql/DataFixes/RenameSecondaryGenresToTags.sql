SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @ConstraintName SYSNAME;
    DECLARE @Sql NVARCHAR(MAX);

    SELECT TOP (1)
        @ConstraintName = cc.name
    FROM sys.check_constraints cc
    WHERE cc.parent_object_id = OBJECT_ID(N'dbo.book_genres')
      AND cc.definition LIKE N'%GenreType%';

    IF @ConstraintName IS NOT NULL
    BEGIN
        SET @Sql = N'ALTER TABLE dbo.book_genres DROP CONSTRAINT '
            + QUOTENAME(@ConstraintName) + N';';
        EXEC sys.sp_executesql @Sql;
    END;

    UPDATE dbo.book_genres
    SET GenreType = N'Tag'
    WHERE GenreType = N'Secondary';

    IF EXISTS (
        SELECT 1
        FROM dbo.book_genres
        WHERE GenreType NOT IN (N'Main', N'Tag')
    )
    BEGIN
        THROW 50001, 'Unexpected GenreType value found. Migration cancelled.', 1;
    END;

    ALTER TABLE dbo.book_genres WITH CHECK
        ADD CONSTRAINT CK_book_genres_GenreType
        CHECK (GenreType IN (N'Main', N'Tag'));

    ALTER TABLE dbo.book_genres
        CHECK CONSTRAINT CK_book_genres_GenreType;

    COMMIT TRANSACTION;

    SELECT
        GenreType,
        COUNT(*) AS AssignmentCount
    FROM dbo.book_genres
    GROUP BY GenreType
    ORDER BY GenreType;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
