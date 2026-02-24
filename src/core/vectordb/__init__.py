"""Vector database modules."""

try:
    from .chroma_client import ChromaClient, get_chroma_client
    __all__ = ["ChromaClient", "get_chroma_client"]
except ImportError:
    # chromadb not installed (e.g. Lambda deployment)
    ChromaClient = None  # type: ignore
    def get_chroma_client(*args, **kwargs):  # type: ignore
        raise RuntimeError("chromadb is not installed in this environment")
    __all__ = ["ChromaClient", "get_chroma_client"]
