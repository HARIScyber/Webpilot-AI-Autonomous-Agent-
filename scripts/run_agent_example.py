#!/usr/bin/env python3
"""
run_agent_example.py — CLI Test Script for WebPilot AI
========================================================
Run this script to test the full pipeline without opening a browser.
It directly calls your running FastAPI backend and streams the output
to your terminal — great for debugging or running automated tasks.

Prerequisites:
  1. Backend must be running:  cd backend && uvicorn main:app --reload
  2. Your TINYFISH_API_KEY must be set in backend/.env (or the environment)
  3. Install requests:  pip install requests httpx httpx-sse

Usage:
  cd scripts
  python run_agent_example.py

  # Run a specific example:
  python run_agent_example.py --example jobs

  # Run a custom task:
  python run_agent_example.py --url https://amazon.com --goal "Find AirPods Pro price"
"""

import json
import sys
import time
import argparse
import requests

# ---- Configuration --------------------------------------------------

API_BASE = "http://localhost:8000"   # Change if your backend is on a different port

# ANSI colour codes for pretty terminal output
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
BLUE    = "\033[94m"
RESET   = "\033[0m"
BOLD    = "\033[1m"

# ---- Pre-built example tasks ----------------------------------------

EXAMPLES = {
    "price": {
        "title": "Find AirPods Pro price",
        "target_url": "https://www.amazon.com",
        "goal": "Search for 'AirPods Pro 2nd generation' and return the price, title, and rating.",
        "category": "price_check",
    },
    "jobs": {
        "title": "Software Engineer jobs",
        "target_url": "https://news.ycombinator.com/jobs",
        "goal": "Return the first 5 job postings listed on Hacker News Jobs, "
                "including the company name and job title.",
        "category": "job_search",
    },
    "availability": {
        "title": "Check MacBook Air availability",
        "target_url": "https://www.apple.com/shop/buy-mac/macbook-air",
        "goal": "Tell me which MacBook Air models are currently available to buy "
                "and their starting prices.",
        "category": "availability_check",
    },
    "news": {
        "title": "Top HN headlines",
        "target_url": "https://news.ycombinator.com",
        "goal": "Return the top 5 story titles and URLs from the Hacker News front page.",
        "category": "research",
    },
    "competitor": {
        "title": "Competitor pricing — OpenAI vs Anthropic",
        "target_url": "https://openai.com/pricing",
        "goal": "Extract the pricing table for OpenAI's API (model names and per-token prices).",
        "category": "competitor_monitoring",
    },
}

# =====================================================================
# Core functions
# =====================================================================

def create_task(title: str, target_url: str, goal: str, category: str | None = None) -> dict:
    """
    POST /api/tasks — creates a new task in the backend DB.
    Returns the task object with its id.
    """
    payload = {
        "title": title,
        "target_url": target_url,
        "goal": goal,
        "category": category,
    }
    print(f"\n{BOLD}Submitting task to WebPilot AI backend…{RESET}")
    print(f"  URL   : {CYAN}{target_url}{RESET}")
    print(f"  Goal  : {YELLOW}{goal}{RESET}\n")

    response = requests.post(f"{API_BASE}/api/tasks", json=payload)
    response.raise_for_status()
    return response.json()


def stream_task(task_id: str) -> dict | None:
    """
    GET /api/tasks/{id}/stream — opens the SSE stream and prints each event.
    Returns the final result dict when the task completes.
    """
    url = f"{API_BASE}/api/tasks/{task_id}/stream"
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}AGENT ACTIVITY STREAM{RESET}  (task_id: {task_id})")
    print(f"{BOLD}{'='*60}{RESET}\n")

    start_time = time.time()
    final_result = None

    # requests.get with stream=True lets us read the response line by line
    with requests.get(url, stream=True, timeout=300) as response:
        response.raise_for_status()

        for raw_line in response.iter_lines():
            if not raw_line:
                continue

            # SSE lines look like: b"data: {...}"
            line = raw_line.decode("utf-8")
            if not line.startswith("data:"):
                continue

            json_str = line[5:].strip()  # strip the "data: " prefix
            if not json_str:
                continue

            try:
                event = json.loads(json_str)
            except json.JSONDecodeError:
                print(f"  {RED}[parse error]{RESET} {line}")
                continue

            event_type = event.get("event", "?").upper()
            message    = event.get("message", "")
            data       = event.get("data")

            # Colour-code by event type
            if event_type == "STARTED":
                print(f"  {BLUE}▶ STARTED{RESET}  {message}")
            elif event_type == "PROGRESS":
                print(f"  {CYAN}· RUNNING{RESET}  {message}")
            elif event_type == "COMPLETE":
                elapsed = round(time.time() - start_time, 1)
                print(f"\n  {GREEN}✓ COMPLETE{RESET}  {message}  ({elapsed}s)")
                final_result = data
                break
            elif event_type == "ERROR":
                print(f"\n  {RED}✗ ERROR{RESET}  {message}")
                break
            else:
                print(f"  [{event_type}]  {message}")

    return final_result


