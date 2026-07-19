# LLM08 Endpoint Evidence Report

**Project**: SPBE RAG Backend  
**Area**: OWASP LLM08 - Vector and Embedding Weaknesses  
**Evidence Type**: FastAPI endpoint evidence using `TestClient` with dependency overrides  
**Result File**: `backend/reports/llm08/llm08_endpoint_evidence_results.json`  
**Overall Status**: **PASS**

---

## 1. Ringkasan

Pengujian ini dijalankan untuk memverifikasi bahwa endpoint dokumen dan citation preview menolak akses role `staff` terhadap dokumen dengan metadata restricted:

```json
{
  "allowed_roles": ["admin_pusdatik"],
  "classification": "restricted_audit"
}
```

Pengujian juga menyertakan positive control sebagai `admin_pusdatik` untuk membuktikan bahwa dokumen fixture memang dapat diakses oleh role yang berwenang.

> Catatan penting: pengujian ini **bukan live deployment test terhadap server Uvicorn dan data produksi**. Pengujian menggunakan `FastAPI TestClient` dengan dependency override untuk user, database, dan document manager. Artinya, hasil ini sah sebagai **endpoint-level authorization evidence** untuk logic FastAPI, tetapi belum membuktikan kondisi live Qdrant/BM25/chat stream pada data aktual.

---

## 2. Batasan Evidence

Hasil ini membuktikan:

- Endpoint Document API mengembalikan `403` untuk staff pada dokumen admin-only.
- Endpoint Citation API/chunk preview mengembalikan `403` untuk staff pada dokumen admin-only.
- Endpoint yang sama mengembalikan `200` untuk admin sebagai positive control.
- Access control berbasis `user_can_access_metadata(...)` aktif pada jalur endpoint.

Hasil ini tidak membuktikan secara penuh:

- Live retrieval Qdrant terhadap koleksi aktual.
- Live BM25 terhadap index aktual.
- Literal search terhadap nomor pasal/tabel aktual.
- Context stitching aktual dari Qdrant neighbor chunks.
- Chat stream `/api/chat/stream` dengan model dan data real.

Pemeriksaan SQLite lokal menemukan `0` kandidat dokumen aktual dengan `classification = restricted_audit` atau `allowed_roles = ["admin_pusdatik"]`, sehingga pengujian live terhadap data DB aktual belum dapat dilakukan tanpa menambahkan/mengindeks dokumen restricted terlebih dahulu.

---

## 3. Script Pengujian yang Dijalankan

Script berikut dijalankan dari direktori:

```text
D:\aqil\pusdatik\backend
```

Command eksekusi:

```powershell
.\venv\Scripts\python.exe -c "<script di bawah>"
```

Isi script:

