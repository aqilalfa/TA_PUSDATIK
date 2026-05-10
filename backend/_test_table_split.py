"""Quick test for table-aware splitter."""
import sys
sys.path.insert(0, ".")
from app.core.ingestion.document_manager import split_legal_document

test_text = (
    "Berikut adalah penjelasan mengenai indeks SPBE.\n\n"
    "**Tabel 4. Nilai Indeks SPBE Nasional**\n\n"
    "|          | Domain  |      | Indeks |\n"
    "|----------|---------|------|--------|\n"
    "| Nasional | Kebijakan | 2,91 | 2,79   |\n"
    "| Target   | 2,60    | 2,60 | 2,60   |\n\n"
    "Dapat dilihat pada Tabel 4, nilai indeks SPBE Nasional mencapai 2,79."
)

chunks = split_legal_document(test_text, "Test Doc", "test.pdf", max_chunk_size=200)
for c in chunks:
    ct = c.get("chunk_type", "text")
    ch = c.get("context_header", "")
    tc = str(c.get("table_context", ""))[:100]
    pp = str(c.get("parent_pasal_text", ""))[:80]
    txt = c["text"][:150]
    print(f"[{ct}] header={ch}")
    print(f"  table_context={tc}")
    print(f"  parent_text={pp}")
    print(f"  text={txt}")
    print()
