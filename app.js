// State
let allBooks = [];
let fuse = null;
let currentGenreFilter = '';
let currentSort = 'title';

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

    // Update stats
    document.getElementById('stats').textContent = `${data.count} books`;

    // Initialize Fuse.js for search
    fuse = new Fuse(allBooks, {
      keys: ['title', 'author', 'genres'],
      threshold: 0.3,
      ignoreLocation: true,
      useExtendedSearch: false
    });

    // Populate genre filter
    populateGenreFilter();

    // Render initial list
    render(allBooks);

    // Attach event listeners
    document.getElementById('search').addEventListener('input', handleSearch);
    document.getElementById('genre-filter').addEventListener('change', handleGenreFilter);
    document.getElementById('sort').addEventListener('change', handleSort);

  } catch (error) {
    console.error('Failed to load books:', error);
    document.getElementById('results').innerHTML =
      '<p class="no-results">Failed to load books. Please try again later.</p>';
  }
}

// Populate genre filter dropdown with unique genres
function populateGenreFilter() {
  const genreSet = new Set();

  allBooks.forEach(book => {
    if (book.genres && Array.isArray(book.genres)) {
      book.genres.forEach(genre => genreSet.add(genre));
    }
  });

  const genres = Array.from(genreSet).sort();
  const select = document.getElementById('genre-filter');

  genres.forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    select.appendChild(option);
  });
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

  render(applyFiltersAndSort(filtered));
}

// Handle genre filter change
function handleGenreFilter(event) {
  currentGenreFilter = event.target.value;
  triggerRender();
}

// Handle sort change
function handleSort(event) {
  currentSort = event.target.value;
  triggerRender();
}

// Trigger re-render with current search query
function triggerRender() {
  const searchQuery = document.getElementById('search').value.trim();

  let filtered;
  if (!searchQuery) {
    filtered = allBooks;
  } else {
    const results = fuse.search(searchQuery);
    filtered = results.map(result => result.item);
  }

  render(applyFiltersAndSort(filtered));
}

// Apply genre filter and sorting
function applyFiltersAndSort(books) {
  let result = books;

  // Apply genre filter
  if (currentGenreFilter) {
    result = result.filter(book =>
      book.genres && book.genres.includes(currentGenreFilter)
    );
  }

  // Apply sorting
  result = [...result]; // Create a copy to avoid mutating input
  result.sort((a, b) => {
    switch (currentSort) {
      case 'title':
        return a.title.localeCompare(b.title);
      case 'author':
        return a.author.localeCompare(b.author);
      case 'year':
        return (b.year_published || 0) - (a.year_published || 0);
      default:
        return 0;
    }
  });

  return result;
}

// Render books to the page
function render(books) {
  const container = document.getElementById('results');

  if (books.length === 0) {
    container.innerHTML = '<p class="no-results">No books found</p>';
    return;
  }

  container.innerHTML = books.map(book => createBookCard(book)).join('');
}

// Create HTML for a single book card
function createBookCard(book) {
  const coverHtml = book.cover_url
    ? `<img src="${book.cover_url}" alt="${escapeHtml(book.title)} cover" onerror="this.parentElement.innerHTML='${getPlaceholderInitial(book.title)}';">`
    : getPlaceholderInitial(book.title);

  const genresHtml = book.genres && book.genres.length > 0
    ? `<div class="book-genres">
         ${book.genres.map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`).join('')}
       </div>`
    : '';

  const metaParts = [];
  if (book.year_published) {
    metaParts.push(book.year_published);
  }
  if (book.geo_region) {
    metaParts.push(book.geo_region);
  }

  const metaHtml = metaParts.length > 0
    ? `<div class="book-meta">
         <span class="meta-item">${metaParts.join(' • ')}</span>
       </div>`
    : '';

  const confidenceClass = book.match_confidence === 'low' ? ' confidence-low' : '';
  const titleLink = book.open_library_url
    ? `<a href="${book.open_library_url}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a>`
    : escapeHtml(book.title);

  return `
    <div class="book-card${confidenceClass}">
      <div class="book-cover">
        ${coverHtml}
      </div>
      <div class="book-info">
        <h2 class="book-title">${titleLink}</h2>
        <p class="book-author">${escapeHtml(book.author)}</p>
        ${metaHtml}
        ${genresHtml}
      </div>
    </div>
  `;
}

// Get placeholder initial for books without covers
function getPlaceholderInitial(title) {
  const initial = title.charAt(0).toUpperCase();
  return `<div class="placeholder">${initial}</div>`;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
