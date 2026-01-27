# Book Database Implementation Plan

A static, searchable personal book catalog hosted on GitHub Pages. The user maintains only title/author in a Dropbox CSV; all other metadata (ISBN, publication year, genre, cover images) is enriched automatically via the Open Library API.

## Architecture Overview

```
┌─────────────────┐      ┌──────────────────────────────┐      ┌─────────────────┐
│  Dropbox        │      │  GitHub Action               │      │  GitHub Pages   │
│  books.csv      │ ──▶  │  1. Fetch CSV from Dropbox   │ ──▶  │  static site    │
│  (title,author  │      │  2. Enrich via Open Library  │      │  + books.json   │
│   + optional    │      │  3. Generate books.json      │      │                 │
│   overrides)    │      │  4. Deploy to GitHub Pages   │      └─────────────────┘
└─────────────────┘      └──────────────────────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────────┐
                         │  cache/enrichment_cache.json │
                         │  (committed to repo)         │
                         │  - Stores API responses      │
                         │  - Avoids re-fetching        │
                         │  - Persists across builds    │
                         └──────────────────────────────┘
```

### Why the Cache?

Without caching, every build would query Open Library ~600 times:
- Slow (~10+ minutes)
- Risks rate limiting
- Wasteful (book metadata rarely changes)

The cache stores enrichment data keyed by normalized title+author. On each build:
1. New books → query API, add to cache
2. Existing books → use cached data
3. Cache committed to repo for persistence

## Repository Structure

```
book-catalog/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Action for build + deploy
├── src/
│   ├── index.html              # Main page
│   ├── styles.css              # Minimal styling
│   └── app.js                  # Search + rendering logic
├── scripts/
│   ├── build.py                # Main build orchestrator
│   └── enrich.py               # Open Library API enrichment
├── cache/
│   └── enrichment_cache.json   # Cached API responses (committed)
├── data/
│   └── .gitkeep                # books.json generated here at build time
├── requirements.txt            # Python: requests
└── README.md
```

## Data Schema

### Source: library.csv (in Dropbox)

The user maintains this minimal CSV. Only title and author are required.

```csv
title,author,isbn_override,geo_region,sort_year,sort_basis,read_by_colin,read_by_kaitlyn
Thinking Fast and Slow,Daniel Kahneman,,general non-fiction,2011,publication,TRUE,FALSE
The Warmth of Other Suns,Isabel Wilkerson,,american south,1930,subject,FALSE,TRUE
Some Obscure Book,Unknown Author,9781234567890,general non-fiction,2000,publication,FALSE,FALSE
```

**Required fields:**
- `title` (string) — book title (approximate; used for API lookup; official title from Open Library will be displayed)
- `author` (string) — author name(s) (approximate; used for API lookup; official author from Open Library will be displayed)

**Optional user-maintained fields:**
- `geo_region` (string) -- geographic region based on author's birthplace (fiction) or subject (non-fiction)
- `sort_year` (string) -- year of author's birth (fiction) or subject's time period (non-fiction)
- `sort_basis` (string) -- explanation for sort_year
- `isbn_override` (string) — manually specify ISBN if auto-lookup fails or picks wrong edition
- `read_by_colin` (boolean) -- whether Colin has read the book
- `read_by_kaitlyn` (boolean) -- ""

All other metadata (ISBN, publication year, genres, cover) is fetched automatically.

### Enrichment Cache: cache/enrichment_cache.json

Stores Open Library API responses, keyed by normalized title+author.

```json
{
  "thinking fast and slow|daniel kahneman": {
    "official_title": "Thinking, Fast and Slow",
    "official_author": "Daniel Kahneman",
    "isbn": "9780374533557",
    "year_published": 2011,
    "subjects": ["Psychology", "Decision making", "Thought and thinking"],
    "open_library_work_key": "/works/OL15994480W",
    "open_library_edition_key": "/books/OL24817132M",
    "fetched_at": "2025-01-15T10:30:00Z",
    "match_confidence": "high"
  },
  "some obscure book|unknown author": {
    "official_title": null,
    "official_author": null,
    "isbn": null,
    "year_published": null,
    "subjects": [],
    "open_library_work_key": null,
    "open_library_edition_key": null,
    "fetched_at": "2025-01-15T10:31:00Z",
    "match_confidence": "none",
    "error": "No results found"
  }
}
```

**Cache key format:** `lowercase(title)|lowercase(author)`

