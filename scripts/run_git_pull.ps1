$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$env:PYTHONIOENCODING = "utf-8"

$LogDir = Join-Path $ProjectDir "export\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# python "$ProjectDir\wechat.py" report @args *>> (Join-Path $LogDir "daily_report.log")

cd .\tools

cd .\wechat-decrypt\
git pull
cd ..

cd .\wx_key_source_code\
git pull
