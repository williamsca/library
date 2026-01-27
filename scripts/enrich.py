#!/usr/bin/env python3
"""
Open Library API enrichment client.
Fetches metadata for books by title and author.
"""

import requests
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List, Optional


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
    'literature',
    'open library staff picks',
    'lending library',
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


def make_cache_key(title: str, author: str) -> str:
    """Create normalized cache key from title and author."""
    return f"{title.lower().strip()}|{author.lower().strip()}"


def compute_match_score(query_title: str, query_author: str, doc: dict) -> float:
    """Score 0-1 based on title and author similarity."""
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


def select_best_isbn(isbn_list: List[str]) -> Optional[str]:
    """Prefer ISBN-13, fallback to ISBN-10."""
    if not isbn_list:
        return None

    # Filter and prefer ISBN-13
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
        # Lowercase for comparison
        lower = subject.lower().strip()

        # Skip ignored
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


def enrich_by_work(work_id: str, title: str, author: str) -> dict:
    """
    Fetch book data by Open Library work ID.
    work_id can be full path (/works/OL123W) or just the ID (OL123W).
    """
    # Normalize: strip /works/ prefix if present
    work_key = work_id.strip('/')
    if not work_key.startswith('works/'):
        work_key = f'works/{work_id}'

    print(f"  Querying by work: {work_key} ({title})")

    try:
        response = requests.get(
            f'https://openlibrary.org/{work_key}.json',
            timeout=10
        )
        response.raise_for_status()
        work_data = response.json()

        # Get editions to find an ISBN and cover
        editions_response = requests.get(
            f'https://openlibrary.org/{work_key}/editions.json',
            params={'limit': 5},
            timeout=10
        )
        editions = editions_response.json().get('entries', [])

        # Find best ISBN from editions
        isbn = None
        edition_key = None
        for ed in editions:
            edition_key = ed.get('key', '').split('/')[-1]
            isbns = ed.get('isbn_13', []) + ed.get('isbn_10', [])
            if isbns:
                isbn = isbns[0]
                break

        # Extract metadata from work
        official_title = work_data.get('title')
        # Authors require separate fetch; fallback to user-provided

        subjects = work_data.get('subjects', [])

        # Parse first_publish_date to extract year
        year_published = None
        first_publish = work_data.get('first_publish_date')
        if first_publish:
            import re
            match = re.search(r'\d{4}', str(first_publish))
            if match:
                year_published = int(match.group())

        print(f"    ✓ Found by work: {official_title}")

        return {
            'official_title': official_title,
            'official_author': None,  # Would need separate author fetch
            'isbn': isbn,
            'year_published': year_published,
            'subjects': subjects[:10],
            'open_library_work_key': f'/{work_key}',
            'open_library_edition_key': edition_key,
            'match_confidence': 'work_override',
            'fetched_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

    except requests.RequestException as e:
        print(f"    ✗ Work API error: {e}")
        return enrich_book(title, author)  # Fallback to search


def enrich_by_isbn(isbn: str, title: str, author: str) -> dict:
    """
    Fetch book data directly by ISBN from Open Library.
    Returns enrichment data dictionary.
    """
    print(f"  Querying by ISBN: {isbn} ({title})")

    try:
        # Fetch book data by ISBN
        response = requests.get(
            f'https://openlibrary.org/api/books',
            params={
                'bibkeys': f'ISBN:{isbn}',
                'format': 'json',
                'jscmd': 'data'
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        isbn_key = f'ISBN:{isbn}'
        if isbn_key not in data:
            print(f"    ⚠ ISBN not found, falling back to title/author search")
            return enrich_book(title, author)

        book_data = data[isbn_key]

        # Extract metadata
        official_title = book_data.get('title')
        authors = book_data.get('authors', [])
        official_author = ', '.join([a.get('name', '') for a in authors]) if authors else None

        # Get subjects
        subjects = []
        if 'subjects' in book_data:
            subjects = [s.get('name', s) if isinstance(s, dict) else s for s in book_data['subjects']]

        # Get work key
        work_key = None
        if 'works' in book_data and book_data['works']:
            work_key = book_data['works'][0].get('key')

        # Get publish year
        year_published = None
        if 'publish_date' in book_data:
            # Try to extract year from publish_date
            import re
            match = re.search(r'\d{4}', book_data['publish_date'])
            if match:
                year_published = int(match.group())

        print(f"    ✓ Found by ISBN: {official_title}")

        return {
            'official_title': official_title,
            'official_author': official_author,
            'isbn': isbn,
            'year_published': year_published,
            'subjects': subjects[:10],
            'open_library_work_key': work_key,
            'open_library_edition_key': book_data.get('key', '').split('/')[-1] if 'key' in book_data else None,
            'match_confidence': 'isbn',  # Special confidence level for ISBN matches
            'fetched_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

    except requests.RequestException as e:
        print(f"    ✗ API error, falling back to title/author search: {e}")
        return enrich_book(title, author)


def enrich_book(title: str, author: str) -> dict:
    """
    Query Open Library API for a single book.
    Returns enrichment data dictionary.
    """
    print(f"  Querying: {title} by {author}")

    try:
        # Query API
        params = {
            'title': title,
            'author': author,
            'limit': 5,
            'fields': 'key,title,author_name,first_publish_year,isbn,subject,edition_key'
        }
        response = requests.get(
            'https://openlibrary.org/search.json',
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data['numFound'] == 0:
            print(f"    ⚠ No results found")
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
                'fetched_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }

        # Score and rank results
        best_match = None
        best_score = 0

        for doc in data['docs']:
            score = compute_match_score(title, author, doc)
            if score > best_score:
                best_score = score
                best_match = doc

        # Determine confidence
        if best_score >= 0.9:
            confidence = 'high'
        elif best_score >= 0.7:
            confidence = 'medium'
        elif best_score >= 0.5:
            confidence = 'low'
        else:
            confidence = 'none'

        # Extract best ISBN
        isbn = select_best_isbn(best_match.get('isbn', []))

        # Extract official title and author
        official_title = best_match.get('title')
        author_names = best_match.get('author_name', [])
        official_author = ', '.join(author_names) if author_names else None

        print(f"    ✓ Found: {official_title} ({confidence} confidence)")

        # Return enrichment data
        return {
            'official_title': official_title,
            'official_author': official_author,
            'isbn': isbn,
            'year_published': best_match.get('first_publish_year'),
            'subjects': best_match.get('subject', [])[:10],  # limit to top 10
            'open_library_work_key': best_match.get('key'),
            'open_library_edition_key': best_match.get('edition_key', [None])[0],
            'match_confidence': confidence,
            'fetched_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

    except requests.RequestException as e:
        print(f"    ✗ API error: {e}")
        return {
            'official_title': None,
            'official_author': None,
            'isbn': None,
            'year_published': None,
            'subjects': [],
            'open_library_work_key': None,
            'open_library_edition_key': None,
            'match_confidence': 'none',
            'error': f'API error: {str(e)}',
            'fetched_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }


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
            # Rate limiting: 1 request per second
            time.sleep(1.1)

        cache_key = make_cache_key(book['title'], book['author'])

        # Use override-based enrichment if provided, otherwise search by title/author
        isbn_override = book.get('isbn_override')
        olid_work_override = book.get('olid_work_override')

        if isbn_override:
            results[cache_key] = enrich_by_isbn(isbn_override, book['title'], book['author'])
        elif olid_work_override:
            results[cache_key] = enrich_by_work(olid_work_override, book['title'], book['author'])
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
