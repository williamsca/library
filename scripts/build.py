#!/usr/bin/env python3
"""
Main build orchestrator.
Fetches CSV, enriches books, generates books.json.
"""

import csv
import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
import requests

# Import from enrich module
from enrich import enrich_books, make_cache_key, clean_genres


def transform_dropbox_url(url: str) -> str:
    """Convert Dropbox share link to direct download URL."""
    # Method 1: Change dl=0 to dl=1
    if '?dl=0' in url:
        return url.replace('?dl=0', '?dl=1')

    # Method 2: Also handle other query params
    if 'dl=0' in url:
        return url.replace('dl=0', 'dl=1')

    return url


def fetch_csv(url: str) -> str:
    """Fetch CSV content from URL."""
    print(f"Fetching CSV from Dropbox...")
    try:
        download_url = transform_dropbox_url(url)
        response = requests.get(download_url, timeout=30)
        response.raise_for_status()
        print(f"✓ CSV fetched successfully")
        return response.text
    except requests.RequestException as e:
        print(f"✗ Failed to fetch CSV: {e}", file=sys.stderr)
        sys.exit(1)


def parse_csv(csv_content: str) -> List[Dict]:
    """Parse CSV content into list of book dictionaries."""
    print(f"Parsing CSV...")
    books = []
    reader = csv.DictReader(csv_content.strip().split('\n'))

    for i, row in enumerate(reader, start=2):  # start at 2 for line numbers (after header)
        # Required fields
        title = row.get('title', '').strip()
        author = row.get('author', '').strip()

        if not title or not author:
            print(f"  ⚠ Skipping row {i}: missing title or author")
            continue

        # Parse optional fields
        book = {
            'title': title,
            'author': author,
            'isbn_override': row.get('isbn_override', '').strip() or None,
            'olid_work_override': row.get('olid_work_override', '').strip() or None,
            'geo_region': row.get('geo_region', '').strip() or None,
            'sort_year': row.get('sort_year', '').strip() or None,
            'sort_basis': row.get('sort_basis', '').strip() or None,
            'read_by_colin': row.get('read_by_colin', '').strip().upper() == 'TRUE',
            'read_by_kaitlyn': row.get('read_by_kaitlyn', '').strip().upper() == 'TRUE',
        }

        books.append(book)

    print(f"✓ Parsed {len(books)} books")
    return books


def load_cache(cache_path: Path) -> Dict:
    """Load enrichment cache from file."""
    if not cache_path.exists():
        return {}

    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠ Failed to load cache, starting fresh: {e}")
        return {}