**Cache entry fields:**
- `official_title` — canonical title from Open Library, null if not found
- `official_author` — canonical author name(s) from Open Library, null if not found
- `isbn` — ISBN-13 preferred, ISBN-10 fallback, null if not found
- `year_published` — first publication year
- `subjects` — raw subjects from Open Library (will be cleaned/normalized)
- `open_library_work_key` — for linking to Open Library page
- `open_library_edition_key` — specific edition matched
- `fetched_at` — timestamp for cache invalidation (optional future feature)
- `match_confidence` — "high", "medium", "low", or "none"
- `error` — error message if lookup failed

### Output: data/books.json

Generated by build script. Merges user data + enrichment data.

```json
{
  "generated_at": "2025-01-15T10:30:00Z",
  "count": 600,
  "books": [
    {
      "id": "abc123",
      "title": "Thinking, Fast and Slow",
      "author": "Daniel Kahneman",
      "user_title": "Thinking Fast and Slow",
      "user_author": "Daniel Kahneman",
      "isbn": "9780374533557",
      "year_published": 2011,
      "genres": ["Psychology", "Cognitive Science"],
      "geo_region": "none",
      "sort_year": 2011,
      "sort_basis": "publication",
      "read_by_colin": false,
      "read_by_kaitlyn": false,
      "cover_url": "https://covers.openlibrary.org/b/isbn/9780374533557-M.jpg",
      "open_library_url": "https://openlibrary.org/works/OL15994480W",
      "match_confidence": "high",
      "search_text": "thinking, fast and slow daniel kahneman psychology cognitive science"
    }
  ]
}
```

**Field definitions:**
- `id` — short hash for stable DOM keys
- `title` — **official title from Open Library** (falls back to user_title if not found)
- `author` — **official author from Open Library** (falls back to user_author if not found)
- `user_title` — title as entered by user in CSV (for reference/debugging)
- `user_author` — author as entered by user in CSV (for reference/debugging)
- `isbn` — from enrichment (or isbn_override if provided)
- `year_published` — from enrichment
- `genres` — cleaned/normalized from Open Library subjects
- `geo_region` — from user CSV
- `sort_year` — from user CSV
- `sort_basis` — from user CSV
- `read_by_colin` — from user CSV
- `read_by_kaitlyn` — from user CSV
- `cover_url` — constructed from ISBN, null if no ISBN
- `open_library_url` — link to book page (if matched)
- `match_confidence` — from enrichment cache
- `search_text` — lowercase concatenation of official title, author, and genres (used for search)

## Build Scripts

### scripts/build.py (Main Orchestrator)

Responsibilities:
1. Fetch CSV from Dropbox shared link: https://www.dropbox.com/scl/fi/nxlkl090aewe3qvebr3f7/library.csv?rlkey=jv1we3yba15l5uf4u9ikwhl5x&st=s8jqnzj8&dl=0
2. Parse and validate user data
3. Call enrichment for new/changed books
4. Merge user data + enrichment data
5. Generate cleaned genres
6. Output `data/books.json`
7. Commit updated cache (if running in CI)

```python
# Pseudocode structure

def main():
    # 1. Fetch CSV from Dropbox
    csv_url = os.environ.get('DROPBOX_URL')
    raw_books = fetch_and_parse_csv(csv_url)
    
    # 2. Load existing cache
    cache = load_cache('cache/enrichment_cache.json')
    
    # 3. Identify books needing enrichment
    to_enrich = []
    for book in raw_books:
        cache_key = make_cache_key(book['title'], book['author'])
        if cache_key not in cache:
            to_enrich.append(book)
    
    # 4. Enrich new books (with rate limiting)
    new_enrichments = enrich_books(to_enrich)  # calls enrich.py
    cache.update(new_enrichments)
    
    # 5. Save updated cache
    save_cache(cache, 'cache/enrichment_cache.json')
    
    # 6. Merge and generate final JSON
    books_json = []
    for book in raw_books:
        cache_key = make_cache_key(book['title'], book['author'])
        enrichment = cache.get(cache_key, {})

        # isbn_override takes precedence
        isbn = book.get('isbn_override') or enrichment.get('isbn')

        # Use official title/author from enrichment, fallback to user values
        display_title = enrichment.get('official_title') or book['title']
        display_author = enrichment.get('official_author') or book['author']

        books_json.append({
            'id': generate_id(book),
            'title': display_title,
            'author': display_author,
            'user_title': book['title'],
            'user_author': book['author'],
            'isbn': isbn,
            'year_published': enrichment.get('year_published'),
            'genres': clean_genres(enrichment.get('subjects', [])),
            'geo_region': book.get('geo_region'),
            'sort_year': book.get('sort_year'),
            'sort_basis': book.get('sort_basis'),
            'read_by_colin': book.get('read_by_colin'),
            'read_by_kaitlyn': book.get('read_by_kaitlyn'),
            'cover_url': make_cover_url(isbn),
            'open_library_url': make_ol_url(enrichment),
            'match_confidence': enrichment.get('match_confidence', 'none'),
            'search_text': make_search_text(display_title, display_author, ...)
        })
    
    # 7. Write output
    output = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'count': len(books_json),
        'books': books_json
    }
    write_json(output, 'data/books.json')
```

