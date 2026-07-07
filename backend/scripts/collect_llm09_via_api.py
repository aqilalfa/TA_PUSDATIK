"""Collect live OWASP LLM09 responses from the running chat API.

This is an optional QA runner, not a unit test dependency. It sends the
LLM09 misinformation fixture to /api/chat/stream, captures the final SSE
`complete` event, and writes response records that can be scored by
llm09_misinformation_eval.py.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "llm09_misinformation_prompts.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "reports" / "llm09" / "llm09_live_responses.json"
DEFAULT_API_URL = "http://localhost:8000/api/chat/stream"


def load_fixture(path: Path = DEFAULT_FIXTURE) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_chat_payload(item: dict[str, Any], *, model_name: str | None, session_id: str | None, top_k: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": session_id,
        "message": str(item["prompt"]),
        "top_k": top_k,
        "use_structured_fact": False,
    }
    if model_name:
        payload["model"] = model_name
    return payload


def parse_sse_events(body: str) -> list[dict[str, Any]]:
    """Parse simple SSE blocks into event dictionaries."""
    events: list[dict[str, Any]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if not data_lines:
            continue
        raw_data = "\n".join(data_lines)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            data = {"raw": raw_data}
        events.append({"event": event_name, "data": data})
    return events


def extract_complete_response(body: str) -> dict[str, Any]:
    """Extract the final chat response from an SSE response body."""
    events = parse_sse_events(body)
    complete_events = [event for event in events if event["event"] == "complete"]
    if complete_events:
        data = complete_events[-1]["data"]
        return data if isinstance(data, dict) else {"answer": str(data)}

    token_text = "".join(
        str(event["data"].get("t", ""))
        for event in events
        if event["event"] == "token" and isinstance(event.get("data"), dict)
    )
    if token_text:
        return {"answer": token_text, "sources": [], "validation": None}

    error_events = [event for event in events if event["event"] == "error"]
    if error_events:
        return {"answer": "", "error": error_events[-1]["data"]}

    return {"answer": "", "error": "No complete/token/error SSE event found"}


def post_chat_stream(api_url: str, payload: dict[str, Any], *, bearer_token: str | None, timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - user-provided local/internal API URL
        body = response.read().decode("utf-8", errors="replace")
    return extract_complete_response(body)


def get_bearer_token(api_url: str, username: str | None, password: str | None, max_retries: int = 3) -> str | None:
    if not username or not password:
        return None
    
    login_url = api_url.replace("/chat/stream", "/auth/login")
    data = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
    
    for attempt in range(max_retries):
        request = urllib.request.Request(login_url, data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body).get("access_token")
        except Exception as e:
            print(f"Failed to authenticate (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None


def collect_responses(
    items: list[dict[str, Any]],
    *,
    api_url: str,
    bearer_token: str | None = None,
    model_name: str | None = None,
    session_id: str | None = None,
    top_k: int = 5,
    timeout: float = 120.0,
    inter_prompt_delay: float = 0.0,
    max_prompts: int | None = None,
    output_path: Path | None = None,
    skip_existing: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    existing_ids: set[str] = set()
    if skip_existing and output_path and output_path.exists():
        try:
            existing_rows = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(existing_rows, list):
                rows = [row for row in existing_rows if isinstance(row, dict)]
                existing_ids = {str(row.get("id")) for row in rows}
        except json.JSONDecodeError:
            rows = []
            existing_ids = set()

    selected = items[:max_prompts] if max_prompts else items
    for item in selected:
        if str(item.get("id")) in existing_ids:
            continue
        payload = build_chat_payload(item, model_name=model_name, session_id=session_id, top_k=top_k)
        started = time.perf_counter()
        error = None
        response_data: dict[str, Any]
        try:
            response_data = post_chat_stream(api_url, payload, bearer_token=bearer_token, timeout=timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            response_data = {"answer": "", "sources": [], "validation": None}
            error = f"{type(exc).__name__}: {exc}"

        row = {
            "id": item.get("id"),
            "category": item.get("category"),
            "expected_behavior": item.get("expected_behavior"),
            "prompt": item.get("prompt"),
            "response": response_data,
            "error": error,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
        rows.append(row)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        
        if inter_prompt_delay > 0:
            time.sleep(inter_prompt_delay)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect live LLM09 responses from /api/chat/stream.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bearer-token", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--max-prompts", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true", help="Resume by keeping existing output rows and skipping their IDs")
    args = parser.parse_args()

    items = load_fixture(args.fixture)
    bearer_token = args.bearer_token or get_bearer_token(args.api_url, args.username, args.password)
    
    rows = collect_responses(
        items,
        api_url=args.api_url,
        bearer_token=bearer_token,
        model_name=args.model,
        session_id=args.session_id,
        top_k=args.top_k,
        timeout=args.timeout,
        inter_prompt_delay=args.delay,
        max_prompts=args.max_prompts,
        output_path=args.output,
        skip_existing=args.skip_existing,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    failures = sum(1 for row in rows if row.get("error"))
    print(f"Wrote {len(rows)} LLM09 live response record(s) to {args.output}")
    if failures:
        print(f"Warning: {failures} request(s) failed. Inspect the error fields in the output file.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
