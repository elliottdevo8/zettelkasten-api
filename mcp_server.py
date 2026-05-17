"""
Zettelkasten MCP Server — Phase 5
Exposes the Zettelkasten REST API as native Claude tools via MCP stdio transport.
Injects X-API-Key from environment for all authenticated routes.
"""

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")
API_BASE = "http://127.0.0.1:8000"
API_KEY = os.getenv("ZETTELKASTEN_API_KEY", "")

mcp = FastMCP("zettelkasten")

_HEADERS = {"X-API-Key": API_KEY}


def _get(path: str, **params: Any) -> dict[str, Any]:
    try:
        r = httpx.get(
            f"{API_BASE}{path}",
            params={k: v for k, v in params.items() if v is not None},
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "Zettelkasten API server is not running on localhost:8000. Start it with: cd scripts/zettelkasten-api && python3 -m uvicorn main:app --host 127.0.0.1 --port 8000"}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error {e.response.status_code}: {e.response.text}"}


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=body, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "Zettelkasten API server is not running on localhost:8000"}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error {e.response.status_code}: {e.response.text}"}


def _put(path: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        r = httpx.put(f"{API_BASE}{path}", json=body, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        return {"error": "Zettelkasten API server is not running on localhost:8000"}
    except httpx.HTTPStatusError as e:
        return {"error": f"API error {e.response.status_code}: {e.response.text}"}


@mcp.tool()
def search_notes(q: str, tag: str | None = None, type: str | None = None) -> dict[str, Any]:
    """
    Full-text search across all Zettelkasten and PARA notes.

    Args:
        q: Search query string (required)
        tag: Filter results to notes with this tag (optional)
        type: Filter by file type — "org" or "md" (optional, default: both)

    Returns dict with 'count' and 'results' list, each result having
    'filename', 'file' (full path), and 'snippets' (list of {line, text}).
    """
    return _get("/search", q=q, tag=tag, type=type)


@mcp.tool()
def get_note(node_id: str) -> dict[str, Any]:
    """
    Fetch the full content and metadata of a note by its org-roam node ID.

    Args:
        node_id: The org-roam node ID (e.g. "2026-01-31-knowledge-career-bridge")

    Returns dict with 'id', 'title', 'file', 'level', 'tags', and 'content'.
    """
    return _get(f"/note/{node_id}")


@mcp.tool()
def create_note(
    title: str,
    type: str,
    body: str = "",
    tags: list[str] | None = None,
    filename_prefix: str = "",
) -> dict[str, Any]:
    """
    Create a new Org-mode note in the Zettelkasten system.

    Args:
        title: Note title (required)
        type: Note type — "fleeting", "literature", or "permanent" (required)
        body: Note body content (optional; uses skeleton template if empty)
        tags: List of tag strings to attach (optional)
        filename_prefix: Prefix for literature note filenames, e.g. "Author-2024" (optional)

    Returns dict with 'id', 'file', 'title', and 'type' of the created note.
    """
    return _post("/note", {
        "title": title,
        "type": type,
        "body": body,
        "tags": tags or [],
        "filename_prefix": filename_prefix,
    })


@mcp.tool()
def update_note(node_id: str, body: str) -> dict[str, Any]:
    """
    Replace the body of an existing note, preserving its org-roam header.

    Args:
        node_id: The org-roam node ID of the note to update
        body: New body content (replaces everything after the header block)

    Returns dict with 'id', 'file', and 'updated' (bool).
    """
    return _put(f"/note/{node_id}", {"body": body})


@mcp.tool()
def list_notes() -> dict[str, Any]:
    """
    Return all indexed notes from the org-roam database.

    Returns dict with 'count' and 'nodes' list, each node having
    'id', 'title', 'file', 'level', and 'tags'.
    """
    return _get("/index")


@mcp.tool()
def list_tags() -> dict[str, Any]:
    """
    Return all tags in the knowledge base with their note counts.

    Returns dict with 'count' and 'tags' list, each tag having
    'tag' (string) and 'count' (int).
    """
    return _get("/tags")


if __name__ == "__main__":
    mcp.run(transport="stdio")
