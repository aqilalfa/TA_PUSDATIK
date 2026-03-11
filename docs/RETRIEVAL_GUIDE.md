# Hybrid Retrieval System Documentation

**Last Updated:** 2026-01-25  
**Status:** ✅ Implemented  
**Location:** `backend/app/core/rag/`

---

## Overview

The SPBE RAG system uses a **hybrid retrieval architecture** that combines multiple search strategies for optimal accuracy:

1. **BM25** - Keyword-based search (good for exact terms like "Pasal 5")
2. **Vector Search** - Semantic search with embeddings (good for conceptual queries)
3. **Reciprocal Rank Fusion (RRF)** - Combines BM25 + Vector results
4. **Cross-Encoder Reranking** - Final accuracy boost

### Why Hybrid Retrieval?

Different retrieval methods have different strengths:

| Method | Strengths | Weaknesses | Best For |
|--------|-----------|------------|----------|
| **BM25** | Exact keyword matching, fast, no ML needed | Misses synonyms, no semantic understanding | Legal references (Pasal X), numbers, exact terms |
| **Vector Search** | Semantic similarity, handles synonyms | May miss exact keywords, requires embeddings | Conceptual questions, paraphrases |
| **Hybrid** | Best of both worlds | More complex, slower | Production RAG systems |

**Research shows hybrid retrieval can improve accuracy by 10-30% compared to single methods.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Query                           │
│              "Bagaimana audit SPBE?"                    │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────┐
│              Hybrid Retriever                             │
│                                                           │
│  ┌──────────────────┐       ┌──────────────────┐        │
│  │  BM25 Retriever  │       │ Vector Retriever │        │
│  │  (Keyword)       │       │  (Semantic)      │        │
│  │                  │       │                  │        │
│  │  Top-100 docs    │       │  Top-100 docs    │        │
│  └────────┬─────────┘       └────────┬─────────┘        │
│           │                          │                   │
│           └───────────┬──────────────┘                   │
│                       ▼                                   │
│           ┌──────────────────────┐                       │
│           │   RRF Fusion         │                       │
│           │   (Rank-based merge) │                       │
│           │   Top-100 unique     │                       │
│           └──────────┬───────────┘                       │
│                      ▼                                    │
│           ┌──────────────────────┐                       │
│           │  Cross-Encoder       │                       │
│           │  Reranker            │                       │
│           │  (Accuracy boost)    │                       │
│           └──────────┬───────────┘                       │
│                      ▼                                    │
│              ┌──────────────┐                            │
│              │  Top-10      │                            │
│              │  Results     │                            │
│              └──────────────┘                            │
└───────────────────────────────────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  RAG System  │
              │  (Generator) │
              └──────────────┘
```

---

## Components

### 1. BM25 Retriever
**File:** `backend/app/core/rag/bm25_retriever.py`

BM25 (Best Matching 25) is a ranking function based on term frequency and document length.

**Features:**
- Indonesian text preprocessing
- Legal entity preservation (Pasal, Ayat, etc.)
- Stopword removal (optimized for Indonesian)
- Persistent index storage (pickle)

**Configuration:**
```python
retriever = BM25Retriever(
    k1=1.5,          # Term frequency saturation (higher = TF matters more)
    b=0.75,          # Length normalization (higher = penalize long docs)
    remove_stopwords=True
)
```

**Best For:**
- Exact legal references: "Pasal 5 ayat (2)"
- Document numbers: "Nomor 10 Tahun 2020"
- Specific keywords: "BSSN", "audit TIK"

**Example:**
```python
from app.core.rag.bm25_retriever import BM25Retriever

retriever = BM25Retriever()
retriever.build_index(documents, doc_id_field="chunk_id", text_field="text")
results = retriever.search("Pasal 5 SPBE", top_k=10)
```

---

### 2. Vector Retriever
**File:** `backend/app/core/rag/vector_retriever.py`

Semantic search using dense embeddings from `firqaaa/indo-sentence-bert-base`.

**Features:**
- Indonesian sentence embeddings
- Qdrant vector store integration
- Metadata filtering
- Similarity threshold control

**Configuration:**
```python
retriever = VectorRetriever(
    collection_name="document_chunks",
    qdrant_url="http://localhost:6333",
    similarity_threshold=0.0  # 0-1 (cosine similarity)
)
```

**Best For:**
- Semantic questions: "Apa tujuan SPBE?"
- Paraphrased queries
- Conceptual similarity
- Multilingual queries (Indonesian/English mix)

**Example:**
```python
from app.core.rag.vector_retriever import VectorRetriever

