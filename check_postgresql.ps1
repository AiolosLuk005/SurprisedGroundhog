# PostgreSQL 诊断脚本
Write-Host "=== PostgreSQL 服务诊断 ===" -ForegroundColor Cyan

# 1. 检查服务状态
Write-Host "`n1. 服务状态:" -ForegroundColor Yellow
$service = Get-Service postgresql-x64-17 -ErrorAction SilentlyContinue
if ($service) {
    Write-Host "   名称: $($service.Name)" -ForegroundColor White
    Write-Host "   状态: $($service.Status)" -ForegroundColor $(if ($service.Status -eq 'Running') {'Green'} else {'Red'})
    Write-Host "   启动类型: $($service.StartType)" -ForegroundColor White
} else {
    Write-Host "   未找到服务!" -ForegroundColor Red
}

# 2. 检查端口
Write-Host "`n2. 端口 5432 检查:" -ForegroundColor Yellow
$portTest = Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue
if ($portTest.TcpTestSucceeded) {
    Write-Host "   ✓ 端口 5432 可访问" -ForegroundColor Green
} else {
    Write-Host "   ✗ 端口 5432 不可访问" -ForegroundColor Red
}

# 3. 检查进程
Write-Host "`n3. PostgreSQL 进程:" -ForegroundColor Yellow
$processes = Get-Process postgres -ErrorAction SilentlyContinue
if ($processes) {
    Write-Host "   找到 $($processes.Count) 个 postgres 进程" -ForegroundColor Green
    $processes | Select-Object Id, CPU, WorkingSet | Format-Table
} else {
    Write-Host "   未找到 postgres 进程" -ForegroundColor Red
}

# 4. 检查安装路径
Write-Host "`n4. 安装路径检查:" -ForegroundColor Yellow
$pgPath = "D:\Program Files\PostgreSQL\17"
if (Test-Path $pgPath) {
    Write-Host "   ✓ 安装目录存在: $pgPath" -ForegroundColor Green
    Write-Host "   ✓ pg_ctl.exe 存在: $(Test-Path "$pgPath\bin\pg_ctl.exe")" -ForegroundColor Green
    Write-Host "   ✓ 数据目录存在: $(Test-Path "$pgPath\data")" -ForegroundColor Green
} else {
    Write-Host "   ✗ 安装目录不存在" -ForegroundColor Red
}

# 5. 读取最新日志
Write-Host "`n5. 最新日志 (最后 10 行):" -ForegroundColor Yellow
$logDir = "D:\Program Files\PostgreSQL\17\data\log"
if (Test-Path $logDir) {
    $latestLog = Get-ChildItem $logDir -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestLog) {
        Write-Host "   日志文件: $($latestLog.Name)" -ForegroundColor White
        Write-Host "   最后修改: $($latestLog.LastWriteTime)" -ForegroundColor White
        Write-Host "`n   内容:" -ForegroundColor Gray
        Get-Content $latestLog.FullName -Tail 10 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    }
} else {
    Write-Host "   日志目录不存在" -ForegroundColor Red
}

# 6. 尝试启动建议
Write-Host "`n=== 解决方案 ===" -ForegroundColor Cyan
if ($service.Status -ne 'Running') {
    Write-Host "`n请选择以下方式之一启动 PostgreSQL:" -ForegroundColor Yellow
    Write-Host "方式 1 (推荐): 右键点击 start_postgresql.bat，选择'以管理员身份运行'" -ForegroundColor White
    Write-Host "方式 2: 在管理员 PowerShell 中运行: Start-Service postgresql-x64-17" -ForegroundColor White
    Write-Host "方式 3: Win+R 输入 services.msc，找到 postgresql-x64-17 并启动" -ForegroundColor White
}

Write-Host "`n==========================================`n" -ForegroundColor Cyan
