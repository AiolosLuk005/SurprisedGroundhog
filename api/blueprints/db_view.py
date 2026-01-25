from flask import Blueprint, jsonify, request, render_template
from core.pg_db import get_pg_conn, PG_ENABLED

bp = Blueprint("db_view", __name__)

@bp.get("/")
def index():
    return render_template("db_view.html", pg_enabled=PG_ENABLED)

@bp.get("/api/files")
def get_db_files():
    if not PG_ENABLED:
        return jsonify({"ok": False, "error": "PostgreSQL is not enabled"}), 400

    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(int(request.args.get("page_size", 50)), 1)
    search = request.args.get("search", "").strip()
    
    conn = get_pg_conn()
    if not conn:
        return jsonify({"ok": False, "error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # Build query
        base_query = "SELECT full_path, name, dir_path, ext, size_bytes, mtime_iso, sha256, keywords, last_scanned FROM screened_files"
        count_query = "SELECT COUNT(*) FROM screened_files"
        params = []
        
        if search:
            where_clause = " WHERE name ILIKE %s OR full_path ILIKE %s OR %s = ANY(keywords)"
            base_query += where_clause
            count_query += where_clause
            params = [f"%{search}%", f"%{search}%", search]
        
        # Get total count
        cur.execute(count_query, params)
        total = cur.fetchone()[0]
        
        # Get data with pagination
        base_query += " ORDER BY last_scanned DESC LIMIT %s OFFSET %s"
        cur.execute(base_query, params + [page_size, (page - 1) * page_size])
        
        rows = cur.fetchall()
        data = []
        for r in rows:
            data.append({
                "full_path": r[0],
                "name": r[1],
                "dir_path": r[2],
                "ext": r[3],
                "size_bytes": r[4],
                "mtime_iso": r[5],
                "sha256": r[6],
                "keywords": r[7],
                "last_scanned": r[8].isoformat() if r[8] else None
            })
            
        cur.close()
        conn.close()
        return jsonify({"ok": True, "data": data, "total": total})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