def save_cache(cache: Dict, cache_path: Path):
    """Save enrichment cache to file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=2)
    print(f"✓ Cache saved to {cache_path}")


def generate_id(book: Dict) -> str:
    """Generate stable short ID for a book."""
    key = f"{book['title']}|{book['author']}"
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def make_cover_url(isbn: Optional[str]) -> Optional[str]:
    """Generate Open Library cover URL from ISBN."""
    if isbn:
        return f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
    return None


def make_ol_url(enrichment: Dict) -> Optional[str]:
    """Generate Open Library book page URL."""
    work_key = enrichment.get('open_library_work_key')
    if work_key:
        return f"https://openlibrary.org{work_key}"
    return None


def make_search_text(title: str, author: str, genres: List[str]) -> str:
    """Create lowercase search text for client-side search."""
    parts = [title, author] + genres
    return ' '.join(parts).lower()


def build_books_json(books: List[Dict], cache: Dict) -> Dict:
    """Merge user data with enrichment cache and generate final JSON."""
    print(f"\nBuilding books.json...")

    books_json = []

    for book in books:
        cache_key = make_cache_key(book['title'], book['author'])
        enrichment = cache.get(cache_key, {})

        # isbn_override takes precedence
        isbn = book.get('isbn_override') or enrichment.get('isbn')

        # Use official title/author from enrichment, fallback to user values
        display_title = enrichment.get('official_title') or book['title']
        display_author = enrichment.get('official_author') or book['author']

        # Clean genres
        genres = clean_genres(enrichment.get('subjects', []))

        book_entry = {
            'id': generate_id(book),
            'title': display_title,
            'author': display_author,
            'user_title': book['title'],
            'user_author': book['author'],
            'isbn': isbn,
            'year_published': enrichment.get('year_published'),
            'genres': genres,
            'geo_region': book.get('geo_region'),
            'sort_year': book.get('sort_year'),
            'sort_basis': book.get('sort_basis'),
            'read_by_colin': book.get('read_by_colin', False),
            'read_by_kaitlyn': book.get('read_by_kaitlyn', False),
            'cover_url': make_cover_url(isbn),
            'open_library_url': make_ol_url(enrichment),
            'match_confidence': enrichment.get('match_confidence', 'none'),
            'search_text': make_search_text(display_title, display_author, genres)
        }

        books_json.append(book_entry)

    output = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'count': len(books_json),
        'books': books_json
    }

    print(f"✓ Built JSON with {len(books_json)} books")
    return output


def main():
    """Main build process."""
    print("=" * 60)
    print("Book Catalog Build")
    print("=" * 60)

    # Paths
    repo_root = Path(__file__).parent.parent
    cache_path = repo_root / 'cache' / 'enrichment_cache.json'
    output_path = repo_root / 'data' / 'books.json'

    # 1. Fetch CSV
    csv_url = 'https://www.dropbox.com/scl/fi/nxlkl090aewe3qvebr3f7/library.csv?rlkey=jv1we3yba15l5uf4u9ikwhl5x&st=vhy8dgyi&dl=0'
    if csv_url:
        # Production: fetch from Dropbox
        csv_content = fetch_csv(csv_url)
    else:
        # Development: use local test file
        test_csv_path = repo_root / 'test_books.csv'
        if not test_csv_path.exists():
            print(f"✗ No DROPBOX_URL set and no test_books.csv found", file=sys.stderr)
            sys.exit(1)
        print(f"Using local test CSV: {test_csv_path}")
        with open(test_csv_path, 'r') as f:
            csv_content = f.read()

    # 2. Parse CSV
    books = parse_csv(csv_content)

    if not books:
        print("✗ No valid books found in CSV", file=sys.stderr)
        sys.exit(1)

    # 3. Load cache
    cache = load_cache(cache_path)
    print(f"✓ Loaded cache with {len(cache)} entries")

    # 4. Identify books needing enrichment
    to_enrich = []
    for book in books:
        cache_key = make_cache_key(book['title'], book['author'])
        current_isbn_override = book.get('isbn_override')

        current_olid_work_override = book.get('olid_work_override')

        # Need enrichment if:
        # 1. Not in cache at all, OR
        # 2. isbn_override has changed, OR
        # 3. olid_work_override has changed
        if cache_key not in cache:
            to_enrich.append(book)
        else:
            cached_isbn_override = cache[cache_key].get('isbn_override_used')
            cached_olid_work_override = cache[cache_key].get('olid_work_override_used')

            if current_isbn_override != cached_isbn_override:
                print(f"  ↻ isbn_override changed for '{book['title']}': "
                      f"{cached_isbn_override or 'None'} → {current_isbn_override or 'None'}")
                to_enrich.append(book)
            elif current_olid_work_override != cached_olid_work_override:
                print(f"  ↻ olid_work_override changed for '{book['title']}': "
                      f"{cached_olid_work_override or 'None'} → {current_olid_work_override or 'None'}")
                to_enrich.append(book)

    print(f"\nBooks needing enrichment: {len(to_enrich)}")
    print(f"Books already cached: {len(books) - len(to_enrich)}")

    # 5. Enrich new books
    if to_enrich:
        new_enrichments = enrich_books(to_enrich)

        # Store overrides in cache for change detection
        for book in to_enrich:
            cache_key = make_cache_key(book['title'], book['author'])
            if cache_key in new_enrichments:
                new_enrichments[cache_key]['isbn_override_used'] = book.get('isbn_override')
                new_enrichments[cache_key]['olid_work_override_used'] = book.get('olid_work_override')

        cache.update(new_enrichments)

        # Check error rate
        errors = sum(1 for e in new_enrichments.values() if 'error' in e)
        error_rate = errors / len(new_enrichments) if new_enrichments else 0

        if error_rate > 0.5:
            print(f"\n⚠ Warning: {error_rate*100:.0f}% of enrichments failed", file=sys.stderr)
            print(f"This may indicate an API issue. Continuing anyway...", file=sys.stderr)

        # Save updated cache
        save_cache(cache, cache_path)
    else:
        print("✓ All books already cached, skipping enrichment")

    # 6. Build and save books.json
    output = build_books_json(books, cache)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"✓ Saved books.json to {output_path}")

    # 7. Summary
    print("\n" + "=" * 60)
    print("Build complete!")
    print("=" * 60)
    print(f"Total books: {len(books)}")
    print(f"Cache entries: {len(cache)}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
