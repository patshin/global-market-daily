#!/usr/bin/env python3
"""Read-only GMD production shadow: classify freshness and run the real Quality commands.

Never creates a publication, branch, PR or deployment. Deliberately no model/API
integration: research and authorized model credentials are separate concerns.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Shanghai")
PUBLIC = "https://patshin.github.io/global-market-daily/data/latest.json"
# Detect accidental removal of mandatory gates while allowing new Quality steps.
MUST_RUN = (
    "scripts/validate_publish_v2.py", "scripts/validate_reconstruction.py",
    "scripts/validate_live_contract.py", "scripts/validate_archive_live_contract.py",
    "scripts/validate_automation_contract.py", "scripts/validate_editorial_ui.py",
    "scripts/validate_frontend.py", "scripts/validate_market_lens.py",
    "scripts/test_publication_checkpoint.py", "scripts/test_publication_preparation.py",
    "scripts/test_candidate_browser_contract.py", "scripts/test_publication_shape.py",
    "scripts/test_market_lens_native_accumulation.py",
    "scripts/test_publication_transition.py", "scripts/test_publication_watchdog.py",
    "scripts/test_reconstruction.py", "scripts/stamp_assets.py --check",
    "node --check", "scripts/verify_candidate_browser.py",
)


@dataclass(frozen=True)
class QualityStep:
    name: str
    command: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_quality_commands(text: str) -> list[QualityStep]:
    """Extract the *actual* run commands in current quality.yml; no static gate copy.

    The current workflow uses straightforward YAML steps at six-space indent,
    with `run:` at eight-space indent. Fail closed on unsupported run syntax.
    """
    lines = text.splitlines()
    steps: list[QualityStep] = []
    name = ""
    for i, line in enumerate(lines):
        m = re.match(r"^ {6}- name:\s*(.+?)\s*$", line)
        if m:
            name = m.group(1).strip().strip("\"'")
        run = re.match(r"^ {8}run:\s*(.*?)\s*$", line)
        if not run:
            continue
        body = run.group(1)
        if body == "|":
            chunks: list[str] = []
            for next_line in lines[i + 1:]:
                if not next_line.strip():
                    chunks.append("")
                elif next_line.startswith(" " * 10):
                    chunks.append(next_line[10:])
                else:
                    break
            command = "\n".join(chunks).strip()
        elif body.startswith(("|", ">", "&", "*", "!")) or not body:
            raise ValueError(f"Unsupported Quality YAML run syntax for {name}: {body!r}")
        else:
            # Inline commands are plain unquoted scalars in the current contract.
            command = body
        if not name or not command:
            raise ValueError(f"Quality step has no name/command near line {i + 1}")
        steps.append(QualityStep(name, command))
    joined = "\n".join(s.command for s in steps)
    missing = [gate for gate in MUST_RUN if gate not in joined]
    if missing:
        raise ValueError(f"Quality workflow missing mandatory gate commands: {missing}")
    if len(steps) < 12:
        raise ValueError(f"Expected >=12 actual Quality command steps, got {len(steps)}")
    return steps


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return data


def classify_core(root: Path, expected_date: str) -> dict:
    """Do not equate a reconstructed edition with a current native publication."""
    try:
        latest = load_json(root / "docs/data/latest.json")
        day = str(latest.get("date", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("latest.date is not YYYY-MM-DD")
        archive = load_json(root / "docs/data/archive.json")
        entries = archive.get("entries")
        if not isinstance(entries, list):
            raise ValueError("archive.entries must be an array")
        date_matches = [x for x in entries if isinstance(x, dict) and x.get("date") == day]
        if len(date_matches) != 1:
            raise ValueError(f"latest date has {len(date_matches)} formal archive entries; expected exactly 1")
        daily_path = latest.get("daily_json_path")
        if not isinstance(daily_path, str) or not daily_path.startswith("data/daily/"):
            raise ValueError("latest.daily_json_path is invalid")
        report = load_json(root / "docs" / daily_path)
        cycle = report.get("publication_cycle")
        if not isinstance(cycle, dict):
            raise ValueError("report.publication_cycle must be an object")
        if report.get("date") != day or latest.get("thesis") != report.get("thesis"):
            raise ValueError("latest/report date or thesis mismatch")
        if report.get("edition_status") != "official" or cycle.get("cycle") != "morning" or cycle.get("is_final") is not True:
            raise ValueError("latest report must be official final morning")
        reconstructed = (report.get("reconstruction") or {}).get("is_reconstructed") is True
        native = report.get("source_mode") == "native_daily" and cycle.get("market_lens_native_eligible") is True
        if reconstructed and native:
            raise ValueError("Reconstructed report cannot be native")
        if day > expected_date:
            status = "FUTURE_LATEST_CHECK_CLOCK"
        elif day < expected_date:
            status = "STALE_MAIN"
        elif reconstructed:
            status = "CURRENT_HISTORICAL_BACKFILL_NOT_NATIVE"
        elif native:
            status = "CURRENT_NATIVE_OFFICIAL"
        else:
            status = "CURRENT_NON_NATIVE_UNVERIFIED"
        lens_status = "UNKNOWN"
        try:
            lens = load_json(root / "docs/data/trends/rolling-30d.json")
            if any(isinstance(x, dict) and x.get("date") == day and
                   x.get("source_mode") == ("reconstructed_daily" if reconstructed else "native_daily")
                   for x in lens.get("days", [])):
                lens_status = "CURRENT_SOURCE_REPRESENTED"
            else:
                lens_status = "LENS_LAG_OR_WINDOW_EXCLUSION"
        except (OSError, ValueError, json.JSONDecodeError):
            lens_status = "LENS_UNREADABLE"
        return {"status": status, "latest_date": day, "expected_date": expected_date,
                "edition": report.get("edition"), "source_mode": report.get("source_mode"),
                "reconstructed": reconstructed, "lens_status": lens_status}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
        return {"status": "MAIN_INVALID", "expected_date": expected_date,
                "error": f"{type(exc).__name__}: {exc}"}


def classify_public(local_latest: dict, public_latest: dict, expected_date: str) -> dict:
    if not isinstance(public_latest, dict) or not isinstance(local_latest, dict):
        return {"status": "PUBLIC_INVALID", "error": "Expected JSON objects"}
    pubdate = public_latest.get("date")
    maindate = local_latest.get("date")
    if not isinstance(pubdate, str) or not isinstance(maindate, str):
        return {"status": "PUBLIC_INVALID", "error": "Missing date"}
    if pubdate != maindate:
        return {"status": "PUBLIC_LAGS_MAIN" if pubdate < maindate else "PUBLIC_AHEAD_OF_MAIN",
                "public_date": pubdate, "main_date": maindate}
    for k in ("thesis", "dominant_narrative", "daily_json_path", "report_path", "sources_path", "edition_status", "source_mode"):
        if public_latest.get(k) != local_latest.get(k):
            return {"status": "PUBLIC_DRIFT", "field": k, "public_date": pubdate, "main_date": maindate}
    return {"status": "CURRENT_PUBLIC_NATIVE" if pubdate == expected_date and
            local_latest.get("source_mode") == "native_daily" else
            "PUBLIC_CONSISTENT_BUT_NOT_NATIVE_CURRENT",
            "public_date": pubdate, "main_date": maindate}


def fetch_public_latest() -> dict:
    request = Request(PUBLIC + "?" + urlencode({"shadow": utc_now()}),
                      headers={"Accept": "application/json", "Cache-Control": "no-cache",
                               "User-Agent": "GMD-Shadow-ReadOnly/1.0"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        body = response.read(512 * 1024 + 1)
        if len(body) > 512 * 1024:
            raise ValueError("Public latest exceeds size limit")
    doc = json.loads(body.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("Public latest is not JSON object")
    return doc


def classify_pr_status(pulls: list[dict], runs: list[dict], expected_date: str) -> dict:
    """Differentiate missing input, failed Quality and a green PR still awaiting promotion."""
    title = f"GMD Publish {expected_date} Morning"
    matching = [p for p in pulls if isinstance(p, dict) and p.get("title") == title]
    if not matching:
        return {"status": "NO_SAME_DATE_PUBLISH_PR", "title": title}
    # Each date must have one PR; even closed duplicates are a production incident.
    if len(matching) != 1:
        return {"status": "DUPLICATE_SAME_DATE_PRS", "count": len(matching), "title": title}
    pr = matching[0]
    sha = (pr.get("head") or {}).get("sha")
    head = (pr.get("head") or {}).get("ref")
    base = (pr.get("base") or {}).get("ref")
    if base != "main" or head != f"publish/gmd-{expected_date}-morning":
        return {"status": "PR_WRONG_REFS", "number": pr.get("number"), "head": head, "base": base}
    if pr.get("merged_at"):
        return {"status": "PR_MERGED", "number": pr.get("number"), "head_sha": sha}
    if pr.get("state") != "open":
        return {"status": "PR_CLOSED_UNMERGED", "number": pr.get("number"), "head_sha": sha}
    relevant = [r for r in runs if r.get("name") == "Publication Quality Gate" and
                r.get("event") == "pull_request" and r.get("head_sha") == sha]
    relevant.sort(key=lambda r: (r.get("created_at") or "", r.get("run_attempt") or 0), reverse=True)
    if not relevant:
        status = "PR_NO_QUALITY_RUN"
    elif relevant[0].get("status") != "completed":
        status = "PR_QUALITY_IN_PROGRESS"
    elif relevant[0].get("conclusion") == "success":
        status = "PR_GREEN_AWAITING_PROMOTION"
    else:
        status = "PR_QUALITY_FAILED"
    return {"status": status, "number": pr.get("number"), "head_sha": sha,
            "quality_url": relevant[0].get("html_url") if relevant else None,
            "quality_conclusion": relevant[0].get("conclusion") if relevant else None}


def inspect_github_pr(expected_date: str) -> dict:
    """Only GET calls. The optional Actions token is read-only and never logged."""
    repo = os.environ.get("GITHUB_REPOSITORY", "patshin/global-market-daily")
    if repo != "patshin/global-market-daily":
        return {"status": "PR_INSPECTION_DISABLED_WRONG_REPOSITORY"}
    token = os.environ.get("GH_TOKEN")
    if not token:
        return {"status": "PR_INSPECTION_UNAVAILABLE_NO_TOKEN"}
    def gh_get(path: str) -> dict | list:
        url = (f"https://api.github.com/{path}" if path.startswith("search/")
               else f"https://api.github.com/repos/{repo}/{path}")
        request = Request(url,
                          headers={"Accept": "application/vnd.github+json",
                                   "Authorization": "Bearer " + token,
                                   "X-GitHub-Api-Version": "2022-11-28",
                                   "User-Agent": "GMD-Shadow-ReadOnly/1.0"})
        with urlopen(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("GitHub response exceeds size limit")
            return json.loads(raw.decode("utf-8"))
    try:
        title = f"GMD Publish {expected_date} Morning"
        # The complete pull-list payload exceeded the prior 1 MiB response cap.
        # Search title first (all PR states), then fetch only matching PR objects.
        query = urlencode({"q": f'repo:{repo} is:pr in:title "{title}"', "per_page": 50})
        results = gh_get("search/issues?" + query)
        if not isinstance(results, dict) or not isinstance(results.get("items"), list):
            raise ValueError("GitHub PR search returned malformed data")
        if results.get("total_count", 0) > 50:
            return {"status": "PR_SEARCH_INCOMPLETE_TOO_MANY_MATCHES"}
        numbers = [p.get("number") for p in results["items"] if p.get("title") == title]
        pulls = [gh_get(f"pulls/{number}") for number in numbers if isinstance(number, int)]
        if not pulls or len(pulls) != 1 or pulls[0].get("state") != "open":
            return classify_pr_status(pulls, [], expected_date)
        sha = (pulls[0].get("head") or {}).get("sha")
        actions = gh_get(f"actions/runs?head_sha={sha}&event=pull_request&per_page=30")
        if not isinstance(actions, dict) or not isinstance(actions.get("workflow_runs"), list):
            raise ValueError("GitHub Actions runs endpoint returned malformed data")
        return classify_pr_status(pulls, actions["workflow_runs"], expected_date)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "PR_INSPECTION_ERROR", "error": f"{type(exc).__name__}: {exc}"}


def run_real_quality(root: Path, steps: list[QualityStep], out: Path, timeout: int) -> dict:
    """Use the current repository's exact run commands and real Chromium; fail closed."""
    quality_dir = out / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index, step in enumerate(steps, 1):
        label = f"{index:02d}"
        started = utc_now()
        try:
            p = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step.command],
                               cwd=str(root), text=True, capture_output=True,
                               timeout=timeout, check=False)
            stdout, stderr = p.stdout, p.stderr
            code = p.returncode
            status = "PASS" if code == 0 else "FAIL"
        except subprocess.TimeoutExpired as exc:
            def decoded(v):
                return v.decode("utf-8", errors="replace") if isinstance(v, bytes) else (v or "")
            stdout, stderr = decoded(exc.stdout), decoded(exc.stderr)
            code, status = None, "TIMEOUT"
        # Never output a candidate's raw contents, credentials, environment or source bytes.
        (quality_dir / f"{label}.stdout.log").write_text(stdout, encoding="utf-8")
        (quality_dir / f"{label}.stderr.log").write_text(stderr, encoding="utf-8")
        records.append({"step": step.name, "command": step.command, "started_utc": started,
                        "completed_utc": utc_now(), "exit_code": code, "status": status,
                        "stdout_log": f"quality/{label}.stdout.log", "stderr_log": f"quality/{label}.stderr.log"})
        print(f"{status}: {step.name}", flush=True)
        if status != "PASS":
            break
    return {"status": "PASS" if len(records) == len(steps) and all(x["status"] == "PASS" for x in records) else "FAIL",
            "executed": len(records), "expected": len(steps), "steps": records}


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only production shadow and full Quality parity check")
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-date", default=None, help="SGT YYYY-MM-DD; defaults to real date")
    p.add_argument("--run-quality", action="store_true", help="Execute every actual Quality run: step, including Chromium")
    p.add_argument("--check-public", action="store_true", help="Read Pages latest via network")
    p.add_argument("--inspect-pr", action="store_true", help="Read-only GitHub candidate PR and CI state")
    p.add_argument("--fail-on-non-native", action="store_true", help="Use for monitoring, not historical backfill tests")
    p.add_argument("--timeout-seconds", type=int, default=180)
    args = p.parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    expected = args.expected_date or datetime.now(SGT).strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expected):
        p.error("--expected-date must be YYYY-MM-DD")
    run = {"started_utc": utc_now(), "sgt_date": expected,
           "mode": "READ_ONLY_SHADOW", "github_sha": os.environ.get("GITHUB_SHA", "not shown"),
           "publication_writes": 0, "model_api_calls": 0,
           "core": classify_core(root, expected), "quality": {"status": "NOT_RUN"},
           "public": {"status": "NOT_CHECKED"}, "pr": {"status": "NOT_CHECKED"}}
    final_code = 0
    try:
        workflow = root / ".github/workflows/quality.yml"
        content = workflow.read_text(encoding="utf-8")
        steps = parse_quality_commands(content)
        run["quality_workflow_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        run["quality_command_count"] = len(steps)
        if args.check_public:
            try:
                main_latest = load_json(root / "docs/data/latest.json")
                run["public"] = classify_public(main_latest, fetch_public_latest(), expected)
            except (OSError, ValueError, TimeoutError, json.JSONDecodeError) as exc:
                run["public"] = {"status": "PUBLIC_FETCH_ERROR", "error": f"{type(exc).__name__}: {exc}"}
        if args.inspect_pr:
            run["pr"] = inspect_github_pr(expected)
        if args.run_quality:
            run["quality"] = run_real_quality(root, steps, out, max(10, args.timeout_seconds))
            if run["quality"]["status"] != "PASS":
                final_code = 1
        if args.fail_on_non_native and (run["core"]["status"] != "CURRENT_NATIVE_OFFICIAL" or
                                       args.check_public and run["public"]["status"] != "CURRENT_PUBLIC_NATIVE"):
            final_code = 1
    except Exception as exc:
        final_code = 1
        run["setup_error"] = f"{type(exc).__name__}: {exc}"
    run["completed_utc"] = utc_now()
    run["result"] = ("QUALITY_FAIL_OR_INVALID" if final_code else
                     "SHADOW_COMPLETE_WITH_FRESHNESS_WARNING" if run["core"]["status"] != "CURRENT_NATIVE_OFFICIAL" or
                     args.check_public and run["public"]["status"] != "CURRENT_PUBLIC_NATIVE" else "SHADOW_PASS")
    receipt = out / "receipt.json"
    receipt.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SHADOW RECEIPT: {receipt}")
    print(f"CORE={run['core']['status']} PUBLIC={run['public']['status']} PR={run['pr']['status']} QUALITY={run['quality']['status']} RESULT={run['result']}")
    return final_code


if __name__ == "__main__":
    sys.exit(main())
