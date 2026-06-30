"""
evaluation/runner.py

Drives all personas' scripted trajectories against the real Stride API.
Logs every request/response. On any error (non-2xx, failed check,
unresolved placeholder, etc.) logs the problem and continues — no halts,
no retries.

Usage:
    python runner.py
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
TIMEOUT = 300


def _log_error(reason: str, context: dict, log_file=None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": reason,
        "context": context,
    }
    print(f"\n[ERROR] {reason}")
    print(json.dumps(context, indent=2, default=str))
    if log_file:
        log_file.write(json.dumps(entry, default=str) + "\n")
        log_file.flush()


def _next_run_log_path(log_dir: Path) -> Path:
    existing_runs = []
    if log_dir.exists():
        for f in log_dir.iterdir():
            match = re.fullmatch(r"events_run(\d+)\.jsonl", f.name)
            if match:
                existing_runs.append(int(match.group(1)))
    next_run = max(existing_runs, default=0) + 1
    return log_dir / f"events_run{next_run}.jsonl"


def _lookup(path: str, context: dict, log_file=None):
    """
    Resolve a dot-path into context. Returns (value, ok).
    On failure, logs the error and returns (None, False) instead of halting.
    """
    parts = path.split(".")
    current = context
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                _log_error(
                    f"Placeholder {{{{{path}}}}} could not be resolved — "
                    f"key '{part}' not found in saved context.",
                    {"available_keys": list(current.keys())},
                    log_file,
                )
                return None, False
            current = current[part]
        else:
            _log_error(
                f"Placeholder {{{{{path}}}}} could not be resolved — "
                f"tried to index into a non-dict at '{part}'.",
                {"current_value": current},
                log_file,
            )
            return None, False
    return current, True


def _resolve(value, context: dict, log_file=None):
    """
    Recursively resolve {{key}} or {{key.nested.path}} placeholders.
    Returns (resolved_value, ok). If any placeholder fails, returns (None, False).
    """
    if isinstance(value, str) and "{{" in value and "}}" in value:
        # Whole-string placeholder — preserve the resolved value's real type
        if value.startswith("{{") and value.endswith("}}") and value.count("{{") == 1:
            path = value[2:-2].strip()
            return _lookup(path, context, log_file)

        # Embedded placeholder(s) inside a larger string (e.g. URL path)
        ok = True
        def _sub(match):
            nonlocal ok
            resolved, sub_ok = _lookup(match.group(1).strip(), context, log_file)
            if not sub_ok:
                ok = False
                return ""
            return str(resolved)
        result = re.sub(r"\{\{([^}]+)\}\}", _sub, value)
        return result, ok

    if isinstance(value, dict):
        resolved = {}
        for k, v in value.items():
            r, ok = _resolve(v, context, log_file)
            if not ok:
                return None, False
            resolved[k] = r
        return resolved, True

    if isinstance(value, list):
        resolved = []
        for v in value:
            r, ok = _resolve(v, context, log_file)
            if not ok:
                return None, False
            resolved.append(r)
        return resolved, True

    return value, True


def call(method: str, path: str, log_file, expect_status: int = 200, **kwargs):
    """
    Make one API call and log it. Returns (response_body, ok).
    On non-2xx or request error, logs and returns (None, False) — no halting.
    """
    url = f"{BASE_URL}{path}"
    try:
        response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        _log_error(
            f"{method} {path} raised a request exception: {exc}",
            {"url": url},
            log_file,
        )
        return None, False

    body = _safe_json(response)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "path": path,
        "request_body": kwargs.get("json"),
        "status_code": response.status_code,
        "response_body": body,
    }
    log_file.write(json.dumps(entry, default=str) + "\n")
    log_file.flush()

    if response.status_code != expect_status:
        _log_error(
            f"{method} {path} returned {response.status_code}, expected {expect_status}",
            entry,
            log_file,
        )
        return body, False

    return body, True


def _safe_json(response):
    try:
        return response.json()
    except ValueError:
        return {"raw_text": response.text}


def _contains_placeholder(payload, key: str) -> bool:
    """
    Recursively check whether {{key}} appears anywhere in a payload structure.
    More precise than dumping the whole thing to a string.
    """
    target = f"{{{{{key}}}}}"
    if isinstance(payload, str):
        return target in payload
    if isinstance(payload, dict):
        return any(_contains_placeholder(v, key) for v in payload.values())
    if isinstance(payload, list):
        return any(_contains_placeholder(v, key) for v in payload)
    return False


def run_persona(persona_module_name: str) -> bool:
    """
    Run a single persona. Returns True if all steps completed without any
    error, False if any step had a problem (but always runs to completion).
    """
    try:
        persona = importlib.import_module(f"personas.{persona_module_name}")
    except ImportError as exc:
        print(f"[SKIP] Could not import personas.{persona_module_name}: {exc}")
        return False

    log_dir = Path(f"logs/{persona.USER_ID}")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = _next_run_log_path(log_dir)

    had_errors = False

    with open(log_path, "w") as log_file:
        print(f"\n{'='*60}")
        print(f"--- Onboarding {persona.USER_ID} ---")
        print(f"--- Logging to {log_path} ---")

        _, ok = call("POST", "/onboarding/profile", log_file, json=persona.ONBOARDING_PAYLOAD)
        if not ok:
            had_errors = True

        for i, step in enumerate(persona.SCRIPT):
            print(f"[{i+1}/{len(persona.SCRIPT)}] {step['event_type']} (week {step['week']})")

            if step["event_type"] == "advance_week":
                _, ok = call("POST", "/weekly/cycle", log_file, json=step["payload"])
                if not ok:
                    had_errors = True
                continue

            method = step.get("method", "POST")

            path, ok = _resolve(step["path"], persona.CONTEXT, log_file)
            if not ok:
                had_errors = True
                continue

            expect_status = step.get("expect_status", 200)

            if _contains_placeholder(step["payload"], "ACTIVE_GOAL_SUMMARIES"):
                persona.CONTEXT["ACTIVE_GOAL_SUMMARIES"] = list(
                    persona.CONTEXT.get("_goal_summaries", {}).values()
                )

            resolved_payload, ok = _resolve(step["payload"], persona.CONTEXT, log_file)
            if not ok:
                had_errors = True
                continue

            if (
                step["event_type"] == "complete_task"
                and "completion_timestamp" not in resolved_payload
            ):
                week_date_fn = getattr(persona, "_week_date", None)
                if week_date_fn is not None:
                    sim_date = week_date_fn(step["week"])
                    # Normalise to plain date string regardless of whether
                    # _week_date() returns a date object or a string
                    if hasattr(sim_date, "isoformat"):
                        sim_date = sim_date.isoformat()[:10]
                    else:
                        sim_date = str(sim_date)[:10]
                    resolved_payload["completion_timestamp"] = f"{sim_date}T12:00:00+00:00"
                else:
                    _log_error(
                        f"complete_task step at week {step['week']} has no "
                        f"completion_timestamp and persona '{persona_module_name}' "
                        f"has no _week_date() helper — skipping step.",
                        {"step": step},
                        log_file,
                    )
                    had_errors = True
                    continue

            result, ok = call(
                method, path, log_file,
                expect_status=expect_status,
                json=resolved_payload,
            )
            if not ok:
                had_errors = True

            if "save_as" in step and result is not None:
                persona.CONTEXT[step["save_as"]] = result

            if step["event_type"] == "confirm_goal" and result and "goal_id" in result:
                smart = resolved_payload.get("smart_assessment", {})
                deadline = smart.get("extracted_deadline") or "2099-12-31"
                summary = {
                    "goal_id": result["goal_id"],
                    "name": smart.get("smart_formulation", {}).get("specific", "Unnamed Goal"),
                    "macro_impact": smart.get("impact_score", 3),
                    "terminal_deadline": deadline,
                    "status": "ACTIVE",
                }
                persona.CONTEXT.setdefault("_goal_summaries", {})[result["goal_id"]] = summary

    status = "with errors" if had_errors else "cleanly"
    print(f"Done ({status}). {len(persona.SCRIPT)} steps. Log: {log_path}")
    return not had_errors


def discover_personas() -> list[str]:
    """
    Find all persona module names by scanning the personas/ package.
    No hardcoded list — whatever files exist there get run.
    """
    import personas
    return [
        mod.name
        for mod in pkgutil.iter_modules(personas.__path__)
    ]


if __name__ == "__main__":
    persona_names = discover_personas()

    if not persona_names:
        print("No personas found in personas/. Nothing to run.")
        sys.exit(0)

    print(f"Found {len(persona_names)} persona(s): {', '.join(persona_names)}")

    results = {}
    for name in persona_names:
        results[name] = run_persona(name)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, success in results.items():
        status = "OK" if success else "ERRORS"
        print(f"  {name:<30} {status}")

    any_errors = not all(results.values())
    sys.exit(1 if any_errors else 0)