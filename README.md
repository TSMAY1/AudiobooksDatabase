# Audiobooks Database Schema

This project implements a relational SQL database that tracks audiobook metadata, reader activity, genres, and Cozy Corner Book Club selections.

It supports:

- reader-specific ratings
- many-to-many relationships (authors, genres)
- normalized schema design
- reusable views and stored procedures for common workflows

This project began as a hands-on SQL learning exercise and evolved into a fully normalized, queryable database system.

## Getting Started

To run this project locally in SQL Server:

1. Create a new database:

```sql
CREATE DATABASE Audiobooks;
```

2. Run the schema:

```plaintext
schema.sql
```

3. Insert sample data:

```plaintext
seed_data.sql
```

4. (Optional) Create reusable objects:
```plaintext
views.sql  
procedures.sql
```

5. Explore queries:
```plaintext
basic_queries.sql  
analytics_queries.sql
```

## Project Structure

├── schema.sql                -- Table definitions and relationships
├── seed_data.sql             -- Sample dataset for testing
├── basic_queries.sql         -- Lookup and retrieval queries
├── analytics_queries.sql     -- Aggregations and insights
├── views.sql                 -- Reusable query abstractions
├── procedures.sql            -- Parameterized database operations


## Core Tables

**books** - audiobook metadata

**authors_new** - normalized author list

**book_authors** - many-to-many book to author

**series** - book series

**readers** - users

**reading_status** - reader activity and ratings

**genres** - genre reference

**book_genres** - many-to-many book to genre

**cozy_corner_book_club** - monthly book club records

**bookclub_monthly_books** - book selections per month

**bookclub_calendars** - yearly planning data

## Relationships

- A book belongs to one series

- A book can have multiple authors via `book_authors`

- A reader interacts with books via `reading_status`

- Books can have multiple genres via `book_genres`

- book club selections are tracked via `bookclub_monthly_books`

## Diagram

```plaintext

authors_new
   │
   └───< book_authors >─── books >─── series
                                │
                                ├───< book_genres >─── genres
                                │
                                ├───< reading_status >─── readers
                                │
                                └───< bookclub_monthly_books >─── cozy_corner_book_club

bookclub_calendars

```

## Example Query (Using Views)

*Example: Display books read by a specific reader with aggregated authors*
```sql
SELECT
    Authors,
    Title,
    SeriesName,
    BookNumber,
    Rating
FROM vw_tori_read_books
ORDER BY Authors, SeriesName, BookNumber;
GO
```

## Views

Views were used to simplify complex joins and improve query readability

Key examples:

`vw_book_details`
→ Aggregated book metadata (authors, series, order)
`vw_reader_books`
→ Reader activity across all books
`vw_bookclub_books`
→ Book club selections with display order
`vw_angela_read_books`, `vw_tori_read_books`
→ Reader-specific book lists with ratings

## Stored Procedures

Created procedures to utilize reusable, parameterized operations

`AddBook`
→ Inserts a book and links authors and genres
`SetReaderRating`
→ Updates or inserts a reader’s rating
`SetReadStatus`
→ Marks a book as read/unread
`UpdateBookGenres`
→ Replaces a book’s genre assignments

## Analytics Highlights

Example insights supported by this database:

- Books read per reader
- Shared books between readers
- Average ratings per reader
- Most-read genres
- Highest-rated books
- Reader-specific top books

## Schema Refactor: Before vs After

#### Before (Initial Design)

In the original schema, each book was linked to a single author using a direct foreign key:

authors ───< books >─── series

- `books.AuthorID` referenced `authors.AuthorID`

- Each row in `authors` sometimes contained multiple authors in a single string

        Example: "A.R. Capetta, Cory McCarthy"

- This made it difficult to:

    - Accurately query individual authors

    - Handle co-authored books

    - Prevent duplicate or inconsistent author entries


#### After (Normalized Design)

The schema was refactored to support a proper many-to-many relationship between books and authors:

authors_new ───< book_authors >─── books >─── series

- `authors_new` contains one row per individual author

- `book_authors` acts as a junction table:

    - One book -> many authors

    - One author -> many books

## Key Highlights

- Fully normalized relational schema
- Many-to-many relationships (authors, genres)
- Reader-specific rating system
- Aggregation-heavy analytics queries
- Reusable views for simplified querying
- Stored procedures for real-world workflows

## Future Improvements

- Refactor queries to rename authors_new to authors

- Add role support (e.g., Author, Translator, Narrator) for contributors

- Expand analytics (e.g., top authors, co-author frequency, trends)

- Connect yearly calendars to monthly book club data

## Notes

This project reflects iterative database design improvements and real-world data challenges, including normalization, data cleaning, and query optimization.