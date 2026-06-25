"""Backfill UK + US IPA for every word, dictionary-first.

For each word: look it up on Wiktionary (authoritative); only fall back to the
model when the dictionary has no usable IPA (phrases, inflected forms, gaps).

Run from the vocab_app directory:  python3 backfill_phonetics.py
  --only-missing   only fill rows that have no UK/US phonetic yet
  (default)        refresh ALL rows (overwrites the old single-accent data)
"""
import sys
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import db
from phonetics import resolve


def main():
    db.init_db()  # ensure phonetic_uk / phonetic_us columns exist
    only_missing = '--only-missing' in sys.argv

    conn = sqlite3.connect(db.DB_PATH)
    if only_missing:
        rows = conn.execute(
            "SELECT id, entry, type FROM words WHERE phonetic_uk = '' AND phonetic_us = ''"
        ).fetchall()
    else:
        rows = conn.execute("SELECT id, entry, type FROM words").fetchall()

    if not rows:
        print('Nothing to do.')
        return

    print(f'Resolving UK+US IPA for {len(rows)} word(s) (dictionary-first)...\n')

    def _gen(row):
        word_id, entry, type_ = row
        uk, us, source = resolve(entry, type_)
        return word_id, entry, uk, us, source

    done = 0
    by_source = {'wiktionary': 0, 'ai': 0, '': 0}
    failed = []
    # Keep concurrency modest — Wiktionary asks clients not to hammer the API.
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_gen, r): r for r in rows}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                word_id, entry, uk, us, source = fut.result()
                conn.execute(
                    'UPDATE words SET phonetic_uk = ?, phonetic_us = ? WHERE id = ?',
                    (uk, us, word_id))
                conn.commit()
                done += 1
                by_source[source] = by_source.get(source, 0) + 1
                tag = {'wiktionary': '📖', 'ai': '🤖', '': '⚠️ '}.get(source, '?')
                print(f'  {tag} {entry:30} UK={uk or "—":18} US={us or "—"}')
            except Exception as e:
                failed.append((row[1], str(e)))

    print(f'\nDone. Updated {done} word(s).')
    print(f'  📖 from Wiktionary: {by_source.get("wiktionary", 0)}')
    print(f'  🤖 from model:      {by_source.get("ai", 0)}')
    print(f'  ⚠️  no result:       {by_source.get("", 0)}')
    if failed:
        print(f'\n{len(failed)} errored (re-run to retry):')
        for entry, err in failed:
            print(f'  - {entry}: {err}')


if __name__ == '__main__':
    main()
