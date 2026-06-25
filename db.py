import sqlite3
import random
import os
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vocab.db')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS words (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            entry            TEXT NOT NULL,
            type             TEXT NOT NULL,
            sentence         TEXT NOT NULL,
            chinese_meaning  TEXT NOT NULL,
            english_definition TEXT NOT NULL,
            chinese_sentence TEXT NOT NULL DEFAULT '',
            date_added       TEXT NOT NULL,
            check_count      INTEGER DEFAULT 0,
            review_sentence  TEXT NOT NULL DEFAULT '',
            review_sentence_chinese TEXT NOT NULL DEFAULT '',
            phonetic         TEXT NOT NULL DEFAULT '',
            phonetic_uk      TEXT NOT NULL DEFAULT '',
            phonetic_us      TEXT NOT NULL DEFAULT ''
        )''')
        cols = [r[1] for r in conn.execute("PRAGMA table_info(words)").fetchall()]
        if 'chinese_sentence' not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN chinese_sentence TEXT NOT NULL DEFAULT ''")
        if 'review_sentence' not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN review_sentence TEXT NOT NULL DEFAULT ''")
        if 'review_sentence_chinese' not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN review_sentence_chinese TEXT NOT NULL DEFAULT ''")
        if 'phonetic' not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN phonetic TEXT NOT NULL DEFAULT ''")
        if 'phonetic_uk' not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN phonetic_uk TEXT NOT NULL DEFAULT ''")
        if 'phonetic_us' not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN phonetic_us TEXT NOT NULL DEFAULT ''")
        conn.commit()

def entry_exists(entry, exclude_id=None):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT id FROM words WHERE LOWER(entry) = LOWER(?) AND id != ?',
            (entry.strip(), exclude_id or -1)
        ).fetchone()
    return row is not None

def sentence_exists(sentence, exclude_id=None):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT id FROM words WHERE LOWER(sentence) = LOWER(?) AND id != ?',
            (sentence.strip(), exclude_id or -1)
        ).fetchone()
    return row is not None

def add_word(entry, type_, sentence, chinese_meaning, english_definition, chinese_sentence='',
             phonetic='', phonetic_uk='', phonetic_us=''):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO words (entry, type, sentence, chinese_meaning, english_definition, chinese_sentence, date_added, phonetic, phonetic_uk, phonetic_us) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (entry.strip(), type_, sentence.strip(), chinese_meaning, english_definition, chinese_sentence, date.today().isoformat(), phonetic, phonetic_uk, phonetic_us)
        )
        conn.commit()

def get_words_for_date(target_date):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            'SELECT id, entry, type, sentence, chinese_meaning, english_definition, chinese_sentence, check_count, date_added, review_sentence, review_sentence_chinese, phonetic, phonetic_uk, phonetic_us FROM words WHERE date_added = ? ORDER BY id',
            (target_date,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]

def get_words_by_ids(ids):
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            'SELECT id, entry, type, sentence, chinese_meaning, english_definition, chinese_sentence, check_count, date_added, review_sentence, review_sentence_chinese, phonetic, phonetic_uk, phonetic_us '
            f'FROM words WHERE id IN ({placeholders})',
            ids
        ).fetchall()
    return [_row_to_dict(r) for r in rows]

def get_weighted_random(exclude_date, count):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            'SELECT id, entry, type, sentence, chinese_meaning, english_definition, chinese_sentence, check_count, date_added, review_sentence, review_sentence_chinese, phonetic, phonetic_uk, phonetic_us FROM words WHERE date_added != ? ORDER BY id',
            (exclude_date,)
        ).fetchall()
    if not rows:
        return []
    words = [_row_to_dict(r) for r in rows]
    weights = [1.0 / (w['check_count'] + 1) for w in words]
    selected = []
    pool = list(zip(words, weights))
    for _ in range(min(count, len(pool))):
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        cum = 0
        for i, (word, weight) in enumerate(pool):
            cum += weight
            if r <= cum:
                selected.append(word)
                pool.pop(i)
                break
    return selected

MAX_REVIEW = 20

def get_review_words(target_date):
    words = get_words_for_date(target_date)
    if len(words) >= MAX_REVIEW:
        result = words[:MAX_REVIEW]
    elif len(words) >= 10:
        result = list(words)
    else:
        extra = get_weighted_random(target_date, 10 - len(words))
        result = (words + extra)[:MAX_REVIEW]
    # Shuffle so newly-added words aren't always listed first in input order —
    # mixing them with older words makes the fill-in-the-blank harder.
    random.shuffle(result)
    return result

def update_entry(word_id, entry, type_, sentence, chinese_meaning, english_definition):
    """Edit a word. Clears review_sentence so it regenerates from the new entry
    on the next review."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE words SET entry = ?, type = ?, sentence = ?, chinese_meaning = ?, "
            "english_definition = ?, review_sentence = '', review_sentence_chinese = '' WHERE id = ?",
            (entry.strip(), type_, sentence.strip(), chinese_meaning.strip(),
             english_definition.strip(), word_id)
        )
        conn.commit()

def update_review_sentence(word_id, review_sentence, review_sentence_chinese=''):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'UPDATE words SET review_sentence = ?, review_sentence_chinese = ? WHERE id = ?',
            (review_sentence, review_sentence_chinese, word_id)
        )
        conn.commit()

def increment_check_count(word_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE words SET check_count = check_count + 1 WHERE id = ?', (word_id,))
        conn.commit()

def get_today_count():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute('SELECT COUNT(*) FROM words WHERE date_added = ?', (date.today().isoformat(),)).fetchone()
    return row[0]

def get_total_count():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute('SELECT COUNT(*) FROM words').fetchone()
    return row[0]

def _row_to_dict(r):
    return dict(zip(['id','entry','type','sentence','chinese_meaning','english_definition','chinese_sentence','check_count','date_added','review_sentence','review_sentence_chinese','phonetic','phonetic_uk','phonetic_us'], r))
