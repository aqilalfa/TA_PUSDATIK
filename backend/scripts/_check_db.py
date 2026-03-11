import sqlite3, json
conn = sqlite3.connect('d:/aqil/pusdatik/backend/data/spbe_rag.db')
rows = conn.execute("""
    SELECT d.id, d.filename, d.doc_type, d.status, COUNT(c.id) chunk_count,
           COALESCE(MAX(LENGTH(c.chunk_text)),0) max_size,
           COALESCE(MIN(LENGTH(c.chunk_text)),0) min_size,
           COALESCE(AVG(LENGTH(c.chunk_text)),0) avg_size
    FROM documents d
    LEFT JOIN chunks c ON c.document_id = d.id
    GROUP BY d.id ORDER BY d.id
""").fetchall()

out = {"documents": []}
for r in rows:
    out["documents"].append({
        "id": r[0], "file": r[1], "type": r[2], "status": r[3],
        "chunks": r[4], "max": r[5], "min": r[6], "avg": round(r[7])
    })

# Oversized chunks detail
oversized = conn.execute("""
    SELECT d.filename, c.chunk_index, LENGTH(c.chunk_text), SUBSTR(c.chunk_text, 1, 100)
    FROM chunks c JOIN documents d ON c.document_id = d.id
    WHERE LENGTH(c.chunk_text) > 3000
    ORDER BY LENGTH(c.chunk_text) DESC
""").fetchall()
out["oversized"] = [{"file": r[0], "idx": r[1], "size": r[2], "preview": r[3]} for r in oversized]

with open('d:/aqil/pusdatik/backend/_stats.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
conn.close()
print("Done")