retriever = VectorRetriever()
results = retriever.search(
    query="Bagaimana cara audit sistem?",
    top_k=10,
    filters={"doc_type": "peraturan"}
)
```

---

### 3. Reciprocal Rank Fusion (RRF)
**File:** `backend/app/core/rag/fusion.py`

RRF merges results from multiple retrievers using rank-based scoring.

**Formula:**
```
RRF_score(doc) = Σ 1 / (k + rank_i(doc))
```

Where:
- `k` = constant (default: 60)
- `rank_i(doc)` = rank of doc in retrieval method i

**Why RRF?**
- No score normalization needed (rank-based)
- Robust to different score scales
- Proven effective in IR research
- Better than simple score averaging

**Configuration:**
```python
from app.core.rag.fusion import ReciprocalRankFusion

rrf = ReciprocalRankFusion(k=60)

# Standard fusion (equal weights)
fused = rrf.fuse([bm25_results, vector_results], top_k=100)

# Weighted fusion (e.g., prefer vector 60%, BM25 40%)
fused = rrf.fuse_with_weights(
    [bm25_results, vector_results],
    weights=[0.4, 0.6],
    top_k=100
)
```

**Example Analysis:**
```python
analysis = rrf.analyze_fusion([bm25_results, vector_results])
# Output:
# {
#     "num_lists": 2,
#     "total_unique_docs": 150,
#     "common_docs": 30,
#     "overlap_percentage": 20.0
# }
```

---

### 4. Cross-Encoder Reranker
**File:** `backend/app/core/rag/reranker.py`

Final reranking using `BAAI/bge-reranker-base` cross-encoder.

**Cross-Encoder vs Bi-Encoder:**
- **Bi-Encoder** (Vector Search): Encodes query and doc separately → fast but less accurate
- **Cross-Encoder** (Reranker): Encodes [query, doc] together → slow but very accurate

**Features:**
- Pre-trained cross-encoder model
- Batch processing
- GPU acceleration
- Fallback to dummy reranker if unavailable

**Configuration:**
```python
from app.core.rag.reranker import CrossEncoderReranker

reranker = CrossEncoderReranker(
    model_name="BAAI/bge-reranker-base",
    device="cuda",      # "cuda" or "cpu"
    max_length=512,     # Max sequence length
    batch_size=32       # Batch size for inference
)
```

**Example:**
```python
# Get top-100 candidates from RRF
fused_results = rrf.fuse([bm25_results, vector_results], top_k=100)

# Rerank to get best top-10
reranked = reranker.rerank(
    query="Bagaimana audit SPBE?",
    documents=fused_results,
    top_k=10
)
```

---

### 5. Hybrid Retriever (Main Interface)
**File:** `backend/app/core/rag/hybrid_retriever.py`

Orchestrates all components into a unified retrieval pipeline.

**Full Pipeline:**
```python
from app.core.rag.hybrid_retriever import HybridRetriever

# Initialize
retriever = HybridRetriever(
    collection_name="document_chunks",
    bm25_weight=0.5,
    vector_weight=0.5,
    rrf_k=60,
    use_reranker=True
)

# Build BM25 index (one-time, vector index already exists from ingestion)
retriever.build_indices(documents)

# Search
results = retriever.search(
    query="Apa itu SPBE?",
    top_k=10,
    use_reranker=True,
    bm25_top_k=100,
    vector_top_k=100
)
```

**Method Comparison:**
```python
comparison = retriever.compare_methods("audit SPBE", top_k=5)

# Returns:
# {
#     "bm25": [...],      # BM25 only results
#     "vector": [...],    # Vector only results
#     "hybrid": [...]     # Full hybrid pipeline results
# }
```

---

## Testing

### Quick Test (Sample Data)
```bash
cd backend
python scripts/test_retrieval.py
```

### Test with Real Database
```bash
# Make sure Qdrant is running and documents are ingested
python scripts/test_retrieval.py --use-db
```

### Test Specific Query
```bash
python scripts/test_retrieval.py --query "Bagaimana cara audit TIK?"
```

### Compare Methods
```bash
python scripts/test_retrieval.py --compare
```

### Test Individual Components
```bash
# Test BM25 only
python scripts/test_retrieval.py --component bm25

# Test vector only
python scripts/test_retrieval.py --component vector --use-db

