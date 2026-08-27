import { useEffect, useState } from "react";

export default function BookList({ query }) {
  const [books, setBooks] = useState(null);     // null | array
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!query) return;

    let ignore = false;

    async function loadBooks() {
      try {
        setLoading(true);
        setError(null);
        setBooks(null);

        const response = await fetch(
          `https://openlibrary.org/search.json?q=${encodeURIComponent(query)}`
        );

        if (!response.ok) {
          throw new Error("Search request failed");
        }

        const data = await response.json();
        const results = data.docs ? data.docs.slice(0, 10) : [];

        if (!ignore) {
          setBooks(results);
          setError(null);
        }
      } catch (err) {
        if (ignore) return;

        console.error("Book search error:", err);

        setBooks([]);
        setError("Something went wrong. Please try again.");
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadBooks();

    return () => {
      ignore = true; // stale request protection
    };
  }, [query]);

  // Render states
  if (loading) {
    return <p>Loading…</p>;
  }

  if (error) {
    return <p className="error-message">{error}</p>;
  }

  if (books && books.length === 0) {
    return <p>No books found.</p>;
  }

  if (books && books.length > 0) {
    return (
      <ul className="book-list">
        {books.map((book, index) => {
          const coverId = book.cover_i;
          const coverUrl = coverId
            ? `https://covers.openlibrary.org/b/id/${coverId}-L.jpg`
            : null;

          return (
            <li key={book.key || `${book.title}-${index}`} className="book-item">
              {coverUrl && (
                <img
                  src={coverUrl}
                  alt={book.title || "Book cover"}
                  className="book-cover"
                />
              )}

              <div className="book-info">
                <h3>{book.title || "No title available"}</h3>

                {book.author_name && (
                  <p>
                    <strong>Author:</strong> {book.author_name.join(", ")}
                  </p>
                )}

                {book.first_publish_year && (
                  <p>
                    <strong>First published:</strong> {book.first_publish_year}
                  </p>
                )}

                {book.subject && (
                  <p>
                    <strong>Subjects:</strong> {book.subject.slice(0, 3).join(", ")}
                  </p>
                )}

                {book.key && (
                  <a
                    href={`https://openlibrary.org${book.key}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View on Open Library
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    );
  }

  return null;
}
