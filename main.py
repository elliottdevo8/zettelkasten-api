"""
Zettelkasten API -- Phase 5
FastAPI skeleton + file reader + search + write/update endpoints + Org formatter + API key auth
"""

import os
import re
import sqlite3
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.getenv("ZETTELKASTEN_API_KEY")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(_api_key_header)):
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(os.getenv("ZETTELKASTEN_BASE_DIR", str(Path.home() / "Documents/SelfDevelopment")))
DB_PATH = BASE_DIR / ".org-roam.db"
LOG_PATH = BASE_DIR / "logs" / "zettelkasten-api.log"

SEARCH_DIRS = [
    BASE_DIR / "05-Zettelkasten",
    BASE_DIR / "01-Projects",
    BASE_DIR / "02-Areas",
    BASE_DIR / "03-Resources",
    BASE_DIR / "07-Journals",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("zettelkasten-api")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Zettelkasten API",
    description="Local knowledge API for Claude, GPT-4, Gemini and user access.",
    version="0.5.0",
)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def db_connect():
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="org-roam.db not found")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _dq(s: str) -> str:
    """Strip surrounding double-quotes org-roam stores in SQLite."""
    return s.strip('"') if s else s


def db_node_by_id(node_id: str) -> Optional[dict]:
    # org-roam stores IDs wrapped in double-quotes; try both forms
    quoted_id = f'"{node_id.strip(chr(34))}"'
    bare_id = node_id.strip('"')
    with db_connect() as conn:
        row = None
        for lookup in (bare_id, quoted_id):
            cur = conn.execute(
                "SELECT id, title, file, level FROM nodes WHERE id = ?", (lookup,)
            )
            row = cur.fetchone()
            if row:
                break
        if not row:
            return None
        stored_id = row["id"]
        tags = [
            _dq(r["tag"])
            for r in conn.execute(
                "SELECT tag FROM tags WHERE node_id = ?", (stored_id,)
            ).fetchall()
        ]
        return {
            "id": _dq(row["id"]),
            "title": _dq(row["title"]),
            "file": _dq(row["file"]),
            "level": row["level"],
            "tags": tags,
            "_stored_id": stored_id,  # kept for internal DB lookups
        }


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def read_file(path: str) -> str:
    p = Path(path.strip('"'))
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return p.read_text(encoding="utf-8")


def parse_org_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#+title:") or line.startswith("#+TITLE:"):
            return line.split(":", 1)[1].strip()
    return "(untitled)"


def parse_md_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip('"')
    return "(untitled)"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class NoteCreate(BaseModel):
    title: str
    type: str                  # "fleeting" | "literature" | "permanent"
    tags: list[str] = []
    body: str = ""
    filename_prefix: str = ""  # e.g. "Author-2024" for literature notes


class NoteUpdate(BaseModel):
    body: str                  # replaces everything after the org header block


# ---------------------------------------------------------------------------
# Org formatter helpers
# ---------------------------------------------------------------------------

NOTE_DIRS = {
    "fleeting":   BASE_DIR / "05-Zettelkasten" / "Fleeting",
    "literature": BASE_DIR / "05-Zettelkasten" / "Literature",
    "permanent":  BASE_DIR / "05-Zettelkasten" / "Permanent",
}

_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_BODY_SKELETONS = {
    "fleeting": (
        "* Quick Capture\n\n\n"
        "* Why This Matters\n\n\n"
        "* Next Steps\n"
        "- [ ] Develop into literature note\n"
        "- [ ] Research further\n\n"
        "* Potential Connections\n"
        "- [[]]\n\n"
        "* Source/Context\n"
    ),
    "literature": (
        "* Source Information\n"
        "- *Full Citation:*\n"
        "- *Source URL/Location:*\n\n"
        "* Key Ideas\n\n"
        "** Idea 1\n\n"
        "* Personal Reactions\n\n\n"
        "* Connections\n"
        "- Connects to: [[]]\n\n"
        "* Potential Permanent Notes\n"
        "- [ ] [[]]\n"
    ),
    "permanent": (
        "* Core Idea\n\n\n"
        "* Explanation\n\n\n"
        "* Why This Matters\n\n\n"
        "* Supporting Evidence\n\n\n"
        "* Connected Ideas\n"
        "- *Builds on:* [[]]\n"
        "- *Supports:* [[]]\n"
    ),
}


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def make_org_id(title: str, ts: datetime) -> str:
    return f"{ts.strftime('%Y-%m-%d')}-{slugify(title)}"


def make_org_filename(note_type: str, title: str, ts: datetime, prefix: str = "") -> str:
    if note_type == "fleeting":
        return f"{ts.strftime('%Y-%m-%d-%H%M')}-{slugify(title)}.org"
    if note_type == "literature":
        return f"{prefix}.org" if prefix else f"{ts.year}-{slugify(title)}.org"
    # permanent
    return f"{slugify(title)}.org"


def format_org_header(title: str, note_type: str, tags: list[str], org_id: str, ts: datetime) -> str:
    day = _DAY_ABBR[ts.weekday()]
    date_str = ts.strftime(f"%Y-%m-%d {day} %H:%M")
    all_tags = [note_type] + [t for t in tags if t != note_type]
    filetags = ":" + ":".join(all_tags) + ":"
    return (
        f":PROPERTIES:\n"
        f":ID:       {org_id}\n"
        f":END:\n"
        f"#+title: {title}\n"
        f"#+date: [{date_str}]\n"
        f"#+filetags: {filetags}\n"
    )


