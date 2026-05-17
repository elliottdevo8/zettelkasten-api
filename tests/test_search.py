"""
Phase 2 unit/integration tests for the /search endpoint.
Run from scripts/zettelkasten-api/:  pytest tests/
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app  # noqa: E402

from fastapi.testclient import TestClient

client = TestClient(app)


def test_search_requires_q():
    r = client.get("/search")
    assert r.status_code == 422


def test_search_returns_results():
    r = client.get("/search", params={"q": "Zettelkasten"})
    assert r.status_code == 200
    data = r.json()
    assert "query" in data
    assert "count" in data
    assert "results" in data
    assert isinstance(data["results"], list)


def test_search_type_filter_org():
    r = client.get("/search", params={"q": "the", "type": "org"})
    assert r.status_code == 200
    for item in r.json()["results"]:
        assert item["filename"].endswith(".org"), f"Got non-org file: {item['filename']}"


def test_search_type_filter_md():
    r = client.get("/search", params={"q": "the", "type": "md"})
    assert r.status_code == 200
    for item in r.json()["results"]:
        assert item["filename"].endswith(".md"), f"Got non-md file: {item['filename']}"


def test_search_type_filter_reduces_vs_unfiltered():
    r_all = client.get("/search", params={"q": "the"})
    r_org = client.get("/search", params={"q": "the", "type": "org"})
    r_md  = client.get("/search", params={"q": "the", "type": "md"})
    assert r_all.status_code == 200
    assert r_org.status_code == 200
    assert r_md.status_code == 200
    # org + md should not exceed total (some files may be filtered by glob, not double-counted)
    assert r_org.json()["count"] <= r_all.json()["count"]
    assert r_md.json()["count"]  <= r_all.json()["count"]


def test_search_tag_filter_does_not_exceed_unfiltered():
    r_all    = client.get("/search", params={"q": "the"})
    r_tagged = client.get("/search", params={"q": "the", "tag": "fleeting"})
    assert r_all.status_code == 200
    assert r_tagged.status_code in (200, 503)  # 503 if DB missing
    if r_tagged.status_code == 200:
        assert r_tagged.json()["count"] <= r_all.json()["count"]


def test_search_ripgrep_missing(monkeypatch):
    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError("rg not found")

    monkeypatch.setattr(subprocess, "run", raise_not_found)
    r = client.get("/search", params={"q": "test"})
    assert r.status_code == 503
    assert "ripgrep" in r.json()["detail"].lower()
