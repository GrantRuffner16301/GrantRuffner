const button = document.getElementById("search-button");
const input = document.getElementById("search-input");

button.addEventListener("click", handleSearch);

function handleSearch() {
  const term = input.value.trim();

  if (term === "") {
    alert("Please enter a search term.");
    return;
  }

  const url = "https://openlibrary.org/search.json?q=" + encodeURIComponent(term);

  searchBooks(url);
}
async function searchBooks(url) {
  try {
    const response = await fetch(url);
    const data = await response.json();

    const results = data.docs.slice(0, 10);

    const list = document.getElementById("book-list");
    list.innerHTML = "";

    if (results.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No results found.";
      list.appendChild(li);
      return;
    }

    for (const book of results) {
      const li = document.createElement("li");
      li.textContent = book.title ? book.title : "No title available";
      list.appendChild(li);
    }

  } catch (err) {
    console.error("Search failed:", err);

    const list = document.getElementById("book-list");
    list.innerHTML = "";

    const li = document.createElement("li");
    li.textContent = "Something went wrong. Please try again.";
    list.appendChild(li);
  }
}
