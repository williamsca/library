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
