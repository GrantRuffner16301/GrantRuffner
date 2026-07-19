# 📚 Web Book Search

A sleek, modern web application for searching and discovering books using the Open Library API. Built with vanilla JavaScript, HTML, and CSS, featuring a cyberpunk-inspired dark theme with neon accents.

## Features

- 🔍 **Real-time Book Search** - Search for books by title using the Open Library API
- 🎨 **Cyberpunk Design** - Dark theme with neon blue and red accents, animated grid background
- ⚡ **Async Fetch** - Non-blocking search requests for smooth user experience
- 🛡️ **Error Handling** - Graceful error messages when searches fail
- 📱 **Responsive Layout** - Works across different screen sizes
- 📖 **Top 10 Results** - Displays up to 10 most relevant search results

## Project Structure

```
Web_Book_Search/
├── index.html      # Main HTML markup and structure
├── main.js         # Search logic and API interaction
├── styles.css      # Styling and cyberpunk theme
└── README.md       # This file
```

## Technologies Used

- **HTML5** - Semantic markup and structure
- **CSS3** - Advanced styling with animations and gradients
- **JavaScript (ES6+)** - Async/await, DOM manipulation
- **Open Library API** - Free book data source

## How to Use

1. Clone or download the repository
2. Open `index.html` in your web browser
3. Enter a book title in the search input field
4. Click the "Search" button or press Enter
5. View results displayed in the list below

## API Reference

This project uses the **Open Library Search API**:
- Endpoint: `https://openlibrary.org/search.json?q={query}`
- Free and requires no authentication
- Returns book metadata including titles, authors, and publication info

## File Descriptions

### `index.html`
Basic HTML structure containing:
- Search input field for book queries
- Search button to trigger the search
- Unordered list to display search results

### `main.js`
Core JavaScript functionality:
- `handleSearch()` - Validates input and initiates API call
- `searchBooks()` - Async function that fetches data from Open Library API
- Error handling and DOM manipulation
- Displays "No results found" or error messages as needed

### `styles.css`
Comprehensive styling featuring:
- Dark background with animated grid overlay
- Neon blue (#1220df) and red (#ff073c) color scheme
- Glowing text effects and transitions
- Hover animations on interactive elements
- Responsive design for various screen sizes

## Future Enhancements

- Add book cover images from Open Library API
- Display author names and publication years
- Add filtering options (by year, author, etc.)
- Implement keyboard shortcuts (Enter to search)
- Add search history/favorites feature
- Display book ratings and descriptions
- Add pagination for more results

## License

This project is part of the GrantRuffner portfolio repository.

---

**Created for learning and building web applications with modern JavaScript and API integration.**
