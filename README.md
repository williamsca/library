# Williams Family Library

A searchable online catalog of books we own. The catalog is automatically enriched with metadata from the Open Library API and deployed to GitHub Pages.

## How It Works

1. Maintain a simple CSV file (`library.csv`) in Dropbox with book titles and authors
2. A GitHub Action runs daily to:
   - Fetch the CSV
   - Enrich books with metadata from Open Library (ISBN, publication year, genres, cover images)
   - Cache the enrichment data to avoid repeated API calls
   - Generate `books.json`
   - Deploy the static site to GitHub Pages

## Setup

### 1. Repository Secrets

Add the following secret in your repository settings:

- `DROPBOX_CSV_URL`: The direct download URL for your `library.csv` file in Dropbox

### 2. GitHub Pages

Enable GitHub Pages in repository settings:
- Source: Deploy from a branch
- Branch: `gh-pages`
- Folder: `/ (root)`

### 3. CSV Format

Your `library.csv` should have the following columns:

```csv
title,author,isbn_override,geo_region,sort_year,sort_basis,read_by_colin,read_by_kaitlyn
```

**Required columns:**
- `title` - Book title (approximate; used for API lookup)
- `author` - Author name (approximate; used for API lookup)

**Optional columns:**
- `isbn_override` - Manually specify ISBN if auto-lookup fails
- `geo_region` - Geographic region
- `sort_year` - Year for sorting
- `sort_basis` - Explanation for sort_year
- `read_by_colin` - TRUE/FALSE
- `read_by_kaitlyn` - TRUE/FALSE

## Local Development

### Run the build script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Build with local test CSV
python scripts/build.py

# Or build with Dropbox CSV
export DROPBOX_URL="your-dropbox-url"
python scripts/build.py
```

### Test the frontend:

```bash
python -m http.server 8000
# Open http://localhost:8000 in your browser
```

## Manual Deployment

Trigger a manual build from the Actions tab:
1. Go to Actions
2. Select "Build and Deploy"
3. Click "Run workflow"

## Features

- **Automatic enrichment** - Book metadata is fetched automatically from Open Library
- **Smart caching** - Enrichment results are cached and committed to avoid repeated API calls
- **Fuzzy search** - Search by title, author, or genre
- **Genre filtering** - Filter books by genre
- **Sorting** - Sort by title, author, or year
- **Responsive design** - Works on desktop and mobile

## File Structure

```
├── .github/workflows/
│   └── deploy.yml           # GitHub Action workflow
├── cache/
│   └── enrichment_cache.json # Cached API responses (committed)
├── data/
│   └── books.json           # Generated book data (not committed)
├── scripts/
│   ├── build.py             # Main build orchestrator
│   └── enrich.py            # Open Library API client
├── index.html               # Main page
├── styles.css               # Styles
├── app.js                   # Search & rendering logic
└── requirements.txt         # Python dependencies
```

## Credits

Book metadata provided by [Open Library](https://openlibrary.org).