### scripts/enrich.py (Open Library API Client)

Responsibilities:
1. Query Open Library Search API
2. Parse and normalize results
3. Handle rate limiting (1 request/second)
4. Assess match confidence
5. Return enrichment data

#### Open Library API Usage

**Search endpoint:**
```
GET https://openlibrary.org/search.json?title={title}&author={author}&limit=5
```

**Response structure:**
```json
{
  "numFound": 12,
  "docs": [
    {
      "key": "/works/OL15994480W",
      "title": "Thinking, Fast and Slow",
      "author_name": ["Daniel Kahneman"],
      "first_publish_year": 2011,
      "isbn": ["9780374533557", "0374533555", ...],
      "subject": ["Psychology", "Decision making", ...],
      "edition_key": ["OL24817132M", ...]
    }
  ]
}
```

#### Enrichment Logic

```python
# Pseudocode

def enrich_book(title: str, author: str) -> dict:
    # 1. Query API
    params = {
        'title': title,
        'author': author,
        'limit': 5
    }
    response = requests.get('https://openlibrary.org/search.json', params=params)
    data = response.json()
    
    if data['numFound'] == 0:
        return {
            'official_title': None,
            'official_author': None,
            'isbn': None,
            'year_published': None,
            'subjects': [],
            'open_library_work_key': None,
            'open_library_edition_key': None,
            'match_confidence': 'none',
            'error': 'No results found',
            'fetched_at': datetime.utcnow().isoformat() + 'Z'
        }
    
    # 2. Score and rank results
    best_match = None
    best_score = 0
    
    for doc in data['docs']:
        score = compute_match_score(title, author, doc)
        if score > best_score:
            best_score = score
            best_match = doc
    
    # 3. Determine confidence
    if best_score >= 0.9:
        confidence = 'high'
    elif best_score >= 0.7:
        confidence = 'medium'
    elif best_score >= 0.5:
        confidence = 'low'
    else:
        confidence = 'none'
    
    # 4. Extract best ISBN (prefer ISBN-13)
    isbn = select_best_isbn(best_match.get('isbn', []))

    # 5. Extract official title and author
    official_title = best_match.get('title')
    # Combine all author names into a single string
    author_names = best_match.get('author_name', [])
    official_author = ', '.join(author_names) if author_names else None

    # 6. Return enrichment data
    return {
        'official_title': official_title,
        'official_author': official_author,
        'isbn': isbn,
        'year_published': best_match.get('first_publish_year'),
        'subjects': best_match.get('subject', [])[:10],  # limit to top 10
        'open_library_work_key': best_match.get('key'),
        'open_library_edition_key': best_match.get('edition_key', [None])[0],
        'match_confidence': confidence,
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }

def compute_match_score(query_title, query_author, doc):
    """Score 0-1 based on title and author similarity."""
    from difflib import SequenceMatcher
    
    title_score = SequenceMatcher(
        None, 
        query_title.lower(), 
        doc.get('title', '').lower()
    ).ratio()
    
    doc_authors = ' '.join(doc.get('author_name', [])).lower()
    author_score = SequenceMatcher(
        None,
        query_author.lower(),
        doc_authors
    ).ratio()
    
    # Weight title slightly higher
    return (title_score * 0.6) + (author_score * 0.4)

def select_best_isbn(isbn_list):
    """Prefer ISBN-13, fallback to ISBN-10."""
    isbn_13 = [i for i in isbn_list if len(i) == 13 and i.isdigit()]
    isbn_10 = [i for i in isbn_list if len(i) == 10]
    
    if isbn_13:
        return isbn_13[0]
    if isbn_10:
        return isbn_10[0]
    return None
```

#### Rate Limiting

Open Library asks for 1 request/second max. Implement with simple sleep:

