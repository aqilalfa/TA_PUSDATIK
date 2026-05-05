import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib.util
from pathlib import Path

def test_evaluate_rag_default_model_is_qwen3_5_4b():
    spec = importlib.util.spec_from_file_location(
        "evaluate_rag",
        Path(__file__).parent.parent / "scripts" / "evaluate_rag.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_MODEL == "qwen3.5:4b"
