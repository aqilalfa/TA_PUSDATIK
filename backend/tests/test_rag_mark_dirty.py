import sys, os, json, tempfile, pathlib, importlib.util


def _load():
    root = pathlib.Path(__file__).resolve().parents[2]
    p = root / ".claude" / "hooks" / "rag_mark_dirty.py"
    spec = importlib.util.spec_from_file_location("rag_mark_dirty", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_matches_rag_core_edit(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    assert mod.should_mark("backend/app/core/rag/langchain_engine.py")
    mod.handle({"tool_input": {"file_path": "backend/app/core/rag/langchain_engine.py"}})
    assert flag.exists()


def test_matches_chat_route(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    mod.handle({"tool_input": {"file_path": "backend/app/api/routes/chat.py"}})
    assert flag.exists()


def test_ignores_non_rag_file(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    mod.handle({"tool_input": {"file_path": "frontend/src/views/ChatView.vue"}})
    assert not flag.exists()


def test_handles_missing_file_path(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    mod.handle({"tool_input": {}})
    assert not flag.exists()