```python
import time

def enrich_books(books: list) -> dict:
    results = {}
    for i, book in enumerate(books):
        if i > 0:
            time.sleep(1.1)  # slightly over 1s to be safe
        
        cache_key = make_cache_key(book['title'], book['author'])
        results[cache_key] = enrich_book(book['title'], book['author'])
        
        # Log progress
        print(f"[{i+1}/{len(books)}] {book['title']} - {results[cache_key]['match_confidence']}")
    
    return results
```

#### Genre Cleaning

Open Library subjects are messy. Clean them up:

```python
# Subjects to ignore (too generic or not useful)
IGNORE_SUBJECTS = {
    'accessible book',
    'protected daisy',
    'in library',
    'overdrive',
    'fiction',
    'nonfiction',
    'general',
    'literary',
    'literature'
}

# Map variations to canonical names
SUBJECT_MAP = {
    'sci-fi': 'Science Fiction',
    'science fiction': 'Science Fiction',
    'self-help': 'Self-Help',
    'selfhelp': 'Self-Help',
    # ... add more as needed
}

def clean_genres(subjects: list) -> list:
    """Clean and deduplicate subjects into usable genres."""
    cleaned = []
    seen = set()
    
    for subject in subjects:
        # Lowercase for comparison
        lower = subject.lower().strip()
        
        # Skip ignored
        if lower in IGNORE_SUBJECTS:
            continue
        
        # Skip if contains numbers (often "Fiction, 1900-1999" type junk)
        if any(c.isdigit() for c in subject):
            continue
        
        # Apply mapping or title-case
        canonical = SUBJECT_MAP.get(lower, subject.title())
        
        # Dedupe
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            cleaned.append(canonical)
    
    return cleaned[:5]  # Limit to 5 genres
```

### Dropbox Link Handling

Dropbox shared links end in `?dl=0`. Transform for direct download:

```python
def transform_dropbox_url(url: str) -> str:
    """Convert Dropbox share link to direct download URL."""
    # Method 1: Change dl=0 to dl=1
    if '?dl=0' in url:
        return url.replace('?dl=0', '?dl=1')
    
    # Method 2: Use dl.dropboxusercontent.com
    if 'www.dropbox.com' in url:
        return url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
    
    return url
```

### Validation Rules

- Skip rows with empty `title` or `author`
- Warn on invalid `isbn_override` format
- Coerce `rating` to integer 1-5, null if invalid
- Parse `date_read` flexibly, warn on invalid format
- Strip whitespace from all string fields

### Error Handling

- If Dropbox fetch fails → exit with error (fail the build)
- If CSV is malformed → exit with error
- If Open Library API fails for a single book → log warning, continue with others
- If Open Library is completely down → exit with error
- If >50% of new books fail enrichment → exit with error (something's wrong)

## Frontend Implementation

### Technology Choices

- **No build step** — vanilla HTML/CSS/JS for simplicity
- **Fuse.js** — fuzzy search library (~5KB gzipped), loaded from CDN
- **Minimal CSS** — clean, readable design; no framework needed

### index.html Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Williams Family Library</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <h1>Williams Family Library</h1>
    <p class="stats"><!-- populated by JS: "600 books" --></p>
  </header>
  
  <main>
    <section class="controls">
      <input type="search" id="search" placeholder="Search titles, authors..." autofocus>
      <select id="genre-filter">
        <option value="">All genres</option>
        <!-- populated by JS -->
      </select>
      <select id="sort">
        <option value="title">Sort by title</option>
        <option value="author">Sort by author</option>
        <option value="date_read">Sort by date read</option>
        <option value="rating">Sort by rating</option>
      </select>
    </section>
    
    <section id="results" class="book-grid">
      <!-- populated by JS -->
    </section>
  </main>
  
  <script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

### app.js Logic

```javascript
// Pseudocode structure

let books = [];
let fuse = null;

async function init() {
  // 1. Fetch books.json
  const response = await fetch('data/books.json');
  const data = await response.json();
  books = data.books;
  
  // 2. Initialize Fuse.js
  // Note: search uses official title/author (the 'title' and 'author' fields)
  fuse = new Fuse(books, {
    keys: ['title', 'author', 'genres'],
    threshold: 0.3,  // 0 = exact match, 1 = match anything
    ignoreLocation: true
  });
  
  // 3. Populate genre filter dropdown
  populateGenreFilter();
  
  // 4. Render initial list
  render(books);
  
  // 5. Attach event listeners
  document.getElementById('search').addEventListener('input', onSearchChange);
  document.getElementById('genre-filter').addEventListener('change', onFilterChange);
  document.getElementById('sort').addEventListener('change', onSortChange);
}

function render(bookList) {
  // Render book cards to #results
  // Each card shows: cover image, official title, official author, geo_region, sort_year
  // (title and author fields contain the official values from Open Library)
}

function onSearchChange(e) {
  const query = e.target.value.trim();
  if (!query) {
    render(applyFiltersAndSort(books));
    return;
  }
  const results = fuse.search(query).map(r => r.item);
  render(applyFiltersAndSort(results));
}

// ... filter and sort implementations
```

### Book Card Component

Each book displays as a card:

```
┌─────────────────────────────┐
│  ┌───────┐                  │
│  │ Cover │  Title           │
│  │ Image │  Author          │
│  │       │  Geography - 2023│
│  └───────┘                  │
└─────────────────────────────┘
```

- Cover image: Use Open Library URL, with fallback to placeholder
- Handle missing covers gracefully (onerror → show placeholder)


### Cover Image Strategy

Use Open Library Covers API:

```
https://covers.openlibrary.org/b/isbn/{ISBN}-M.jpg
```

Sizes: S (small), M (medium), L (large)

**Fallback chain:**
1. Open Library by ISBN
2. If no ISBN, or image 404s, show a placeholder (solid color + title initial?)

**Implementation:**
```javascript
function getCoverUrl(book) {
  if (book.isbn) {
    return `https://covers.openlibrary.org/b/isbn/${book.isbn}-M.jpg`;
  }
  return 'placeholder.svg';
}