```python
import json
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies.auth_dependencies import get_current_user
from app.api.documents import get_manager
from app.database import get_db
from app.models.db_models import Document, Chunk

REPORT_DIR = Path('reports/llm08')
REPORT_DIR.mkdir(parents=True, exist_ok=True)

class User(SimpleNamespace):
    pass

staff = User(id=3, email='evaluator@bssn.go.id', roles=json.dumps(['staff']), department='DEPUTI_EVALUASI')
admin = User(id=2, email='admin@bssn.go.id', roles=json.dumps(['admin_pusdatik']), department='PUSDATIK')
current_user = {'value': staff}

def override_user():
    return current_user['value']

class FakeManager:
    restricted = {
        'doc_id': 'restricted-audit-live-test',
        'filename': 'restricted_audit.pdf',
        'document_title': 'Restricted Audit Evidence Fixture',
        'doc_type': 'audit',
        'file_size': 128,
        'chunk_count': 1,
        'status': 'indexed',
        'access_metadata': {
            'allowed_roles': ['admin_pusdatik'],
            'classification': 'restricted_audit',
            'source_hash': 'sha256:' + 'a' * 64,
        },
    }
    public = {
        'doc_id': 'staff-doc-live-test',
        'filename': 'staff_doc.pdf',
        'document_title': 'Staff Visible Fixture',
        'doc_type': 'policy',
        'file_size': 128,
        'chunk_count': 1,
        'status': 'indexed',
        'access_metadata': {
            'allowed_roles': ['staff'],
            'classification': 'internal',
            'source_hash': 'sha256:' + 'b' * 64,
        },
    }

    def list_documents(self):
        return [self.restricted, self.public]

    def get_document(self, doc_id):
        if doc_id == self.restricted['doc_id']:
            return self.restricted
        if doc_id == self.public['doc_id']:
            return self.public
        return None

    def get_document_detail(self, doc_id):
        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError('not found')
        return {**doc, 'detail': True}

    def get_chunks(self, doc_id, limit=50, offset=0):
        if doc_id == self.restricted['doc_id']:
            return [{
                'id': 1,
                'chunk_id': 1,
                'doc_id': doc_id,
                'chunk_index': 0,
                'text': 'RESTRICTED_AUDIT_SECRET_CONTEXT',
                'is_parent': False,
                'is_indexed': True,
            }]
        return []

    def preview_chunks(self, doc_id):
        if doc_id != self.restricted['doc_id']:
            raise ValueError('not found')
        return {
            'doc_id': doc_id,
            'document_title': self.restricted['document_title'],
            'doc_type': 'audit',
            'total_chunks': 1,
            'chunks': [{'text': 'RESTRICTED_AUDIT_SECRET_CONTEXT'}],
            'has_more': False,
        }

fake_manager = FakeManager()

def override_manager():
    return fake_manager

class FakeQuery:
    def __init__(self, model):
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if self.model is Document:
            return SimpleNamespace(
                id=77,
                doc_id='restricted-audit-live-test',
                filename='restricted_audit.pdf',
                original_filename='restricted_audit.pdf',
                document_title='Restricted Audit Evidence Fixture',
                doc_type='audit',
                file_path=None,
                original_path=None,
                doc_metadata=json.dumps({
                    'security': {
                        'allowed_roles': ['admin_pusdatik'],
                        'classification': 'restricted_audit',
                        'source_hash': 'sha256:' + 'a' * 64,
                    }
                }),
            )
        if self.model is Chunk:
            return SimpleNamespace(
                chunk_index=0,
                chunk_text='RESTRICTED_AUDIT_SECRET_CONTEXT',
                chunk_metadata=json.dumps({
                    'pasal': 'Pasal Rahasia',
                    'context_header': 'Restricted Audit',
                }),
            )
        return None

class FakeDB:
    def query(self, model):
        return FakeQuery(model)

def override_db():
    yield FakeDB()

app.dependency_overrides[get_current_user] = override_user
app.dependency_overrides[get_manager] = override_manager
app.dependency_overrides[get_db] = override_db

client = TestClient(app, raise_server_exceptions=False)

def request_as(user, method, path):
    current_user['value'] = user
    response = client.request(method, path)
    return {
        'method': method,
        'path': path,
        'role': json.loads(user.roles)[0],
        'status_code': response.status_code,
        'body_preview': response.text[:500],
    }

checks = []
restricted = 'restricted-audit-live-test'
checks.append({**request_as(staff, 'GET', f'/api/documents/{restricted}'), 'id': 'DOC-DETAIL-STAFF', 'expected': 403})
checks.append({**request_as(staff, 'GET', f'/api/documents/{restricted}/chunks'), 'id': 'DOC-CHUNKS-STAFF', 'expected': 403})
checks.append({**request_as(staff, 'POST', f'/api/documents/{restricted}/preview'), 'id': 'DOC-PREVIEW-STAFF', 'expected': 403})
checks.append({**request_as(staff, 'GET', f'/api/rag/documents/by-doc-id/{restricted}/chunks/0'), 'id': 'CITATION-CHUNK-STAFF', 'expected': 403})
checks.append({**request_as(staff, 'GET', f'/api/rag/documents/by-doc-id/{restricted}/file'), 'id': 'CITATION-FILE-STAFF', 'expected': 403})
checks.append({**request_as(admin, 'GET', f'/api/documents/{restricted}'), 'id': 'DOC-DETAIL-ADMIN-POSITIVE-CONTROL', 'expected': 200})
checks.append({**request_as(admin, 'GET', f'/api/rag/documents/by-doc-id/{restricted}/chunks/0'), 'id': 'CITATION-CHUNK-ADMIN-POSITIVE-CONTROL', 'expected': 200})

for check in checks:
    check['verdict'] = 'PASS' if check['status_code'] == check['expected'] else 'FAIL'

overall = 'PASS' if all(check['verdict'] == 'PASS' for check in checks) else 'FAIL'
result = {
    'scope': 'FastAPI TestClient endpoint evidence with dependency overrides',
    'overall_status': overall,
    'checks': checks,
}

(REPORT_DIR / 'llm08_endpoint_evidence_results.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding='utf-8',
)
print(json.dumps({'overall_status': overall, 'checks': len(checks)}, indent=2))
```

---

## 4. Hasil Pengujian Endpoint

