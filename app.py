# -*- coding: utf-8 -*-
# 仅本机访问（localhost），适合开发调试
from app_unified import create_app
from core.config import PORT

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=PORT, debug=True)
