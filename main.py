import sys
import os
import argparse

# -----------------------------------------------------------------------
# 运行方式兼容处理：
#   方式 A: python main.py           （直接执行，__package__ 为 None）
#   方式 B: python -m SurprisedGroundhog.main  （模块执行，__package__ 已设定）
#
# 方式 A 时，Python 把 main.py 所在目录加入 sys.path，相对导入失败。
# 解决办法：若 __package__ 为 None，则将父目录（D:\Data-Lab）插入 sys.path，
# 然后使用完整包路径的绝对导入，两种方式统一为绝对导入。
# -----------------------------------------------------------------------
if __package__ is None or __package__ == '':
    _project_dir = os.path.dirname(os.path.abspath(__file__))   # D:\Data-Lab\SurprisedGroundhog
    _parent_dir  = os.path.dirname(_project_dir)                 # D:\Data-Lab
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from SurprisedGroundhog.config import SCAN_DIR
from SurprisedGroundhog.db import init_db
from SurprisedGroundhog.scanner import scan_directory


def main():
    parser = argparse.ArgumentParser(description="SurprisedGroundhog - 资产文件扫描并写入 PostgreSQL")
    parser.add_argument(
        "--path",
        type=str,
        default=SCAN_DIR,
        help="指定要扫描的资产目录路径（默认读取 .env 中的 SCAN_DIR）"
    )

    args = parser.parse_args()

    print("=========================================")
    print("    SurprisedGroundhog Asset Scanner    ")
    print("=========================================")

    # 1. 初始化数据库表结构（如果表不存在则自动建表）
    print("Initializing database tables...")
    try:
        init_db()
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database tables: {e}")
        sys.exit(1)

    # 2. 执行目录递归扫描
    print(f"Starting scan in target directory: {args.path}")
    scan_directory(args.path)


if __name__ == "__main__":
    main()
