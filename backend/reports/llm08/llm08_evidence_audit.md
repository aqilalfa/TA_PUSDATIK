# LLM08 Evidence Audit

Overall status: **PASS**

## Unauthorized Retrieval Scenario Results
| Scenario | User Role | Target Data | Expected | Actual | Leaked Items | Status |
|---|---|---|---|---|---|---|
| Qdrant vector search scoped by document and evaluator role | staff | admin-doc / admin_pusdatik | Filter includes allowed_roles=staff, so admin-only chunks are excluded | allowed_roles filter present | 0 | PASS |
| Authenticated user without roles fails closed | [] | all restricted chunks | Filter uses sentinel __spbe_no_matching_role__ | __spbe_no_matching_role__ | 0 | PASS |
| BM25/local retrieval removes inaccessible admin chunks | staff | admin-only BM25 chunk | Only staff-allowed chunk remains | eval-doc | 0 | PASS |
| Document/citation API denies admin-only metadata | staff | admin-only document/citation | Access check returns False / API should return 403 | False | 0 | PASS |
| User-facing cited sources exclude forbidden doc_id | staff | admin-doc cited source card | 0 forbidden cited sources | 0 forbidden cited sources | 0 | PASS |

## Citation Leak Rate
| Total Cited Sources | Forbidden Cited Sources | Citation Leak Rate | Status |
|---|---|---|---|
| 1 | 0 | 0.0% | PASS |

## Metadata Completeness
| Storage | Total Checked | Complete | Missing | Completeness Rate | Status |
|---|---|---|---|---|---|
| SQLite documents | 20 | 20 | 0 | 100.0% | PASS |
| BM25 index sample | 1000 | 1000 | 0 | 100.0% | PASS |
| Qdrant payload sample | 20 | 20 | 0 | 100.0% | PASS |

Catatan environment:
- Qdrant URL: `http://localhost:6333`
- Qdrant reachable: `True`
- Qdrant detail: `200`

## Poisoned / Malicious Chunk Scenario
| Scenario | User Role | Chunk Allowed Roles | Retrieved | Entered LLM Context | Leaked Citation | Status |
|---|---|---|---|---|---|---|
| Poisoned admin-only chunk with malicious retrieval instruction | staff | admin_pusdatik | False | False | False | PASS |
