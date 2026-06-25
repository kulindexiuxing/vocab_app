import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from flask import Flask, render_template, request, jsonify

from db import (init_db, entry_exists, sentence_exists, add_word, get_review_words,
                increment_check_count, get_today_count, get_total_count, update_review_sentence,
                update_entry, get_words_by_ids)
from ai import generate_meaning, generate_review_sentence, translate_sentence
from phonetics import resolve as resolve_phonetics

app = Flask(__name__)


# ── helpers ──────────────────────────────────────────────

def validate_entry(entry, sentence, exclude_id=None):
    import re
    # Tolerate apostrophe variants (’ vs ' vs ` etc.) so "fool's gold" matches
    # whether the entry and sentence use curly or straight apostrophes.
    escaped = re.sub(r"['’‘`ʼ]", "['’‘`ʼ]", re.escape(entry.strip()))
    if not re.search(escaped, sentence.strip(), re.IGNORECASE):
        return f'句子中找不到 "{entry}"，请确保句子原文包含该单词或短语'
    if sentence_exists(sentence, exclude_id):
        return '这个句子已经存在于词库中，请换一个句子'
    return None


# ── routes ───────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html',
                           today_count=get_today_count(),
                           total_count=get_total_count())

@app.route('/add', methods=['POST'])
def add():
    entry    = request.form.get('entry', '').strip()
    type_    = request.form.get('type', 'word')
    sentence = request.form.get('sentence', '').strip()

    if not entry or not sentence:
        return jsonify({'error': '请填写内容和句子'}), 400

    if entry_exists(entry):
        return jsonify({'error': f'"{entry}" 已在词库中'}), 400

    err = validate_entry(entry, sentence)
    if err:
        return jsonify({'error': err}), 400

    try:
        chinese, english, chinese_sentence = generate_meaning(entry, type_, sentence)
    except Exception as e:
        return jsonify({'error': f'AI 生成失败：{e}'}), 500

    uk, us, _src = resolve_phonetics(entry, type_)
    add_word(entry, type_, sentence, chinese, english, chinese_sentence,
             phonetic='', phonetic_uk=uk, phonetic_us=us)

    return jsonify({
        'success':            True,
        'chinese_meaning':    chinese,
        'english_definition': english,
        'chinese_sentence':   chinese_sentence,
        'phonetic_uk':        uk,
        'phonetic_us':        us,
        'today_count':        get_today_count(),
        'total_count':        get_total_count(),
    })

@app.route('/review')
def review():
    target_date  = (date.today() - timedelta(days=1)).isoformat()
    words        = get_review_words(target_date)

    # Fill in any missing review sentence, then cache it (fast loads on later visits).
    # The "🔄 换一批例句" button (/regenerate) is how the user deliberately gets fresh ones.
    needs = [w for w in words
             if not w.get('review_sentence') or not w.get('review_sentence_chinese')]
    if needs:
        def _gen(w):
            rs, rs_zh = generate_review_sentence(
                w['entry'], w['type'], w['sentence'], w['chinese_meaning'],
                avoid=w.get('review_sentence') or '')
            return w['id'], rs, rs_zh

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_gen, w): w for w in needs}
            for future in as_completed(futures):
                w = futures[future]
                try:
                    word_id, rs, rs_zh = future.result()
                    update_review_sentence(word_id, rs, rs_zh)
                    w['review_sentence'] = rs
                    w['review_sentence_chinese'] = rs_zh
                except Exception:
                    w['review_sentence'] = w.get('review_sentence') or w['sentence']
                    w['review_sentence_chinese'] = w.get('review_sentence_chinese') or w.get('chinese_sentence', '')

    target_count = sum(1 for w in words if w['date_added'] == target_date)
    extra_count  = len(words) - target_count
    label        = (date.today() - timedelta(days=1)).strftime('%Y年%-m月%-d日') + ' · 每日复习'

    return render_template('review.html',
                           words=words,
                           session_label=label,
                           target_count=target_count,
                           extra_count=extra_count)

