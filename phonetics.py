"""Phonetic (IPA) resolution — dictionary-first, model-fallback.

Strategy (mirrors the app's "deterministic first, LLM only as backup" principle):
  1. Look the word up on Wiktionary (an authoritative external source). This is a
     deterministic lookup — the same word always yields the same standard answer,
     with British (RP) and American (GenAm) transcriptions kept separate.
  2. Only when Wiktionary has no usable IPA (phrases, inflected forms, gaps) do we
     fall back to the Haiku model to *generate* both accents.

`resolve(entry, type_)` -> (uk, us, source) where source is 'wiktionary' | 'ai' | ''.
"""
import urllib.parse
import urllib.request
import json
import re
import time

USER_AGENT = "VocabBuilder/1.0 (personal study tool; https://github.com/kulindexiuxing/vocab_app)"

# Accent qualifiers used by Wiktionary's {{IPA}} templates.
_UK = {'RP', 'UK', 'British', 'GB', 'Britain'}
_US = {'US', 'GA', 'GenAm', 'America', 'American'}


def _fetch_wikitext(word):
    """Return the page wikitext, '' if the page doesn't exist, or None on failure."""
    url = ("https://en.wiktionary.org/w/api.php?action=parse&page="
           + urllib.parse.quote(word)
           + "&prop=wikitext&format=json&formatversion=2&redirects=1")
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception:
            time.sleep(0.4)
            continue
        if 'parse' in data:
            return data['parse']['wikitext']
        if data.get('error', {}).get('code') == 'missingtitle':
            return ''
        time.sleep(0.4)
    return None


def lookup_wiktionary(entry):
    """Return (uk, us) IPA strings from Wiktionary, or (None, None) if unavailable.

    When the entry has IPA but no explicit UK/US label, the first transcription is
    used for both. Prefers /broad/ transcriptions over [narrow] ones.
    """
    wt = _fetch_wikitext(entry.strip())
    if not wt:  # '' (no page) or None (fetch failed)
        return None, None

    m = re.search(r'==English==(.*?)(\n==[^=]|\Z)', wt, re.S)
    english = m.group(1) if m else wt

    uk = us = gen = None
    for tmpl in re.findall(r'\{\{IPA\|en\|([^}]*)\}\}', english):
        accents, values = [], []
        for part in (p.strip() for p in tmpl.split('|')):
            if part.startswith('a='):
                accents += re.split(r'[,/ ]+', part[2:])
            elif part.startswith('/') or part.startswith('['):
                values.append(part)
        slashed = [v for v in values if v.startswith('/')]
        val = slashed[0] if slashed else (values[0] if values else None)
        if not val:
            continue
        # Keep only the /.../ (or [...]) transcription, dropping any trailing
        # wikitext that slipped in (refs, accent tags, etc.).
        mclean = re.match(r'/[^/]*/', val) or re.match(r'\[[^\]]*\]', val)
        if mclean:
            val = mclean.group(0)
        acc = set(accents)
        if acc & _UK and not uk:
            uk = val
        elif acc & _US and not us:
            us = val
        if gen is None:
            gen = val

    if not (uk or gen):
        return None, None
    return uk or gen, us or gen


def resolve(entry, type_='word'):
    """Dictionary-first, model-fallback. Returns (uk, us, source)."""
    uk, us = lookup_wiktionary(entry)
    if uk or us:
        return uk or us, us or uk, 'wiktionary'

    # Fallback: have the model generate both accents.
    try:
        from ai import generate_phonetics
        uk2, us2 = generate_phonetics(entry, type_)
        if uk2 or us2:
            return uk2 or us2, us2 or uk2, 'ai'
    except Exception:
        pass
    return '', '', ''
