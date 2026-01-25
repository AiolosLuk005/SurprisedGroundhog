import logging
import psycopg2
from psycopg2.extras import execute_values
from core.config import PG_CFG, PG_ENABLED

logger = logging.getLogger(__name__)

def get_pg_conn():
    if not PG_ENABLED:
        return None
    try:
        conn = psycopg2.connect(
            host=PG_CFG["host"],
            port=PG_CFG["port"],
            user=PG_CFG["user"],
            password=PG_CFG["password"],
            database=PG_CFG["database"]
        )
        return conn
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        return None

def ensure_pg_tables():
    conn = get_pg_conn()
    if not conn:
        return
    try:
        cur = conn.cursor()
        # Create screened_files table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS screened_files (
            full_path TEXT PRIMARY KEY,
            name TEXT,
            dir_path TEXT,
            ext TEXT,
            size_bytes BIGINT,
            mtime_iso TEXT,
            sha256 TEXT,
            keywords TEXT[],
            last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to ensure PostgreSQL tables: {e}")

def upsert_files(files_data: list):
    """
    files_data: list of dicts from asdict(row)
    """
    if not PG_ENABLED or not files_data:
        logger.info("Skipping upsert: PG not enabled or no data")
        return

    conn = get_pg_conn()
    if not conn:
        raise Exception("Failed to connect to PostgreSQL")

    try:
        ensure_pg_tables()
        cur = conn.cursor()
        
        # Prepare data for upsert (without last_scanned, it's auto-generated)
        values = []
        for f in files_data:
            values.append((
                f["full_path"],
                f["name"],
                f["dir_path"],
                f["ext"],
                f["size_bytes"],
                f["mtime_iso"],
                f.get("sha256", ""),
                f.get("keywords", [])
            ))

        query = """
        INSERT INTO screened_files (full_path, name, dir_path, ext, size_bytes, mtime_iso, sha256, keywords, last_scanned)
        VALUES %s
        ON CONFLICT (full_path) DO UPDATE SET
            name = EXCLUDED.name,
            dir_path = EXCLUDED.dir_path,
            ext = EXCLUDED.ext,
            size_bytes = EXCLUDED.size_bytes,
            mtime_iso = EXCLUDED.mtime_iso,
            sha256 = EXCLUDED.sha256,
            keywords = EXCLUDED.keywords,
            last_scanned = CURRENT_TIMESTAMP;
        """
        
        execute_values(cur, query, values, template="(%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)")
        conn.commit()
        logger.info(f"Successfully upserted {len(files_data)} files to PostgreSQL")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to upsert files to PostgreSQL: {e}")
        if conn:
            conn.close()
        raise  # Re-raise the exception so the API can report it