// In render, handle broken images:
// <img src="${coverUrl}" onerror="this.src='placeholder.svg'" alt="${title} cover">
```

## GitHub Action (deploy.yml)

```yaml
name: Build and Deploy

on:
  # Manual trigger
  workflow_dispatch:
  
  # Scheduled: daily at 6am UTC
  schedule:
    - cron: '0 6 * * *'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          # Need full history to push cache updates
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install requests
      
      - name: Fetch CSV and build JSON
        env:
          DROPBOX_URL: ${{ secrets.DROPBOX_CSV_URL }}
        run: |
          python scripts/build.py
      
      - name: Commit cache updates
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add cache/enrichment_cache.json
          git diff --staged --quiet || git commit -m "Update enrichment cache [skip ci]"
          git push
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./
          exclude_assets: '.github,scripts,cache,requirements.txt,.gitignore'
```

### Required Secrets

Set in repository Settings → Secrets → Actions:

- `DROPBOX_CSV_URL`: The direct download URL for books.csv

### Trigger Options

1. **Manual**: Go to Actions tab → "Build and Deploy" → "Run workflow"
2. **Scheduled**: Runs daily at 6am UTC automatically
3. **On push** (optional): Add `push:` trigger if you want deploys on code changes

### Cache Commit Behavior

- The `[skip ci]` in the commit message prevents an infinite loop
- Cache is only committed if there are actual changes
- Cache commits don't trigger a new deploy

### First Run Behavior

On the first run with 600 books:
- All books need enrichment
- ~600 API calls at 1/second = ~10 minutes
- GitHub Actions has a 6-hour timeout, so this is fine
- Subsequent runs only enrich new books (fast)

## Styling Guidelines

Keep it minimal and readable:

- Max width container (~900px) for comfortable reading
- Responsive grid: 4 columns → 2 columns → 1 column
- System font stack for fast loading
- High contrast, accessible colors
- Subtle hover states on book cards

```css
/* Example core styles */
:root {
  --max-width: 900px;
  --gap: 1rem;
}

body {
  font-family: system-ui, -apple-system, sans-serif;
  line-height: 1.5;
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--gap);
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--gap);
}

