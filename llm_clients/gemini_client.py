"""
Gemini 2.0 Flash Zettelkasten client — Phase 5
Uses google-genai SDK with function_declarations (different schema from OpenAI tools).
"""

import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

ZETTELKASTEN_URL = "http://127.0.0.1:8000"
ZETTELKASTEN_KEY = os.environ["ZETTELKASTEN_API_KEY"]
HEADERS = {"X-API-Key": ZETTELKASTEN_KEY}

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_notes",
        description="Full-text search across all Zettelkasten notes",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "q": types.Schema(type=types.Type.STRING, description="Search query"),
                "tag": types.Schema(type=types.Type.STRING, description="Filter by tag (optional)"),
                "type": types.Schema(
                    type=types.Type.STRING,
                    description="File type filter: org or md (optional)",
                    enum=["org", "md"],
                ),
            },
            required=["q"],
        ),
    ),
    types.FunctionDeclaration(
        name="create_note",
        description="Create a new note in the Zettelkasten",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "title": types.Schema(type=types.Type.STRING),
                "type": types.Schema(
                    type=types.Type.STRING,
                    enum=["fleeting", "literature", "permanent"],
                ),
                "body": types.Schema(type=types.Type.STRING),
                "tags": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
            },
            required=["title", "type"],
        ),
    ),
])


def dispatch(name: str, args: dict[str, Any]) -> str:
    if name == "search_notes":
        r = httpx.get(f"{ZETTELKASTEN_URL}/search", params=args, headers=HEADERS, timeout=10)
    elif name == "create_note":
        r = httpx.post(f"{ZETTELKASTEN_URL}/note", json=args, headers=HEADERS, timeout=10)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return r.text


def run(user_message: str):
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=user_message,
        config=types.GenerateContentConfig(tools=[TOOLS]),
    )

    part = response.candidates[0].content.parts[0]
    if not hasattr(part, "function_call"):
        print(part.text)
        return

    fc = part.function_call
    result = dispatch(fc.name, dict(fc.args))

    follow_up = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Content(role="user", parts=[types.Part(text=user_message)]),
            types.Content(role="model", parts=[types.Part(function_call=fc)]),
            types.Content(
                role="user",
                parts=[types.Part(function_response=types.FunctionResponse(
                    name=fc.name, response={"result": result}
                ))],
            ),
        ],
        config=types.GenerateContentConfig(tools=[TOOLS]),
    )
    print(follow_up.text)


if __name__ == "__main__":
    run("Search my notes for 'remote work' and summarize what you find.")
