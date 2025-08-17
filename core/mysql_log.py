from core.config import MYSQL_CFG, MYSQL_ENABLED
def get_mysql_conn():
    import mysql.connector
    conn = mysql.connector.connect(
        host=MYSQL_CFG.get("host","127.0.0.1"),
        port=int(MYSQL_CFG.get("port",3306)),
        user=MYSQL_CFG.get("user","root"),
        password=MYSQL_CFG.get("password",""),
        database=MYSQL_CFG.get("database","groundhog"),
    )
    return conn

def ensure_history_table(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS file_ops_history (
      id BIGINT PRIMARY KEY AUTO_INCREMENT,
      op_type VARCHAR(16) NOT NULL,
      src_path TEXT NOT NULL,
      dst_path TEXT,
      old_name TEXT,
      new_name TEXT,
      op_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    conn.commit()
    cur.close()

def log_op(op_type: str, src_path: str, dst_path: str | None=None, old_name: str | None=None, new_name: str | None=None):
    if not MYSQL_ENABLED:
        return
    try:
        conn = get_mysql_conn()
        ensure_history_table(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO file_ops_history (op_type, src_path, dst_path, old_name, new_name) VALUES (%s,%s,%s,%s,%s)",
            (op_type, src_path, dst_path, old_name, new_name)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[warn] log_op failed: {e}")
