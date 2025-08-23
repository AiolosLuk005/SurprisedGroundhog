# -*- coding: utf-8 -*-
# 仅本机访问（localhost），适合开发调试
from app_unified import create_app
from core.config import PORT

# 预加载关键词服务模块，确保依赖可用
try:  # pragma: no cover - 仅在运行时导入
    import services.keywords  # noqa: F401
except Exception:
    pass

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=PORT, debug=True)
