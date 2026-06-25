---
name: run-vocab-app
description: Run, launch, start, build, or smoke-test the VocabBuilder Flask app (~/vocab_app, localhost:5001). Use when asked to run vocab, start the vocab app, test the vocab routes, or verify a change to it.
---

# Run VocabBuilder

VocabBuilder is a small **Flask** web app for learning English vocabulary
(add words → AI generates Chinese/English meanings → daily review). It serves
on **http://127.0.0.1:5001**. There is no build step — it's plain Python.

All paths below are relative to the app root (`~/vocab_app`).

The agent-facing way to drive it is the smoke driver at
`.claude/skills/run-vocab-app/driver.py` — it has an **isolated** mode (temp
DB, no API key, no network) and a **--live** mode (curls a running server).

## Prerequisites

```bash
python3 -m pip install flask anthropic      # only deps (see requirements.txt)
```

Verified on macOS with Python 3.14.5, Flask 3.1.3.

The AI routes (`/add`, `/batch`, and `/review` when it generates sentences)
call Anthropic and need `ANTHROPIC_API_KEY` exported. The smoke driver does
**not** use them, so it runs without a key.

## Run (agent path) — the driver

Default = **isolated** smoke. Points the DB at a throwaway temp file, seeds two
rows directly, and exercises every non-AI route via Flask's test client. Never
touches the real `vocab.db`, needs no API key, no network:

```bash
python3 .claude/skills/run-vocab-app/driver.py
```

Expected tail: `SMOKE PASSED (isolated)` (7 PASS lines, exit 0).

To check a server that's already running on :5001:

```bash
python3 .claude/skills/run-vocab-app/driver.py --live
```

Expected: `LIVE SMOKE PASSED`. If it can't connect, the server isn't up — start
it (human path below).

### Driving routes by hand (curl)

Read-only routes need no key. **Use `127.0.0.1`, not `localhost`** (see Gotchas):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/         # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/review   # 200
```

Inspect DB counts without the server:

```bash
python3 -c "import db; print('total:', db.get_total_count(), '| today:', db.get_today_count())"
```

## Run (human path)

A `vocab` zsh alias exists: `cd ~/vocab_app && python3 app.py`. In an
interactive shell just type `vocab`. It prints a startup banner, on **macOS**
auto-opens the browser after 2s, and blocks until Ctrl+C. Equivalent directly:

```bash
python3 app.py     # serves on :5001, Ctrl+C to stop
```

Useless in a headless/non-interactive shell (it blocks and the browser-open is
macOS-only) — use the driver instead.

## Gotchas

- **`localhost` can fail where `127.0.0.1` works.** Flask binds IPv4 only, and
  in a sandboxed shell `localhost` may resolve to IPv6 *or* get routed through
  an HTTP proxy that returns `502 Bad Gateway`. `curl` quietly works around it;
  Python's `urllib` does not. Always hit `http://127.0.0.1:5001`. The `--live`
  driver also installs an empty `ProxyHandler` to force a direct connection.
- **Port 5001 is hardcoded** in `app.py` (`app.run(port=5001)`). A second
  launch dies with `Address already in use`. Check first:
  `lsof -iTCP:5001 -sTCP:LISTEN`. To run a second copy, edit the port or use
  the driver's isolated mode.
- **The real DB is `vocab.db` in the app root** (path is derived from
  `db.py`'s location). `db.DB_PATH` is read at every call, so setting it before
  `init_db()` fully redirects to a temp DB — that's how the driver stays
  isolated. Don't run AI routes against the real server casually; they mutate
  this file.
- **`/add` validates the sentence contains the word** (`validate_entry`, regex,
  case-insensitive) before calling AI, and rejects duplicate words/sentences.
  A bad payload returns `400` *without* spending tokens — handy for testing.
- **macOS-only browser open:** `app.py` calls `subprocess.run(['open', ...])`
  on a 2s timer (guarded by `/tmp/vocab_browser_opened` once per day). On Linux
  `open` doesn't exist — the timer errors in a background thread but the server
  keeps serving.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Address already in use` / `Port 5001 is in use` | An instance is already up. `lsof -iTCP:5001 -sTCP:LISTEN`; reuse it or `kill <pid>`. |
| `--live` driver fails with connection error / 502 | Server isn't running, or you used `localhost`. Start it (`vocab`) and the driver already targets `127.0.0.1` with proxy bypass. |
| `/add` returns `AI 生成失败` (500) | `ANTHROPIC_API_KEY` not exported, or no network. The smoke driver avoids AI on purpose. |
| `ModuleNotFoundError: flask` / `anthropic` | `python3 -m pip install flask anthropic`. |
