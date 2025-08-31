# -*- coding: utf-8 -*-
# 局域网可访问；/full/* 默认仅限本机，可在 config/settings.json 中开启 allow_remote_full 放开
from app_unified import create_app
from core.config import PORT

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=False)
