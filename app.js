// State
let allBooks = [];
let fuse = null;

// Initialize the app
async function init() {
  try {
    // Fetch books.json
    const response = await fetch('./data/books.json');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    allBooks = data.books;

    // Sort by author by default
    allBooks.sort((a, b) => a.author.localeCompare(b.author));

    // Initialize Fuse.js for search
    fuse = new Fuse(allBooks, {
      keys: ['title', 'author', 'genres'],
      threshold: 0.3,
      ignoreLocation: true,
      useExtendedSearch: false
    });

    // Render initial list
    render(allBooks);

    // Attach event listeners
    document.getElementById('search').addEventListener('input', handleSearch);
    document.getElementById('search').addEventListener('keydown', handleKeyDown);

  } catch (error) {
    console.error('Failed to load books:', error);
    document.getElementById('results').innerHTML =
      '<p class="no-results">Failed to load catalog.</p>';
  }
}

// Handle search input
function handleSearch(event) {
  const query = event.target.value.trim();

  let filtered;
  if (!query) {
    filtered = allBooks;
  } else {
    const results = fuse.search(query);
    filtered = results.map(result => result.item);
  }

  render(filtered);
}

// Handle Enter key to trigger search
function handleKeyDown(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    handleSearch(event);
  }
}

// Render books to the page
function render(books) {
  const container = document.getElementById('results');

  if (books.length === 0) {
    container.innerHTML = '<p class="no-results">No volumes found.</p>';
    return;
  }

  container.innerHTML = books.map(book => createBookEntry(book)).join('');
}

// Create HTML for a single book entry in archival style
function createBookEntry(book) {
  const metaParts = [];

  if (book.year_published) {
    metaParts.push(book.year_published);
  }
  if (book.geo_region) {
    metaParts.push(book.geo_region);
  }

  const metaHtml = metaParts.length > 0
    ? `<p class="book-meta">${metaParts.join('<span class="separator">·</span>')}</p>`
    : '';

  const titleText = toTitleCase(book.title);
  const titleContent = book.books_url
    ? `<a href="${book.books_url}" target="_blank" rel="noopener">${escapeHtml(titleText)}</a>`
    : escapeHtml(titleText);

  return `
    <div class="book-entry">
      <p class="book-author">${escapeHtml(book.author)}</p>
      <p class="book-title">${titleContent}</p>
      ${metaHtml}
    </div>
  `;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Convert text to title case
function toTitleCase(text) {
  const smallWords = new Set([
    'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'nor',
    'of', 'on', 'or', 'so', 'the', 'to', 'up', 'yet', 'via'
  ]);

  return text.split(' ').map((word, index) => {
    if (!word) return word;
    const lower = word.toLowerCase();
    // Always capitalize first word, otherwise check if it's a small word
    if (index === 0 || !smallWords.has(lower)) {
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    }
    return lower;
  }).join(' ');
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
