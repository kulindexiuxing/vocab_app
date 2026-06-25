import anthropic
import json

TYPE_LABELS = {
    'word':       'word',
    'phrasal':    'phrasal verb',
    'idiom':      'idiom',
    'expression': 'expression',
}

def generate_meaning(entry, type_, sentence):
    label = TYPE_LABELS.get(type_, 'word')
    prompt = f"""The user encountered this English {label}: "{entry}"
It was used in this sentence: "{sentence}"

Provide:
1. Chinese meaning of "{entry}" as used in this specific sentence (concise, 1-2 lines)
2. Brief English definition (1 line)
3. Natural Chinese translation of the full sentence

Return ONLY valid JSON, no markdown:
{{"chinese_meaning": "...", "english_definition": "...", "chinese_sentence": "..."}}"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=400,
        messages=[{'role': 'user', 'content': prompt}]
    )

    text = message.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()

    result = json.loads(text)
    return result['chinese_meaning'], result['english_definition'], result.get('chinese_sentence', '')


def generate_review_sentence(entry, type_, original_sentence, chinese_meaning, avoid=''):
    label = TYPE_LABELS.get(type_, 'word')
    avoid_clean = (avoid or '').replace('[[', '').replace(']]', '').strip()
    avoid_block = (
        f'\nPreviously shown sentence (write something CLEARLY different — different scenario, '
        f'subject, and wording, not a minor reword): "{avoid_clean}"' if avoid_clean else ''
    )
    prompt = f"""The user is learning the English {label}: "{entry}"
It means: {chinese_meaning}
Original context sentence: "{original_sentence}"{avoid_block}

Write ONE new natural English sentence that uses "{entry}" with exactly the same meaning as in the original. It may be conjugated, or have pronouns/placeholders filled in to fit the grammar (e.g. "pull oneself up by one's bootstraps" → "pulled herself up by her bootstraps").

In the English sentence, wrap the EXACT words where "{entry}" actually appears in double square brackets, like: [[pulled herself up by her bootstraps]]. Bracket only that phrase, nothing else. The sentence must differ from the original. Then give a natural Chinese translation (do NOT put any brackets in the Chinese).

Return ONLY valid JSON, no markdown:
{{"sentence": "...", "chinese_sentence": "..."}}"""

    client = anthropic.Anthropic()
    multiword = len(entry.strip().split()) > 1

    sentence = chinese = ''
    for _attempt in range(2):
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = message.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()
        result = json.loads(text)
        sentence = result['sentence'].strip()
        chinese = result.get('chinese_sentence', '').strip()
        # Retry once if a multi-word phrase came back without the [[ ]] marker — an
        # unmarked inflected idiom can't be blanked. Single words don't need the marker
        # (the literal fallback handles them), so accept on the first try.
        if not (multiword and '[[' not in sentence):
            break
    return sentence, chinese


def generate_phonetics(entry, type_='word'):
    """Fallback IPA generator (used only when Wiktionary has no entry).
    Returns (uk, us) — British RP and American GenAm transcriptions."""
    label = TYPE_LABELS.get(type_, 'word')
    prompt = f"""Give the IPA pronunciation of this English {label}: "{entry}"

Provide BOTH:
- "uk": British Received Pronunciation (RP)
- "us": American General American (GenAm)

Rules:
- Wrap each transcription in slashes, e.g. /ˈel.ə.kwənt/
- Use the plain symbol /r/ (not ɹ) for the r-sound, matching standard learner dictionaries
- Use /ə/ for unstressed/weak vowels
- Mark primary stress with ˈ
- For a multi-word phrase, transcribe the whole phrase

Return ONLY valid JSON, no markdown:
{{"uk": "/.../", "us": "/.../"}}"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=150,
        messages=[{'role': 'user', 'content': prompt}]
    )

    text = message.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()

    result = json.loads(text)
    return result.get('uk', '').strip(), result.get('us', '').strip()


def translate_sentence(sentence):
    prompt = f"""Translate this English sentence into natural Chinese.
Return ONLY the Chinese translation, no quotes, no explanation.

"{sentence}\""""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=200,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text.strip()
