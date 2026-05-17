"""
GPT-4o Zettelkasten client — Phase 5
Demonstrates calling search_notes and create_note via OpenAI function calling.
"""

import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

ZETTELKASTEN_URL = "http://127.0.0.1:8000"
ZETTELKASTEN_KEY = os.environ["ZETTELKASTEN_API_KEY"]
HEADERS = {"X-API-Key": ZETTELKASTEN_KEY}

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

TOOLS = [
    {"type": "function", "function": {
        "name": "search_notes",
        "description": "Full-text search across all Zettelkasten notes",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Search query"},
            "tag": {"type": "string", "description": "Filter by tag (optional)"},
            "type": {"type": "string", "enum": ["org", "md"], "description": "File type filter (optional)"},
        }, "required": ["q"]},
    }},
    {"type": "function", "function": {
        "name": "create_note",
        "description": "Create a new note in the Zettelkasten",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "type": {"type": "string", "enum": ["fleeting", "literature", "permanent"]},
            "body": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        }, "required": ["title", "type"]},
    }},
]


def dispatch(name: str, args: dict[str, Any]) -> str:
    if name == "search_notes":
        r = httpx.get(f"{ZETTELKASTEN_URL}/search", params=args, headers=HEADERS, timeout=10)
    elif name == "create_note":
        r = httpx.post(f"{ZETTELKASTEN_URL}/note", json=args, headers=HEADERS, timeout=10)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return r.text


def run(user_message: str):
    messages = [{"role": "user", "content": user_message}]
    response = client.chat.completions.create(
        model="gpt-4o",
        tools=TOOLS,
        messages=messages,
    )
    msg = response.choices[0].message
    if not msg.tool_calls:
        print(msg.content)
        return

    messages.append(msg)
    for call in msg.tool_calls:
        result = dispatch(call.function.name, json.loads(call.function.arguments))
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    final = client.chat.completions.create(model="gpt-4o", messages=messages)
    print(final.choices[0].message.content)


if __name__ == "__main__":
    run("Search my notes for 'remote work' and summarize what you find.")