| ID | Role | Method | Endpoint | Expected | Actual | Verdict |
|---|---|---|---|---:|---:|---|
| DOC-DETAIL-STAFF | staff | GET | `/api/documents/restricted-audit-live-test` | 403 | 403 | **PASS** |
| DOC-CHUNKS-STAFF | staff | GET | `/api/documents/restricted-audit-live-test/chunks` | 403 | 403 | **PASS** |
| DOC-PREVIEW-STAFF | staff | POST | `/api/documents/restricted-audit-live-test/preview` | 403 | 403 | **PASS** |
| CITATION-CHUNK-STAFF | staff | GET | `/api/rag/documents/by-doc-id/restricted-audit-live-test/chunks/0` | 403 | 403 | **PASS** |
| CITATION-FILE-STAFF | staff | GET | `/api/rag/documents/by-doc-id/restricted-audit-live-test/file` | 403 | 403 | **PASS** |
| DOC-DETAIL-ADMIN-POSITIVE-CONTROL | admin_pusdatik | GET | `/api/documents/restricted-audit-live-test` | 200 | 200 | **PASS** |
| CITATION-CHUNK-ADMIN-POSITIVE-CONTROL | admin_pusdatik | GET | `/api/rag/documents/by-doc-id/restricted-audit-live-test/chunks/0` | 200 | 200 | **PASS** |

---

## 5. Raw Evidence Ringkas

### Staff ditolak oleh Document API

```json
{
  "id": "DOC-DETAIL-STAFF",
  "status_code": 403,
  "body_preview": "{\"detail\":\"Akses dokumen ditolak\"}",
  "verdict": "PASS"
}
```

### Staff ditolak oleh Citation API

```json
{
  "id": "CITATION-CHUNK-STAFF",
  "status_code": 403,
  "body_preview": "{\"detail\":\"Document access denied\"}",
  "verdict": "PASS"
}
```

### Admin positive control berhasil

```json
{
  "id": "CITATION-CHUNK-ADMIN-POSITIVE-CONTROL",
  "status_code": 200,
  "body_preview": "{\"chunk_index\":0,\"text\":\"RESTRICTED_AUDIT_SECRET_CONTEXT\",...}",
  "verdict": "PASS"
}
```

---

## 6. Interpretasi untuk Tabel Laporan

Berdasarkan pengujian ini, baris berikut dapat dinyatakan sebagai endpoint-level evidence:

| Jalur | Pernyataan yang Sah | Status |
|---|---|---|
| Document API | Staff menerima HTTP 403 saat mengakses dokumen `restricted_audit`; admin menerima HTTP 200 sebagai positive control. | PASS |
| Citation API / chunk preview | Staff menerima HTTP 403 saat membuka chunk/citation preview dokumen `restricted_audit`; admin menerima HTTP 200 sebagai positive control. | PASS |

Untuk baris berikut, evidence yang tersedia tetap berasal dari unit/integration test dan script deterministik sebelumnya, bukan endpoint live dari report ini:

| Jalur | Evidence Saat Ini | Status |
|---|---|---|
| Qdrant vector search | Unit/integration test memastikan filter `allowed_roles` dipasang pada Qdrant filter. | PASS berdasarkan regression test |
| BM25 | Unit test memastikan chunk admin-only difilter dari hasil BM25 untuk role staff. | PASS berdasarkan regression test |
| Literal search | Unit test memastikan literal search menyertakan filter `allowed_roles`. | PASS berdasarkan regression test |
| Context stitching | Unit test memastikan neighbor fetch menyertakan filter `allowed_roles`. | PASS berdasarkan regression test |

---

## 7. Kesimpulan

Pengujian endpoint-level yang dijalankan menunjukkan hasil **PASS** untuk Document API dan Citation API:

- Staff ditolak dengan HTTP `403` untuk dokumen restricted.
- Admin berhasil mengakses dokumen/chunk yang sama dengan HTTP `200`.
- Positive control membuktikan fixture restricted memang ada dan dapat diakses oleh role yang berwenang.

Namun, karena tidak ditemukan dokumen restricted aktual di SQLite lokal (`0` kandidat `restricted_audit`), report ini harus diberi label:

```text
Endpoint evidence using controlled TestClient fixture
```

bukan:

```text
Live production data evidence
```

Untuk menjadikan seluruh tabel bypass path sepenuhnya sah sebagai live evidence, perlu langkah tambahan:

1. Tambahkan atau ingest dokumen aktual dengan metadata `classification=restricted_audit` dan `allowed_roles=["admin_pusdatik"]`.
2. Pastikan dokumen tersebut masuk SQLite, BM25, dan Qdrant.
3. Jalankan `/api/chat/stream` sebagai staff dan admin dengan query semantik, BM25 keyword, dan literal pasal/tabel.
4. Simpan raw SSE response dan pastikan `sources` staff tidak mengandung doc restricted, sedangkan admin dapat melihatnya.