# Test reranker only
python scripts/test_retrieval.py --component reranker
```

---

## Performance Characteristics

| Component | Speed | Accuracy | GPU Required | Notes |
|-----------|-------|----------|--------------|-------|
| **BM25** | ⚡⚡⚡ Very Fast | ⭐⭐⭐ Good | No | CPU only, <10ms per query |
| **Vector Search** | ⚡⚡ Fast | ⭐⭐⭐⭐ Very Good | Optional | <50ms with GPU |
| **RRF** | ⚡⚡⚡ Very Fast | - | No | Minimal overhead |
| **Reranker** | ⚡ Slow | ⭐⭐⭐⭐⭐ Excellent | Recommended | ~500ms for 100 docs on GPU |
| **Full Hybrid** | ⚡ Slow | ⭐⭐⭐⭐⭐ Best | Recommended | Total ~600ms |

**Benchmarks (GTX 1650 4GB):**
- BM25 retrieval: ~5ms for 1000 docs
- Vector search: ~30ms for 10k docs
- Reranker (batch=32): ~400ms for 100 docs
- **Total hybrid pipeline: ~500-800ms**

---

## Configuration Best Practices

### For Legal Documents (SPBE)
```python
retriever = HybridRetriever(
    bm25_weight=0.6,        # Favor BM25 (good for legal refs)
    vector_weight=0.4,
    rrf_k=60,
    use_reranker=True
)
```

### For General Questions
```python
retriever = HybridRetriever(
    bm25_weight=0.4,        # Favor vector (good for semantics)
    vector_weight=0.6,
    rrf_k=60,
    use_reranker=True
)
```

### For Speed (Disable Reranker)
```python
retriever = HybridRetriever(
    use_reranker=False      # ~5x faster, slight accuracy loss
)
```

---

## Integration with RAG

The hybrid retriever is used in the RAG query engine (Week 3-4):

```python
# In app/core/rag/query_engine.py (to be implemented)
from app.core.rag.hybrid_retriever import HybridRetriever
from app.core.rag.llm import get_llm

class RAGQueryEngine:
    def __init__(self):
        self.retriever = HybridRetriever(use_reranker=True)
        self.llm = get_llm()
    
    def query(self, question: str, top_k: int = 5):
        # 1. Retrieve relevant chunks
        chunks = self.retriever.search(question, top_k=top_k)
        
        # 2. Build context
        context = "\n\n".join([c["text"] for c in chunks])
        
        # 3. Generate answer
        prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
        answer = self.llm.complete(prompt)
        
        return {
            "answer": answer,
            "sources": chunks
        }
```

---

## Troubleshooting

### BM25 Index Not Found
```bash
# Build index from database
python scripts/build_bm25_index.py

# Or build on-the-fly
retriever.build_indices(documents)
```

### Qdrant Connection Error
```bash
# Check if Qdrant is running
docker-compose -f docker-compose.dev.yml ps qdrant

# Restart Qdrant
docker-compose -f docker-compose.dev.yml restart qdrant
```

### Reranker Out of Memory
```python
# Reduce batch size
reranker = CrossEncoderReranker(batch_size=16)  # Default: 32

# Or disable reranker
retriever = HybridRetriever(use_reranker=False)
```

### Poor Results
1. **Check index quality:**
   ```python
   health = retriever.health_check()
   print(health)  # All should be True
   ```

2. **Analyze fusion:**
   ```python
   analysis = rrf.analyze_fusion([bm25_results, vector_results])
   print(f"Overlap: {analysis['overlap_percentage']}%")
   # Low overlap (<10%) may indicate issues
   ```

3. **Compare methods:**
   ```python
   comparison = retriever.compare_methods(query)
   # Check which method performs best
   ```

---

## Next Steps

After implementing retrieval, continue to:

1. **Week 3-4: RAG Query Engine** (`docs/RAG_GUIDE.md`)
   - Query reformulation
   - Response generation
   - Conversation memory
   - Streaming responses

2. **Week 9-10: Agentic AI** (`docs/AGENTIC_GUIDE.md`)
   - Legal analysis agent
   - Multi-document summarization
   - Citation extraction

3. **Week 11: Evaluation** (`docs/EVALUATION_GUIDE.md`)
   - RAGAS metrics
   - BUS-11 evaluation
   - Retrieval accuracy benchmarks

---

## References

- **BM25:** Robertson, S., & Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond"
- **RRF:** Cormack, G. V., et al. (2009). "Reciprocal rank fusion outperforms condorcet"
- **Cross-Encoder Reranking:** Nogueira, R., & Cho, K. (2019). "Passage Re-ranking with BERT"
- **Hybrid Retrieval:** Ma, X., et al. (2021). "A Replication Study of Dense Passage Retriever"

---

**Status:** ✅ Week 2-3 Complete  
**Next:** Week 3-4 - RAG Query Engine Implementation
