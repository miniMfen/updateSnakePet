@echo off
rem SnakePet v5 启动器 —— 双击即可在桌面养蛇
rem 依赖:已安装 Python 3.10+ 与 Pillow(首次运行会自动安装 Pillow)
setlocal
set SCRIPT_DIR=%~dp0

where pythonw >nul 2>nul
if errorlevel 1 (
  echo [SnakePet] 未找到 Python,请先安装 Python 3.10+ 并勾选 "Add to PATH"。
  pause
  exit /b 1
)

rem 首次运行自动补装 Pillow(已装则跳过)
python -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo [SnakePet] 首次运行,正在安装 Pillow ...
  python -m pip install pillow
)

start "" pythonw "%SCRIPT_DIR%run_pet.py" %*
endlocal
