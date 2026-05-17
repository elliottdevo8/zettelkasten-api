# Zettelkasten API

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tested%20with-pytest-brightgreen)

**Any LLM. One API. Your notes, always reachable.**

Keep your knowledge in plain Org-mode and Markdown files — and let every AI model you use read from and write to the same graph. Claude, GPT-4, Gemini, DeepSeek, Kimi, and Qwen all share one local REST endpoint. Knowledge persists across sessions and models.

## Why?

Most AI tools keep knowledge siloed per session or per model. This API solves that:

- **One source of truth** — your local Zettelkasten files, never locked in a vendor
- **Multi-model** — Claude uses native MCP tools; every other LLM calls REST with an API key
- **Persistent** — notes survive conversation resets; build a knowledge graph over months
- **Private** — the server runs on `127.0.0.1`; no cloud sync, no data leaving your machine

## Architecture

```
                        User
                          |
          +---------------+---------------+
          |               |               |
        CLI           Claude           GPT-4 / Gemini
          |               |           DeepSeek / Kimi / Qwen
          |           MCP tools           |
          |               |               |
          +--------> FastAPI :8000 <------+
                          |
                 Org-mode + Markdown
                 (local filesystem)
```

Claude connects natively via the MCP wrapper (`mcp_server.py`), which translates tool calls to REST. All other LLMs call the REST API directly with an `X-API-Key` header.

## Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | None | Server health check |
| `GET` | `/search?q=...` | Key | Full-text search (ripgrep backend) |
| `GET` | `/note/{id}` | Key | Fetch a note by org-roam ID |
| `POST` | `/note` | Key | Create a new note (fleeting / literature / permanent) |
| `PUT` | `/note/{id}` | Key | Update an existing note body |
| `GET` | `/index` | Key | All nodes with tags from org-roam DB |
| `GET` | `/tags` | Key | Aggregate tag counts |

Search supports optional filters: `?tag=RHCSA`, `?type=org`, `?type=md`.

## Setup

**Requirements:** Python 3.11+, [ripgrep](https://github.com/BurntSushi/ripgrep), org-roam SQLite DB.

```bash
pip install -r requirements.txt

# Generate an API key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Create .env (not committed)
cp .env.example .env
# Edit .env — set ZETTELKASTEN_API_KEY and ZETTELKASTEN_BASE_DIR
```

## Running

**One-shot:**
```bash
bash start.sh
```

**As a systemd user service (auto-start on login):**
```bash
bash install.sh
systemctl --user enable --now zettelkasten-api.service
systemctl --user enable --now zettelkasten-capture.timer   # daily capture at 07:00
```

## Authentication

All routes except `/health` require an `X-API-Key` header:

```bash
curl -H "X-API-Key: $ZETTELKASTEN_API_KEY" http://localhost:8000/tags
```

## Multi-LLM Integration

Client scripts in `llm_clients/` show how each LLM calls the API using its native function-calling mechanism:

| File | LLM | SDK |
|------|-----|-----|
| `gpt4_client.py` | GPT-4o | `openai` |
| `gemini_client.py` | Gemini 2.0 Flash | `google-generativeai` |
| `deepseek_client.py` | DeepSeek-V4-Pro | `openai` (drop-in, `api.deepseek.com`) |
| `kimi_client.py` | Kimi-K2.6 | `openai` (drop-in, `api.moonshot.ai`) |
| `qwen_client.py` | Qwen3.5 | `openai` (OpenRouter / DashScope) |

DeepSeek, Kimi, and Qwen are OpenAI SDK drop-ins — same `tools` schema, different `base_url`.

Add the relevant API keys to `.env` (see `.env.example`), then run any client directly:
```bash
python3 llm_clients/gpt4_client.py
```

## Claude / MCP Integration

`mcp_server.py` wraps the REST API as Claude-native tools. Register it in `~/.claude.json`:

```json
{
  "mcpServers": {
    "zettelkasten": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/scripts/zettelkasten-api/mcp_server.py"]
    }
  }
}
```

Available tools: `search_knowledge`, `get_note`, `create_note`, `update_note`, `list_tags`, `get_index`.

## Auto-Capture

Two capture scripts run on a systemd timer (daily at 07:00):

- **`capture-rss.py`** — polls configured RSS feeds and saves new items as fleeting notes. Add feed URLs to `FEED_URLS` at the top of the file. Supports `--dry-run`.
- **`capture-daily-journal.py`** — idempotently creates today's Markdown journal from template and reminds you of unprocessed fleeting notes from yesterday.

## Note Types

Notes are written to the Zettelkasten directory automatically by type:

| Type | Directory | Use |
|------|-----------|-----|
| `fleeting` | `05-Zettelkasten/Fleeting/` | Quick captures, temporary |
| `literature` | `05-Zettelkasten/Literature/` | Source summaries |
| `permanent` | `05-Zettelkasten/Permanent/` | Developed, atomic insights |

## Tests

```bash
pytest tests/
```

## Phase History

| Phase | Feature |
|-------|---------|
| 1 | FastAPI skeleton + Org/Markdown file reader |
| 2 | Search endpoint (ripgrep backend) + test suite |
| 3 | Write/update endpoints + Org formatter |
| 4 | MCP wrapper for Claude native tool use |
| 5 | API key auth + multi-LLM client scripts |
| 6 | Auto-capture scripts + systemd units |

## License

MIT — see [LICENSE](LICENSE).
