import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed; use env vars directly


def _env_set(key: str, default: str) -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")



def _env_set_of(key: str, default: str) -> set:
    val = os.getenv(key, default)
    items = [v.strip() for v in val.split(",") if v.strip()]
    return set(items)


# --- File ingestion ---
SUPPORTED_EXTENSIONS = {f".{ext}" for ext in _env_set_of("SUPPORTED_EXTENSIONS", "java,py")}
IGNORED_DIRS = _env_set_of("IGNORED_DIRS", ".git,__pycache__,node_modules,venv,.venv,target,build,dist,.idea,.vscode")

# --- tree-sitter language grammars ---
JAVA_LANGUAGE_PACKAGE = "tree_sitter_java"
PYTHON_LANGUAGE_PACKAGE = "tree_sitter_python"

# --- Diagram output ---
DEFAULT_OUTPUT_FILENAME = _env_set("DEFAULT_OUTPUT_FILENAME", "architecture.puml")

# --- RAG / Embeddings ---
ENABLE_RAG = _env_bool("ENABLE_RAG", False)
CHROMA_PERSIST_DIR = _env_set("CHROMA_PERSIST_DIR", "./chroma_db")
EMBEDDING_MODEL = _env_set("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
