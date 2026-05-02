@echo off
echo 正在启动 PostgreSQL 服务...
net start postgresql-x64-17
if %errorlevel% equ 0 (
    echo PostgreSQL 服务已成功启动！
    timeout /t 3
) else (
    echo 启动失败，错误代码: %errorlevel%
    echo.
    echo 请检查以下可能的原因:
    echo 1. 是否以管理员身份运行此脚本
    echo 2. PostgreSQL 数据目录是否存在
    echo 3. 查看日志: D:\Program Files\PostgreSQL\17\data\log
    pause
)
