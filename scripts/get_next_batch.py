# AI-Assisted Development Notice
# This file was developed with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: making code cleaner and well-structured, implementing complex code logic
# Student contribution: high-level pseudocode, coding, requirements definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

#!/usr/bin/env python3
"""
get_next_batch.py — Returns the next N unprocessed qualifying records across all source files.
Maintains state in data/import_state.json. State advances only after records are printed.

Usage:
  python3 scripts/get_next_batch.py            # next 5 records
  python3 scripts/get_next_batch.py --size 10  # next 10 records
  python3 scripts/get_next_batch.py --status   # show progress only, no advance

Output (stdout): JSON object
  {
    "records": [ ...raw JSONL records... ],
    "progress": { ...per-file and total counts... },
    "done": true/false
  }
"""

import sys
import json
import os
import argparse
from datetime import datetime

BASE_RAW = "/Users/yajwin/Desktop/CS6747/SecurePay/data/raw"
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE_FILE = os.path.join(REPO_ROOT, "data", "import_state.json")

# Per-file config: path + filter function
SOURCE_FILES = [
    {
        "label": "reddit_upi_fraud",
        "path": os.path.join(BASE_RAW, "reddit_upi_fraud.jsonl"),
        # All 81 records are high quality — no filter needed
        "filter": lambda r: True,
        "notes": "23 fields, fraud_confidence present",
    },
    {
        "label": "nilansh_reddit_verified",
        "path": os.path.join(BASE_RAW, "nilansh_reddit_verified.jsonl"),
        # All verified; has pre-extracted extracted_upi_id and extracted_amount as hints
        "filter": lambda r: True,
        "notes": "24 fields, has extracted_upi_id + extracted_amount hints",
    },
    {
        "label": "v2_reddit_500_verified",
        "path": os.path.join(BASE_RAW, "v2", "v2_reddit_500_verified.jsonl"),
        "filter": lambda r: r.get("fraud_confidence") == "high",
        "notes": "23 fields, filter: fraud_confidence==high",
    },
    {
        "label": "v2_upi_fraud_verified",
        "path": os.path.join(BASE_RAW, "v2", "v2_upi_fraud_verified.jsonl"),
        # No fraud_confidence field — rely on is_fraud_verified
        "filter": lambda r: r.get("is_fraud_verified") is True,
        "notes": "12 fields, no fraud_confidence, filter: is_fraud_verified==true",
    },
    {
        "label": "upi_fraud_complaints_cleaned",
        "path": os.path.join(BASE_RAW, "upi_fraud_complaints_cleaned.jsonl"),
        # Complaint portal records — either high confidence or verified
        "filter": lambda r: (
            r.get("fraud_confidence") == "high"
            or r.get("is_fraud_verified") is True
        ),
        "notes": "19 fields, complaint portal (no subreddit), filter: confidence==high OR verified",
    },
    {
        "label": "v2_upi_fraud_2000",
        "path": os.path.join(BASE_RAW, "v2", "v2_upi_fraud_2000.jsonl"),
        # Large file — filter strictly: verified + meaningful text
        "filter": lambda r: (
            r.get("is_fraud_verified") is True
            and len(r.get("raw_text") or "") > 200
        ),
        "notes": "12 fields, no fraud_confidence, filter: is_fraud_verified==true + text>200",
    },
]


def count_lines(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def init_state():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    files = []
    for sf in SOURCE_FILES:
        files.append({
            "label": sf["label"],
            "path": sf["path"],
            "notes": sf["notes"],
            "total_lines": count_lines(sf["path"]),
            "line_pos": 0,
            "qualifying_given": 0,
            "status": "pending",
        })
    state = {
        "version": 1,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "current_file_idx": 0,
        "files": files,
        "total_qualifying_given": 0,
    }
    save_state(state)
    return state


def load_state():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return init_state()


def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_filter(label):
    for sf in SOURCE_FILES:
        if sf["label"] == label:
            return sf["filter"]
    return lambda r: True


def get_next_batch(state, batch_size):
    records = []
    files = state["files"]
    file_idx = state["current_file_idx"]

    while len(records) < batch_size and file_idx < len(files):
        fi = files[file_idx]
        filter_fn = get_filter(fi["label"])

        if fi["status"] == "complete":
            file_idx += 1
            continue

        fi["status"] = "in_progress"
        path = fi["path"]

        if not os.path.exists(path):
            print(f"WARNING: not found: {path}", file=sys.stderr)
            fi["status"] = "complete"
            file_idx += 1
            continue

        with open(path, "r", encoding="utf-8") as f:
            all_lines = [ln.strip() for ln in f if ln.strip()]

        pos = fi["line_pos"]

        while len(records) < batch_size and pos < len(all_lines):
            try:
                record = json.loads(all_lines[pos])
            except json.JSONDecodeError:
                pos += 1
                continue

            pos += 1

            if not filter_fn(record):
                continue

            record["_source_label"] = fi["label"]
            records.append(record)

        fi["line_pos"] = pos

        if pos >= len(all_lines):
            fi["status"] = "complete"
            file_idx += 1

    # Commit advances to state
    state["current_file_idx"] = file_idx
    for rec in records:
        label = rec["_source_label"]
        for fi in files:
            if fi["label"] == label:
                fi["qualifying_given"] = fi.get("qualifying_given", 0) + 1
    state["total_qualifying_given"] = state.get("total_qualifying_given", 0) + len(records)

    return records, state


def build_progress(state):
    files = state["files"]
    complete = sum(1 for f in files if f["status"] == "complete")
    idx = state["current_file_idx"]
    current = files[idx]["label"] if idx < len(files) else "ALL DONE"

    return {
        "current_file": current,
        "files_complete": f"{complete}/{len(files)}",
        "total_qualifying_given": state.get("total_qualifying_given", 0),
        "per_file": [
            {
                "label": f["label"],
                "status": f["status"],
                "lines_seen": f["line_pos"],
                "total_lines": f["total_lines"],
                "qualifying_given": f.get("qualifying_given", 0),
            }
            for f in files
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=5)
    parser.add_argument("--status", action="store_true", help="Show progress only")
    args = parser.parse_args()

    state = load_state()

    if args.status:
        progress = build_progress(state)
        print(json.dumps({"records": [], "progress": progress, "done": False}, indent=2))
        return

    all_done = state["current_file_idx"] >= len(SOURCE_FILES)
    if all_done:
        progress = build_progress(state)
        print(json.dumps({"records": [], "progress": progress, "done": True}, indent=2))
        return

    records, state = get_next_batch(state, args.size)
    save_state(state)

    done = state["current_file_idx"] >= len(SOURCE_FILES)

    # Strip internal field before output
    output_records = [
        {k: v for k, v in r.items() if k != "_source_label"}
        for r in records
    ]

    print(json.dumps({
        "records": output_records,
        "progress": build_progress(state),
        "done": done,
    }, indent=2))


if __name__ == "__main__":
    main()
