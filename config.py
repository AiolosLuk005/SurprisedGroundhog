import os
import urllib.parse
from dotenv import load_dotenv

# 按优先级查找 .env 文件：
#   1. 当前项目目录（D:\Data-Lab\SurprisedGroundhog\.env）
#   2. 父目录（D:\Data-Lab\.env）
#   3. 同级 XfilesHub 目录（D:\Data-Lab\XfilesHub\.env）—— 共享配置
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
_sibling_xfileshub = os.path.join(_parent_dir, 'XfilesHub', '.env')

_env_candidates = [
    os.path.join(_this_dir, '.env'),
    os.path.join(_parent_dir, '.env'),
    _sibling_xfileshub,
]

_loaded = False
for _env_path in _env_candidates:
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        print(f"[config] Loaded .env from: {_env_path}")
        _loaded = True
        break

if not _loaded:
    load_dotenv()  # 最终退回到系统默认
    print("[config] Warning: No .env file found, using system environment variables.")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "xfileshub")

# 扫描文件夹路径
SCAN_DIR = os.getenv("SCAN_DIR", "d:/Data-Lab/TestAssets")

# 拼接 SQLAlchemy pg8000 连接串
# 格式: postgresql+pg8000://user:password@host:port/dbname
# 使用 quote_plus 对账号密码中的特殊字符（@、:、# 等）进行 URL 编码
safe_user = urllib.parse.quote_plus(DB_USER)
safe_password = urllib.parse.quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql+pg8000://{safe_user}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
