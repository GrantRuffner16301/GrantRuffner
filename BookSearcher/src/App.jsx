import { useState } from "react";
import "./App.css";
import BookList from "./BookList";

export default function App() {
  const [liveQuery, setLiveQuery] = useState("react");
  const [submittedQuery, setSubmittedQuery] = useState("react");

  function handleSubmit(e) {
    e.preventDefault();

    const term = liveQuery.trim();
    if (!term) return;

    setSubmittedQuery(term); // promote live → submitted
  }

  return (
    <div className="page-shell">
      <h1>Book Search</h1>

      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="text"
          className="search-input"
          placeholder="Type a book title..."
          value={liveQuery}
          onChange={(e) => setLiveQuery(e.target.value)}
        />
        <button type="submit" className="search-button">
          Search
        </button>
      </form>

      <BookList query={submittedQuery} />
    </div>
  );
}
