import asyncio
import pandas as pd
import json
from loguru import logger
from typing import List, Dict, Any, Set
from app.core.rag.langchain_engine import langchain_engine
import numpy as np
import os

# Configuration
CSV_PATH = "d:/aqil/pusdatik/data/ground_truth/ground_truth_evaluasi_spbe.csv"
TOP_K_RANGE = [1, 3, 5, 10]

def parse_ground_truth_ids(gt_str: str) -> Set[int]:
    """Parse 'CHUNK 1, CHUNK 3' -> {1, 3}"""
    if pd.isna(gt_str) or not gt_str:
        return set()
    
    # Extract numbers from string like "CHUNK 1, CHUNK 3"
    import re
    ids = re.findall(r'\d+', str(gt_str))
    return {int(i) for i in ids}

async def evaluate_query(question: str, gt_ids: Set[int], gt_metadata: Dict[str, Any], k_max: int = 10):
    """Perform retrieval and check against ground truth."""
    # Ensure Qdrant URL uses 127.0.0.1 for local Windows/Docker compatibility
    langchain_engine.qdrant_url = langchain_engine.qdrant_url.replace("localhost", "127.0.0.1")
    
    # Force re-initialization with correct URL if needed
    if not langchain_engine._initialized:
        langchain_engine.initialize()
    
    retriever = langchain_engine.qdrant.as_retriever(search_kwargs={"k": k_max})
    
    # Get retrieved docs
    docs = await retriever.ainvoke(question)
    
    ranks = []
    found_at = None
    
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        chunk_idx = meta.get("chunk_index")
        
        # Match by chunk_index OR by specific metadata if index is not reliable
        is_match = False
        if chunk_idx in gt_ids:
            is_match = True
        else:
            # Check if all keys in gt_metadata match the retrieved meta (using flexible matching)
            match_count = 0
            for key, val in gt_metadata.items():
                target_val = str(val).lower()
                actual_val = str(meta.get(key, "")).lower()
                
                # Substring match: Either GT value in Actual, or vice-versa
                if target_val in actual_val or actual_val in target_val:
                    match_count += 1
            
            if len(gt_metadata) > 0 and match_count == len(gt_metadata):
                is_match = True
        
        if is_match:
            ranks.append(i)
            if found_at is None:
                found_at = i
                
    return {
        "found_at": found_at,
        "hits": ranks,
        "total_retrieved": len(docs)
    }

async def main():
    logger.info(f"Loading Ground Truth from {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        logger.error("CSV file not found!")
        return
        
    df = pd.read_csv(CSV_PATH)
    results = []
    
    logger.info(f"Starting evaluation for {len(df)} queries...")
    
    for idx, row in df.iterrows():
        question = row['pertanyaan']
        gt_ids = parse_ground_truth_ids(row['ground_truth_id'])
        
        try:
            gt_meta = json.loads(row['metadata_konteks'])
        except:
            gt_meta = {}
            
        logger.info(f"Evaluating Q{row['no']}: {question[:50]}...")
        eval_res = await evaluate_query(question, gt_ids, gt_meta, k_max=max(TOP_K_RANGE))
        
        eval_res.update({
            "no": row['no'],
            "question": question,
            "gt_ids": gt_ids
        })
        results.append(eval_res)

    # Calculate Metrics
    logger.info("--- EVALUATION RESULTS ---")
    
    summary = {}
    for k in TOP_K_RANGE:
        hits = sum(1 for r in results if r['found_at'] and r['found_at'] <= k)
        hit_rate = hits / len(results)
        
        mrr_sum = sum(1.0 / r['found_at'] if r['found_at'] and r['found_at'] <= k else 0 for r in results)
        mrr = mrr_sum / len(results)
        
        logger.info(f"K={k} | Hit Rate: {hit_rate:.4f} | MRR: {mrr:.4f}")
        summary[k] = {"hit_rate": hit_rate, "mrr": mrr}

    # Save detailed results
    output_path = "d:/aqil/pusdatik/data/evaluation_report.json"
    with open(output_path, "w") as f:
        # Convert sets to lists for JSON
        for r in results:
            r['gt_ids'] = list(r['gt_ids'])
        json.dump(results, f, indent=2)
    
    logger.success(f"Evaluation complete. Detailed report saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
