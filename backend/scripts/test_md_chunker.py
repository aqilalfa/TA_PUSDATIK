"""Quick validation for markdown fallback chunker on problematic documents."""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.ingestion.structured_chunker import chunk_from_markdown

MARKER_OUTPUT_DIR = BACKEND_DIR / "data" / "marker_output"

TARGETS = [
    {
        "label": "SE 18/2022",
        "filename": "SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf",
        "title": "SE 18 Tahun 2022",
        "keywords": ["SE Menteri PAN-RB Nomor 18 Tahun 2022"],
    },
    {
        "label": "Permenpan 5/2020",
        "filename": "Permenpan RB Nomor 5 Tahun 2020.pdf",
        "title": "Permenpan 5 Tahun 2020",
        "keywords": [
            "Permenpan_RB_Nomor_5_Tahun_2020",
            "Permenpan RB Nomor 5 Tahun 2020",
        ],
    },
]


def find_markdown_file(keywords):
    if not MARKER_OUTPUT_DIR.exists():
        return None

    for folder in MARKER_OUTPUT_DIR.iterdir():
        if not folder.is_dir():
            continue

        folder_name = folder.name.lower()
        if not any(keyword.lower() in folder_name for keyword in keywords):
            continue

        candidate = folder / f"{folder.name}.md"
        if candidate.exists():
            return candidate

    return None


def run_target(target):
    label = target["label"]
    md_path = find_markdown_file(target["keywords"])

    print("=" * 100)
    print(f"Target: {label}")

    if not md_path:
        print("Markdown file not found in marker_output. Skipped.")
        return

    print(f"Markdown path: {md_path}")

    md_text = md_path.read_text(encoding="utf-8")
    chunks = chunk_from_markdown(md_text, target["filename"], target["title"])

    print(f"Chunk count: {len(chunks)}")
    for idx, chunk in enumerate(chunks[:5], 1):
        hierarchy = (chunk.get("metadata") or {}).get("hierarchy", "")
        preview = (chunk.get("text") or "").replace("\n", " ")[:100]
        print(f"  [{idx}] hierarchy={hierarchy[:90]}")
        print(f"       text={preview}")


if __name__ == "__main__":
    for target in TARGETS:
        run_target(target)