.book-card {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.book-card img {
  width: 60px;
  height: 90px;
  object-fit: cover;
}
```

## Implementation Phases

### Phase 1: Enrichment Pipeline
1. Implement `scripts/enrich.py` (Open Library API client)
2. Implement `scripts/build.py` (orchestrator)
3. Test locally with sample CSV (10-20 books)
4. Verify cache read/write works correctly
5. Test edge cases: missing books, multiple editions, non-English titles

### Phase 2: GitHub Action
1. Create repository structure
2. Set up GitHub Action workflow
3. Configure Dropbox secret
4. Test manual trigger
5. Verify cache commits work
6. Test scheduled trigger

### Phase 3: Frontend Core
1. Create minimal `index.html` that loads and displays `books.json`
2. Implement book card rendering
3. Add cover image handling with fallbacks
4. Add loading state

### Phase 4: Search and Filtering
1. Integrate Fuse.js
2. Implement search input handling
3. Add genre filter dropdown (populated from data)
4. Add sort options
5. Add "no results" state

### Phase 5: Polish
1. Style the interface
2. Test responsive design
3. Add match confidence indicator (maybe subtle warning for "low" matches)
4. Add link to Open Library page for each book
5. Handle books with no ISBN gracefully

### Phase 6: Enhancements (Optional)
1. Expandable book cards with notes
2. URL state (search query in URL for shareable links)
3. Dark mode toggle
4. Stats page (books per year, genre breakdown, ratings distribution)
5. "Needs attention" view for low-confidence matches
6. Manual re-enrich button for specific books

## Testing Checklist

### Enrichment Pipeline
- [ ] Enrichment finds correct ISBN for well-known books
- [ ] Enrichment extracts official title and author correctly
- [ ] Official title/author are used for display instead of user input
- [ ] User title/author are preserved in output for reference
- [ ] Enrichment handles books with multiple editions (picks reasonable one)
- [ ] Enrichment handles books not in Open Library (logs warning, continues)
- [ ] Falls back to user title/author when official values not found
- [ ] Enrichment respects rate limiting (1 req/sec)
- [ ] Cache is written correctly after enrichment
- [ ] Cache is read correctly on subsequent runs
- [ ] New books are enriched, existing books use cache
- [ ] `isbn_override` takes precedence over API result
- [ ] Genre cleaning removes junk subjects
- [ ] Match confidence scores are reasonable

### Build Script
- [ ] Handles empty CSV gracefully
- [ ] Handles malformed rows (logs warning, skips)
- [ ] Fails loudly on Dropbox fetch error
- [ ] Fails loudly on Open Library complete outage
- [ ] Generates valid JSON output

### GitHub Action
- [ ] Runs successfully on manual trigger
- [ ] Runs successfully on schedule
- [ ] Commits cache updates correctly
- [ ] `[skip ci]` prevents infinite loop
- [ ] Deploys site after successful build

### Frontend
- [ ] Site loads and displays books
- [ ] Books display official title/author (not user-entered values)
- [ ] Search uses official title/author for matching
- [ ] Search returns relevant results
- [ ] Search handles empty query (shows all)
- [ ] Genre filter works
- [ ] Sort options work
- [ ] Missing cover images show placeholder
- [ ] Low-confidence matches are indicated (if implemented)
- [ ] Open Library links work
- [ ] Site is usable on mobile
- [ ] Loading state displays correctly

## Notes for Implementation

1. **Start with the enrichment script** — get the Open Library API integration working locally before anything else. Test with 10-20 books.

2. **Test edge cases early:**
   - Books with very common titles ("The Road", "It")
   - Books where user title differs from official title (e.g., user enters "Thinking Fast and Slow", Open Library has "Thinking, Fast and Slow")
   - Books with multiple authors (ensure all authors are included in official_author)
   - Books with non-ASCII characters in title/author
   - Very old books (pre-ISBN era)
   - Self-published or obscure books
   - Anthologies and collections

3. **Cache is critical** — the cache makes builds fast and avoids hammering the API. Initialize it as an empty JSON object `{}` in the repo.

4. **Match confidence matters** — surface low-confidence matches in the UI somehow (subtle indicator) so the user can review and add `isbn_override` if needed.

5. **Open Library coverage** — it's good but not perfect. Expect ~5-10% of books to need manual intervention via `isbn_override`.

6. **First run will be slow** — 600 books × 1 second = 10 minutes. This is fine for a one-time initial build. Warn the user.

7. **Fuse.js threshold tuning** — 0.3 is a reasonable default; adjust if search is too fuzzy or too strict.

8. **No JavaScript framework needed** — vanilla JS is fine for this scale; avoid unnecessary complexity.

9. **Consider a "dry run" mode** — for local testing, add a flag that skips the Dropbox fetch and uses a local CSV file instead.

10. **Logging is important** — the enrichment process should log clearly so the user can see progress and identify problem books in the Action logs.

11. **Official vs user values** — the user enters approximate title/author for lookup purposes, but the website displays and searches using the official values from Open Library. This ensures consistency and correct formatting. User values are preserved in `user_title` and `user_author` for debugging/reference.
