import ast
import sys

sys.path.insert(0, ".")


def assert_contains(content: str, needle: str, label: str):
    assert needle in content, f"{label} missing: {needle}"


# 1) langchain_engine: syntax + phase-2 features
engine_path = "app/core/rag/langchain_engine.py"
engine_code = open(engine_path, encoding="utf-8").read()
ast.parse(engine_code)

assert_contains(engine_code, "expand_query", "langchain_engine")
assert_contains(engine_code, "def _bm25_search", "langchain_engine")
assert_contains(engine_code, "def _rrf_fusion", "langchain_engine")
assert_contains(engine_code, "def _rerank", "langchain_engine")
assert_contains(engine_code, "def retrieve_context", "langchain_engine")
assert_contains(engine_code, "use_rag", "langchain_engine.retrieve_context")
assert_contains(engine_code, "top_k", "langchain_engine.retrieve_context")
print("[OK] langchain_engine.py - query expansion + hybrid retrieval + reranker")

# 2) chat stream route: validation integrated
chat_path = "app/api/routes/chat.py"
chat_code = open(chat_path, encoding="utf-8").read()
ast.parse(chat_code)

assert_contains(chat_code, "validate_answer", "chat.py")
assert_contains(chat_code, "event: validation", "chat.py")
assert_contains(chat_code, '"validation": validation', "chat.py complete payload")
print("[OK] chat.py - validation event + complete payload")

# 3) duplicate context formatters removed
prompts_path = "app/core/rag/prompts.py"
prompts_code = open(prompts_path, encoding="utf-8").read()
ast.parse(prompts_code)
assert "def format_context(" not in prompts_code, "prompts.py still has duplicate format_context"
print("[OK] prompts.py - duplicate format_context removed")

formatting_path = "app/core/formatting.py"
formatting_code = open(formatting_path, encoding="utf-8").read()
ast.parse(formatting_code)
assert "def format_context_with_parent(" not in formatting_code, "formatting.py still has duplicate format_context_with_parent"
print("[OK] formatting.py - duplicate format_context_with_parent removed")

print("\n=== PHASE 2 ALL CHECKS PASSED ===")