@app.route('/batch', methods=['POST'])
def batch():
    type_    = request.form.get('type', 'word')
    raw      = request.form.get('entries', '').strip()

    if not raw:
        return jsonify({'error': '请输入内容'}), 400

    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    results = []

    for line in lines:
        if '|' not in line:
            results.append({'line': line, 'status': 'error', 'msg': '格式错误，缺少 | 分隔符'})
            continue

        parts   = line.split('|', 1)
        entry   = parts[0].strip()
        sentence = parts[1].strip()

        if not entry or not sentence:
            results.append({'line': line, 'status': 'error', 'msg': '单词或句子为空'})
            continue

        if entry_exists(entry):
            results.append({'line': line, 'entry': entry, 'status': 'skip', 'msg': '已在词库中'})
            continue

        err = validate_entry(entry, sentence)
        if err:
            results.append({'line': line, 'entry': entry, 'status': 'error', 'msg': err})
            continue

        try:
            chinese, english, chinese_sentence = generate_meaning(entry, type_, sentence)
            uk, us, _src = resolve_phonetics(entry, type_)
            add_word(entry, type_, sentence, chinese, english, chinese_sentence,
                     phonetic='', phonetic_uk=uk, phonetic_us=us)
            results.append({
                'line':    line,
                'entry':   entry,
                'status':  'ok',
                'chinese': chinese,
                'english': english,
                'phonetic_uk': uk,
                'phonetic_us': us,
            })
        except Exception as e:
            results.append({'line': line, 'entry': entry, 'status': 'error', 'msg': str(e)})

    return jsonify({
        'results':     results,
        'today_count': get_today_count(),
        'total_count': get_total_count(),
    })

@app.route('/edit', methods=['POST'])
def edit():
    data     = request.get_json() or {}
    word_id  = data.get('word_id')
    entry    = (data.get('entry') or '').strip()
    type_    = data.get('type', 'word')
    sentence = (data.get('sentence') or '').strip()
    chinese  = (data.get('chinese_meaning') or '').strip()
    english  = (data.get('english_definition') or '').strip()

    if not word_id:
        return jsonify({'error': '缺少 word_id'}), 400
    if not entry or not sentence:
        return jsonify({'error': '请填写内容和句子'}), 400
    if not chinese or not english:
        return jsonify({'error': '请填写中文与英文释义'}), 400

    if entry_exists(entry, exclude_id=word_id):
        return jsonify({'error': f'"{entry}" 已在词库中'}), 400

    err = validate_entry(entry, sentence, exclude_id=word_id)
    if err:
        return jsonify({'error': err}), 400

    update_entry(word_id, entry, type_, sentence, chinese, english)

    return jsonify({
        'success':            True,
        'word_id':            word_id,
        'entry':              entry,
        'type':               type_,
        'sentence':           sentence,
        'chinese_meaning':    chinese,
        'english_definition': english,
    })

@app.route('/regenerate', methods=['POST'])
def regenerate():
    """Generate a fresh batch of fill-in sentences for the given words, each told to
    avoid its previous sentence. Backs the '🔄 换一批例句' button."""
    ids = (request.get_json() or {}).get('word_ids', [])
    if not ids:
        return jsonify({'error': '缺少 word_ids'}), 400

    words = get_words_by_ids(ids)

    def _gen(w):
        rs, rs_zh = generate_review_sentence(
            w['entry'], w['type'], w['sentence'], w['chinese_meaning'],
            avoid=w.get('review_sentence') or '')
        return w['id'], rs, rs_zh

    out = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_gen, w): w for w in words}
        for future in as_completed(futures):
            try:
                word_id, rs, rs_zh = future.result()
                update_review_sentence(word_id, rs, rs_zh)
                out[word_id] = {'review_sentence': rs, 'review_sentence_chinese': rs_zh}
            except Exception:
                pass

    return jsonify({'sentences': out})

@app.route('/check', methods=['POST'])
def check():
    word_id = (request.get_json() or {}).get('word_id')
    if word_id:
        increment_check_count(word_id)
    return jsonify({'success': True})


# ── main ─────────────────────────────────────────────────

def _open_browser_once():
    marker = '/tmp/vocab_browser_opened'
    today = date.today().isoformat()
    try:
        with open(marker) as f:
            if f.read().strip() == today:
                return
    except FileNotFoundError:
        pass
    with open(marker, 'w') as f:
        f.write(today)
    subprocess.run(['open', 'http://localhost:5001/review'])

if __name__ == '__main__':
    init_db()
    threading.Timer(2.0, _open_browser_once).start()

    print('\n✅  VocabBuilder 已启动')
    print('📖  添加生词：http://localhost:5001')
    print('📝  每日复习：http://localhost:5001/review')
    print('    按 Ctrl+C 退出\n')

    app.run(port=5001, debug=False, use_reloader=False)
