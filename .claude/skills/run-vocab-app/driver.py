#!/usr/bin/env python3
"""
Smoke driver for VocabBuilder (Flask app at ~/vocab_app).

Default mode is ISOLATED: it points the DB at a throwaway temp file, seeds a
couple of rows directly (no AI / no API key), and exercises the routes that
don't call Anthropic via Flask's test client. It never touches the real
vocab.db and needs no network.

  python3 .claude/skills/run-vocab-app/driver.py          # isolated smoke (default)
  python3 .claude/skills/run-vocab-app/driver.py --live   # curl a server already on :5001

The AI routes (/add, /batch, and /review when it must generate sentences) need
ANTHROPIC_API_KEY and are intentionally NOT exercised here — they cost tokens
and mutate data. See SKILL.md for how to drive them manually.
"""
import os
import sys
import tempfile

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def smoke_isolated():
    sys.path.insert(0, APP_DIR)
    import db  # noqa: E402

    # Redirect the DB to a temp file BEFORE init — every db.* fn reads
    # db.DB_PATH at call time, so this fully isolates us from the real library.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db.DB_PATH = tmp.name

    import app as appmod  # noqa: E402

    failures = []

    def check(label, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures.append(label)

    try:
        db.init_db()
        # Seed two rows directly (bypasses AI).
        db.add_word("ubiquitous", "word",
                    "Smartphones are ubiquitous these days.",
                    "无处不在的", "present everywhere", "如今智能手机无处不在。")
        db.add_word("kick the bucket", "idiom",
                    "The old car finally kicked the bucket.",
                    "翘辫子（死）", "to die", "那辆旧车终于报废了。")

        client = appmod.app.test_client()

        print("Route checks (isolated temp DB):")
        r = client.get("/")
        check("GET / -> 200", r.status_code == 200)
        check("GET / has app title", b"VocabBuilder" in r.data)
        check("GET / shows total=2", b"2" in r.data)

        r = client.get("/review")
        check("GET /review -> 200", r.status_code == 200)

        r = client.post("/check", json={"word_id": 1})
        check("POST /check -> success", r.status_code == 200 and r.get_json().get("success") is True)

        r = client.post("/edit", json={
            "word_id": 1, "entry": "ubiquitous", "type": "word",
            "sentence": "Plastic is ubiquitous in the ocean.",
            "chinese_meaning": "无处不在的", "english_definition": "present everywhere",
        })
        check("POST /edit -> success", r.status_code == 200 and r.get_json().get("success") is True)

        # Negative path: bad word raises validation error (no AI hit).
        r = client.post("/add", data={"entry": "zzz", "type": "word", "sentence": "no match here"})
        check("POST /add bad input -> 400", r.status_code == 400)
    finally:
        os.unlink(tmp.name)

    print()
    if failures:
        print(f"SMOKE FAILED: {len(failures)} check(s) failed -> {failures}")
        return 1
    print("SMOKE PASSED (isolated)")
    return 0


def smoke_live():
    import urllib.request
    base = "http://127.0.0.1:5001"  # 127.0.0.1, not localhost (Flask binds IPv4)
    # Bypass any HTTP proxy in the environment — a proxy can't reach localhost
    # and returns 502. An empty ProxyHandler forces a direct connection.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    failures = []

    def get(path):
        try:
            with opener.open(base + path, timeout=5) as resp:
                return resp.status, resp.read()
        except Exception as e:
            return None, str(e).encode()

    print(f"Live checks against {base} (must be running, e.g. `vocab`):")
    for path, needle in [("/", b"VocabBuilder"), ("/review", b"VocabBuilder")]:
        status, body = get(path)
        ok = status == 200 and needle in body
        print(f"  [{'PASS' if ok else 'FAIL'}] GET {path} -> {status}")
        if not ok:
            failures.append(path)

    print()
    if failures:
        print(f"LIVE SMOKE FAILED: {failures}  (is the server running on :5001?)")
        return 1
    print("LIVE SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(smoke_live() if "--live" in sys.argv else smoke_isolated())
