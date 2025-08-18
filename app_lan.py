# -*- coding: utf-8 -*-
# 局域网可访问；/full/* 仍仅限本机（统一入口里已做限制）
from app_unified import create_app
from core.config import PORT

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=False)
