from flask import Blueprint, request, jsonify, current_app
from services.retrieval import CollectionManager
from core.extractors import extract_chunks
from core.chunking import index_chunks
from core.utils.iterfiles import is_under_allowed_roots

bp = Blueprint("search", __name__)

# Note: We need a way to share the retriever instance. 
# Either a global here or managed by app extension.
# For simplicity in this plan, we instantiate one global here, similar to previous routes.py
retriever = CollectionManager()

@bp.post("/search")
def search():
    p = request.get_json(silent=True) or {}
    collection = p.get("collection", "default")

    res = retriever.query(
        collection,
        [p.get("query", "")],
        k=p.get("k", 10),
        where=p.get("where"),
        where_document=p.get("where_document"),
        search_type=p.get("search_type", "hybrid"),
    )

    hits = {
        "ids": [h["id"] for h in res],
        "documents": [h["document"] for h in res],
        "metadatas": [h["metadata"] for h in res],
        "distances": [1 - float(h.get("score", 0.0)) for h in res],
        "chunks": [h.get("chunk", {}) for h in res],
    }

    return jsonify({"results": hits})

@bp.post("/index")
def index_file():
    data = request.get_json(silent=True) or {}
    path = data.get("path")
    if not (path and is_under_allowed_roots(path)):
        return jsonify({"ok": False, "error": "路径不合法"}), 400
    chunks = extract_chunks(path)
    count = index_chunks(chunks, retriever)
    return jsonify({"ok": True, "chunks": count})
