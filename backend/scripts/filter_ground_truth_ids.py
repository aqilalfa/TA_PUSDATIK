#!/usr/bin/env python3
"""Filter a JSONL ground-truth file by item IDs."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter JSONL ground truth by IDs")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", required=True)
    args = parser.parse_args()

    wanted = set(args.ids)
    selected = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("id") in wanted:
            selected.append(json.dumps(item, ensure_ascii=False))

    args.output.write_text("\n".join(selected) + "\n", encoding="utf-8")
    print(f"Wrote {len(selected)} item(s) to {args.output}")


if __name__ == "__main__":
    main()