def format_org_body(note_type: str, body: str) -> str:
    if body.strip():
        return f"* Content\n{body.strip()}\n"
    return _BODY_SKELETONS.get(note_type, "* Content\n\n")


def split_org_header_body(text: str) -> tuple[str, str]:
    m = re.search(r"^\* ", text, re.MULTILINE)
    if m:
        return text[: m.start()].rstrip(), text[m.start():]
    return text, ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    db_ok = DB_PATH.exists()
    return {
        "status": "ok",
        "db": str(DB_PATH) if db_ok else "missing",
        "db_ok": db_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/index", dependencies=[Depends(require_api_key)])
def get_index():
    """Return all nodes from org-roam DB with tags."""
    with db_connect() as conn:
        nodes = conn.execute(
            "SELECT id, title, file, level FROM nodes ORDER BY title"
        ).fetchall()
        result = []
        for n in nodes:
            tags = [
                _dq(r["tag"])
                for r in conn.execute(
                    "SELECT tag FROM tags WHERE node_id = ?", (n["id"],)
                ).fetchall()
            ]
            result.append(
                {
                    "id": _dq(n["id"]),
                    "title": _dq(n["title"]),
                    "file": Path(_dq(n["file"])).name,
                    "level": n["level"],
                    "tags": tags,
                }
            )
    log.info(f"GET /index -> {len(result)} nodes")
    return {"count": len(result), "nodes": result}


@app.get("/note/{node_id}", dependencies=[Depends(require_api_key)])
def get_note(node_id: str):
    """Fetch a note by org-roam node ID. Returns metadata + full content."""
    node = db_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    content = read_file(node["file"])
    log.info(f"GET /note/{node_id} -> {node['title']}")
    return {
        "id": node["id"],
        "title": node["title"],
        "file": node["file"],
        "level": node["level"],
        "tags": node["tags"],
        "content": content,
    }



@app.get("/search", dependencies=[Depends(require_api_key)])
def search(
    q: str = Query(..., description="Search query"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    type: Optional[str] = Query(None, description="Filter by type: org or md"),
):
    """
    Full-text search using ripgrep across all note directories.
    Falls back gracefully if ripgrep is not installed.
    """
    globs = []
    if type == "org":
        globs = ["--glob", "*.org"]
    elif type == "md":
        globs = ["--glob", "*.md"]
    else:
        globs = ["--glob", "*.org", "--glob", "*.md"]

    search_paths = [str(d) for d in SEARCH_DIRS if d.exists()]

    cmd = (
        ["rg", "--ignore-case", "--line-number", "--with-filename", "--max-count", "3"]
        + globs
        + [q]
        + search_paths
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().splitlines()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="ripgrep (rg) not installed")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Search timed out")

    hits: dict[str, Any] = {}
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        filepath, lineno, snippet = parts[0], parts[1], parts[2].strip()
        if filepath not in hits:
            hits[filepath] = {
                "file": filepath,
                "filename": Path(filepath).name,
                "snippets": [],
            }
        hits[filepath]["snippets"].append({"line": int(lineno), "text": snippet})

    # Tag filter via DB
    results = list(hits.values())
    if tag:
        with db_connect() as conn:
            tagged = set(
                r["file"].strip('"')
                for r in conn.execute(
                    "SELECT n.file FROM nodes n JOIN tags t ON t.node_id = n.id "
                    "WHERE LOWER(t.tag) = ?",
                    (tag.lower(),),
                ).fetchall()
            )
        results = [r for r in results if r["file"] in tagged]

    log.info(f"GET /search q={q!r} tag={tag} type={type} -> {len(results)} files")
    return {"query": q, "count": len(results), "results": results}


@app.get("/tags", dependencies=[Depends(require_api_key)])
def get_tags():
    """Return all tags and their node counts from org-roam DB."""
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC"
        ).fetchall()
    tags = [{"tag": _dq(r["tag"]), "count": r["count"]} for r in rows]
    log.info(f"GET /tags -> {len(tags)} tags")
    return {"count": len(tags), "tags": tags}


@app.post("/note", status_code=201, dependencies=[Depends(require_api_key)])
def create_note(note: NoteCreate):
    """Create a new Org-mode note in the correct Zettelkasten directory."""
    if note.type not in NOTE_DIRS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{note.type}'. Must be one of: {list(NOTE_DIRS)}",
        )
    ts = datetime.now()
    org_id = make_org_id(note.title, ts)
    filename = make_org_filename(note.type, note.title, ts, note.filename_prefix)
    filepath = NOTE_DIRS[note.type] / filename
    if filepath.exists():
        raise HTTPException(status_code=409, detail=f"File already exists: {filepath}")
    header = format_org_header(note.title, note.type, note.tags, org_id, ts)
    body = format_org_body(note.type, note.body)
    filepath.write_text(header + "\n" + body, encoding="utf-8")
    log.info(f"POST /note -> created {filepath}")
    return {"id": org_id, "file": str(filepath), "title": note.title, "type": note.type}


@app.put("/note/{node_id}", dependencies=[Depends(require_api_key)])
def update_note(node_id: str, update: NoteUpdate):
    """Replace the body of an existing note, preserving the org-roam header."""
    node = db_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    existing = read_file(node["file"])
    header, _ = split_org_header_body(existing)
    filepath = Path(node["file"])
    filepath.write_text(header + "\n\n" + update.body.strip() + "\n", encoding="utf-8")
    log.info(f"PUT /note/{node_id} -> updated {filepath}")
    return {"id": node["id"], "file": node["file"], "updated": True}
