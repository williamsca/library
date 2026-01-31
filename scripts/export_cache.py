#!/usr/bin/env python3
"""
Export books.json as a CSV for use as the master book list going forward.
Bakes each book's resolved ISBN into isbn_override so future API lookups
can skip the search step for already-identified titles.
"""

import csv
import json
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).parent.parent
    books_path = repo_root / 'data' / 'books.json'
    output_path = repo_root / 'data' / 'library_export.csv'

    if not books_path.exists():
        print(f"✗ books.json not found at {books_path}", file=sys.stderr)
        sys.exit(1)

    with open(books_path, 'r') as f:
        data = json.load(f)

    books = data.get('books', [])
    print(f"Exporting {len(books)} books...")

    fieldnames = [
        'ID',
        'user_title',
        'user_author',
        'isbn_override',
        'geo_region',
        'sort_year',
        'sort_basis',
        'read_by_colin',
        'read_by_kaitlyn',
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, book in enumerate(books, start=1):
            writer.writerow({
                'ID': i,
                'user_title': book.get('user_title', ''),
                'user_author': book.get('user_author', ''),
                'isbn_override': book.get('isbn') or '',
                'geo_region': book.get('geo_region') or '',
                'sort_year': book.get('sort_year') or '',
                'sort_basis': book.get('sort_basis') or '',
                'read_by_colin': 'TRUE' if book.get('read_by_colin') else 'FALSE',
                'read_by_kaitlyn': 'TRUE' if book.get('read_by_kaitlyn') else 'FALSE',
            })

    print(f"✓ Exported to {output_path}")

    # Summary
    with_isbn = sum(1 for b in books if b.get('isbn'))
    without_isbn = len(books) - with_isbn
    print(f"  {with_isbn} books have a resolved ISBN (will skip search)")
    print(f"  {without_isbn} books have no ISBN (will need a fresh search)")


if __name__ == '__main__':
    main()