def fetch_task_detail(task_id: str) -> dict:
    """GET /api/tasks/{id} — fetch the full task with result and logs."""
    response = requests.get(f"{API_BASE}/api/tasks/{task_id}")
    response.raise_for_status()
    return response.json()


def print_result(result: dict | None, task_detail: dict) -> None:
    """Pretty-print the final result and task stats."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}FINAL RESULT{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    if task_detail.get("status") == "failed":
        print(f"{RED}Task failed:{RESET} {task_detail.get('error_message', 'Unknown error')}")
        return

    task_result = task_detail.get("result") or {}

    raw_text = task_result.get("raw_text") or (result and str(result)) or "No result captured"
    print(f"\n{YELLOW}Summary:{RESET}\n{raw_text}")

    structured = task_result.get("data")
    if structured:
        print(f"\n{YELLOW}Structured Data:{RESET}")
        print(json.dumps(structured, indent=2))

    screenshot = task_result.get("screenshot_url")
    if screenshot:
        print(f"\n{YELLOW}Screenshot:{RESET} {screenshot}")

    duration = task_detail.get("duration_seconds")
    if duration:
        print(f"\n{GREEN}Completed in {duration}s{RESET}")


def check_backend() -> bool:
    """Ping the health endpoint to make sure the backend is running."""
    try:
        r = requests.get(f"{API_BASE}/api/health", timeout=3)
        return r.status_code == 200
    except requests.ConnectionError:
        return False


# =====================================================================
# Main entry point
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="WebPilot AI — CLI Agent Runner")
    parser.add_argument(
        "--example",
        choices=list(EXAMPLES.keys()),
        default="price",
        help="Pick a pre-built example task (default: price)",
    )
    parser.add_argument("--url",  help="Custom starting URL")
    parser.add_argument("--goal", help="Custom natural language goal")
    parser.add_argument("--title", default="CLI Task", help="Task title")
    args = parser.parse_args()

    # ---- Check the backend is up -------------------------------------
    print(f"{BOLD}WebPilot AI — CLI Test Runner{RESET}")
    print(f"Connecting to backend at {API_BASE}…")
    if not check_backend():
        print(f"\n{RED}ERROR: Cannot reach the backend at {API_BASE}{RESET}")
        print("Make sure you have run:  cd backend && uvicorn main:app --reload")
        sys.exit(1)
    print(f"{GREEN}Backend is online ✓{RESET}\n")

    # ---- Resolve task parameters -------------------------------------
    if args.url and args.goal:
        # Custom task from CLI args
        task_params = {
            "title": args.title,
            "target_url": args.url,
            "goal": args.goal,
            "category": "other",
        }
    else:
        # Use a pre-built example
        task_params = EXAMPLES[args.example]
        print(f"Running example: {BOLD}{args.example}{RESET}")

    # ---- Run the task ------------------------------------------------
    try:
        # 1. Create the task
        task = create_task(**task_params)
        task_id = task["id"]

        # 2. Stream live progress
        final_data = stream_task(task_id)

        # 3. Wait briefly for DB to be updated
        time.sleep(0.5)

        # 4. Fetch full detail and print result
        detail = fetch_task_detail(task_id)
        print_result(final_data, detail)

    except requests.HTTPError as e:
        print(f"\n{RED}HTTP Error {e.response.status_code}: {e.response.text}{RESET}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted by user.{RESET}")
        sys.exit(0)

    print(f"\n{BOLD}Done.{RESET} View all tasks at http://localhost:3000\n")


if __name__ == "__main__":
    main()
