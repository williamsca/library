#!/usr/bin/env python3
"""
Google Books API enrichment client.
Fetches metadata for books by ISBN or title/author search.
"""

import os
import re
import requests
import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional


# Subjects to ignore (too generic or not useful)
IGNORE_SUBJECTS = {
    'fiction',
    'nonfiction',
    'general',
    'literary',
    'literature',
}

# Map variations to canonical names
SUBJECT_MAP = {
    'sci-fi': 'Science Fiction',
    'science fiction': 'Science Fiction',
    'self-help': 'Self-Help',
    'selfhelp': 'Self-Help',
    'self help': 'Self-Help',
    'biography': 'Biography',
    'biographies': 'Biography',
    'memoir': 'Memoir',
    'memoirs': 'Memoir',
    'history': 'History',
    'historical': 'History',
    'psychology': 'Psychology',
    'philosophy': 'Philosophy',
    'economics': 'Economics',
    'politics': 'Politics',
    'political science': 'Politics',
}


def load_api_key() -> str:
    """Load Google Books API key from environment or .Renviron."""
    key = os.environ.get('GOOGLE_BOOKS_API_KEY')
    if key:
        return key

    # Fallback: parse .Renviron at repo root
    renviron_path = Path(__file__).parent.parent / '.Renviron'
    if renviron_path.exists():
        with open(renviron_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('GOOGLE_BOOKS_API_KEY='):
                    return line.split('=', 1)[1].strip()

    print("✗ GOOGLE_BOOKS_API_KEY not found in env or .Renviron", file=sys.stderr)
    sys.exit(1)


API_KEY = load_api_key()


def make_cache_key(title: str, author: str) -> str:
    """Create normalized cache key from title and author."""
    return f"{title.lower().strip()}|{author.lower().strip()}"


def compute_match_score(query_title: str, query_author: str, result_title: str, result_authors: List[str]) -> float:
    """Score 0-1 based on title and author similarity."""
    title_score = SequenceMatcher(
        None,
        query_title.lower(),
        result_title.lower()
    ).ratio()

    result_author_str = ' '.join(result_authors).lower()
    author_score = SequenceMatcher(
        None,
        query_author.lower(),
        result_author_str
    ).ratio()

    # Weight title slightly higher
    return (title_score * 0.6) + (author_score * 0.4)


def select_best_isbn(isbn_list: List[str]) -> Optional[str]:
    """Prefer ISBN-13, fallback to ISBN-10."""
    if not isbn_list:
        return None

    isbn_13 = [i for i in isbn_list if len(i) == 13 and i.isdigit()]
    isbn_10 = [i for i in isbn_list if len(i) == 10]

    if isbn_13:
        return isbn_13[0]
    if isbn_10:
        return isbn_10[0]
    return None


def clean_genres(subjects: List[str]) -> List[str]:
    """Clean and deduplicate subjects into usable genres."""
    cleaned = []
    seen = set()

    for subject in subjects:
        lower = subject.lower().strip()

        if lower in IGNORE_SUBJECTS:
            continue

        # Skip if contains numbers (often "Fiction, 1900-1999" type junk)
        if any(c.isdigit() for c in subject):
            continue

        # Skip very long subjects (usually not useful)
        if len(subject) > 50:
            continue

        # Apply mapping or title-case
        canonical = SUBJECT_MAP.get(lower, subject.title())

        # Dedupe
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            cleaned.append(canonical)

    return cleaned[:5]  # Limit to 5 genres


def extract_volume_data(item: dict) -> dict:
    """Extract normalized metadata from a Google Books volume item."""
    info = item.get('volumeInfo', {})

    # ISBNs from industryIdentifiers array
    identifiers = info.get('industryIdentifiers', [])
    isbn_list = [i['identifier'] for i in identifiers if i.get('type') in ('ISBN_13', 'ISBN_10')]
    isbn = select_best_isbn(isbn_list)

    # Year from publishedDate (can be "2011", "2011-09", or "2011-09-27")
    year_published = None
    pub_date = info.get('publishedDate', '')
    if pub_date:
        match = re.search(r'\d{4}', pub_date)
        if match:
            year_published = int(match.group())

    # Cover URL (API returns http, upgrade to https)
    cover_url = info.get('imageLinks', {}).get('thumbnail')
    if cover_url:
        cover_url = cover_url.replace('http://', 'https://')

    authors = info.get('authors', [])

    return {
        'official_title': info.get('title'),
        'official_author': ', '.join(authors) if authors else None,
        'isbn': isbn,
        'year_published': year_published,
        'subjects': info.get('categories', [])[:10],
        'google_books_volume_id': item.get('id'),
        'cover_url': cover_url,
    }


def _empty_result(error: Optional[str] = None) -> dict:
    """Return a blank enrichment result, optionally with an error message."""
    result = {
        'official_title': None,
        'official_author': None,
        'isbn': None,
        'year_published': None,
        'subjects': [],
        'google_books_volume_id': None,
        'cover_url': None,
        'match_confidence': 'none',
        'fetched_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    if error:
        result['error'] = error
    return result


def enrich_by_isbn(isbn: str, title: str, author: str) -> dict:
    """Fetch book data by ISBN from Google Books."""
    print(f"  Querying by ISBN: {isbn} ({title})")

    try:
        response = requests.get(
            'https://www.googleapis.com/books/v1/volumes',
            params={
                'q': f'isbn:{isbn}',
                'maxResults': 1,
                'key': API_KEY,
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        if not items:
            print(f"    ⚠ ISBN not found, falling back to title/author search")
            return enrich_book(title, author)

        result = extract_volume_data(items[0])
        # Keep the queried ISBN if Google didn't return one in identifiers
        result['isbn'] = result['isbn'] or isbn
        result['match_confidence'] = 'isbn'
        result['fetched_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        print(f"    ✓ Found by ISBN: {result['official_title']}")
        return result

    except requests.RequestException as e:
        print(f"    ✗ API error, falling back to title/author search: {e}")
        return enrich_book(title, author)


def enrich_book(title: str, author: str) -> dict:
    """Query Google Books API for a single book by title and author."""
    print(f"  Querying: {title} by {author}")

    try:
        response = requests.get(
            'https://www.googleapis.com/books/v1/volumes',
            params={
                'q': f'intitle:{title} inauthor:{author}',
                'maxResults': 5,
                'key': API_KEY,
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        if not items:
            print(f"    ⚠ No results found")
            return _empty_result('No results found')

        # Score and rank results
        best_item = None
        best_score = 0

        for item in items:
            info = item.get('volumeInfo', {})
            score = compute_match_score(
                title, author,
                info.get('title', ''),
                info.get('authors', [])
            )
            if score > best_score:
                best_score = score
                best_item = item

        # Determine confidence
        if best_score >= 0.9:
            confidence = 'high'
        elif best_score >= 0.7:
            confidence = 'medium'
        elif best_score >= 0.5:
            confidence = 'low'
        else:
            confidence = 'none'

        result = extract_volume_data(best_item)
        result['match_confidence'] = confidence
        result['fetched_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        print(f"    ✓ Found: {result['official_title']} ({confidence} confidence)")
        return result

    except requests.RequestException as e:
        print(f"    ✗ API error: {e}")
        return _empty_result(f'API error: {str(e)}')


def enrich_books(books: List[dict]) -> Dict[str, dict]:
    """
    Enrich multiple books with rate limiting.
    Returns dict of cache_key -> enrichment_data.
    """
    results = {}
    total = len(books)

    print(f"\nEnriching {total} books...")

    for i, book in enumerate(books):
        if i > 0:
            # Rate limiting
            time.sleep(1.1)

        cache_key = make_cache_key(book['title'], book['author'])
        isbn_override = book.get('isbn_override')

        if isbn_override:
            results[cache_key] = enrich_by_isbn(isbn_override, book['title'], book['author'])
        else:
            results[cache_key] = enrich_book(book['title'], book['author'])

        print(f"  [{i+1}/{total}] Progress: {((i+1)/total)*100:.0f}%")

    print(f"\n✓ Enrichment complete!")
    return results


if __name__ == '__main__':
    # Simple test
    test_book = {
        'title': 'Thinking Fast and Slow',
        'author': 'Daniel Kahneman'
    }
    result = enrich_books([test_book])

    import json
    print("\nTest result:")
    print(json.dumps(result, indent=2))
