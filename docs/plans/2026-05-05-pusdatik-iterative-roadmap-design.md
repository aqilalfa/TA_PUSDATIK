# Pusdatik Iterative Brain Upgrade & Feature Roadmap

## Overview
This document outlines the overarching iterative strategy for building out the core features of the Pusdatik project (RAG, Chunking, Government Law parsing, Frontend Web Design) alongside the explicit creation of `.agent/skills`. We are utilizing the **"Just-In-Time Skill Creation"** (Iterative) approach. This means we will develop specific reusable agent skills exactly when they are needed for a feature, ensuring high rigor without halting feature development for prolonged periods.

## Section 1: The Warm-Up Migration
**Goal:** Migrate existing Claude skills to the Antigravity ecosystem.
* **Process:** Review `.claude/skills/rag-debug-answer/SKILL.md` and rewrite it into `.agent/skills/rag-debug-answer/SKILL.md`.
* **Standard:** Must follow strict Antigravity TDD format (precise triggers, pressure scenarios, removing workflow from the description).
* **Success Criteria:** A fully tested Antigravity skill ready to use when debugging RAG issues in the Pusdatik project.

## Section 2: The Government Law Chunking Domain
**Goal:** Master the parsing of Indonesian government regulations (UU, PP, Perpres, SE) and implement it into the ingest pipeline.
* **Skill Creation:** Create a `government-law-chunking` skill documenting how to handle hierarchical structures (Bab, Bagian, Pasal, Ayat, Huruf) so that context isn't lost during vectorization.
* **Implementation:** Refactor and perfect the existing parser (`backend/app/core/ingestion/json_structure_parser.py`) using the new skill.
* **Success Criteria:** The parser successfully chunks complex legal documents without losing the parent-child relationship of the clauses.

## Section 3: The RAG & Retrieval Domain
**Goal:** Ensure the system retrieves exact contextual data needed for complex queries (e.g., comparing tables, multi-hop reasoning).
* **Skill Creation:** Create a `rag-retrieval-patterns` skill. This dictates query rewriting, hybrid search formulation, reranking, and parent-child document retrieval techniques.
* **Implementation:** Apply these rules to the Qdrant retrieval endpoints and LlamaIndex configurations in the backend.
* **Success Criteria:** Elimination of "information not found" errors when querying cross-year table metrics.

## Section 4: The Frontend Web Design Domain
**Goal:** Build a premium, modern, and highly interactive user interface for Pusdatik.
* **Skill Creation:** Create a `frontend-aesthetic-design` skill to establish strict rules for our UI (vibrant colors, glassmorphism, micro-animations, and dynamic interactions).
* **Implementation:** Build out the website's frontend (in `frontend/src`) ensuring it looks world-class and strictly follows the design skill.
* **Success Criteria:** A visually stunning application that is highly responsive and dynamic.
