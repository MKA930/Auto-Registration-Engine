@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: 配置参数
set PYTHON_VERSION=3.11.9
set ENV_NAME=auto-register
set PROJECT_DIR=%~dp0
set REQUIREMENTS_FILE=%PROJECT_DIR%requirements.txt
set START_SCRIPT=%PROJECT_DIR%start.bat
set STOP_SCRIPT=%PROJECT_DIR%stop.bat
set PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
set PYTHON_DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe

echo ============================================
echo Auto-Registration-Engine 环境自动部署脚本
echo 当前系统: Windows
echo 目标 Python 版本: %PYTHON_VERSION%
echo ============================================

:: 1. 检查 Python 是否已安装
python --version > nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2 delims= " %%v in ('python --version') do (
        set INSTALLED_VERSION=%%v
        echo 已检测到 Python 版本: !INSTALLED_VERSION!
        if "!INSTALLED_VERSION:~0,4!"=="3.11" (
            echo Python 版本符合要求，跳过安装
            goto :CREATE_ENV
        ) else (
            echo Python 版本不符合要求，将安装指定版本 %PYTHON_VERSION%
        )
    )
)

:: 2. 下载 Python 安装包
echo [1/8] 下载 Python %PYTHON_VERSION% 安装包...
powershell -Command "(New-Object System.Net.WebClient).DownloadFile('%PYTHON_DOWNLOAD_URL%', '%PROJECT_DIR%%PYTHON_INSTALLER%')"
if %errorlevel% neq 0 (
    echo 错误: 下载 Python 安装包失败
    exit /b 1
)

:: 3. 静默安装 Python
echo [2/8] 静默安装 Python %PYTHON_VERSION%...
"%PROJECT_DIR%%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if %errorlevel% neq 0 (
    echo 错误: Python 安装失败
    exit /b 1
)

:: 4. 刷新环境变量
echo [3/8] 刷新系统环境变量...
refreshenv > nul 2>&1
call refreshenv > nul 2>&1

:CREATE_ENV
:: 5. 创建虚拟环境
echo [4/8] 创建独立虚拟环境: %ENV_NAME%
cd /d "%PROJECT_DIR%"
python -m venv "%ENV_NAME%"
if %errorlevel% neq 0 (
    echo 错误: 创建虚拟环境失败
    exit /b 1
)

:: 6. 激活环境并升级 pip
echo [5/8] 升级 pip 到最新版本...
call "%PROJECT_DIR%%ENV_NAME%\Scripts\activate.bat"
python -m pip install --upgrade pip -i https://pypi.mirrors.ustc.edu.cn/simple/
if %errorlevel% neq 0 (
    echo 错误: 升级 pip 失败
    exit /b 1
)

:: 7. 安装项目依赖
echo [6/8] 安装项目依赖...
if not exist "%REQUIREMENTS_FILE%" (
    echo 错误: 未找到 requirements.txt
    exit /b 1
)
pip install -r "%REQUIREMENTS_FILE%" -i https://pypi.mirrors.ustc.edu.cn/simple/
if %errorlevel% neq 0 (
    echo 错误: 安装依赖失败
    exit /b 1
)

:: 8. 生成一键启动/停止脚本
echo [7/8] 生成一键启动/停止脚本...

:: 生成 start.bat
(
echo @echo off
echo chcp 65001 ^> nul
echo setlocal
echo set PROJECT_DIR=%PROJECT_DIR%
echo set ENV_NAME=%ENV_NAME%
echo set LOG_FILE=%%PROJECT_DIR%%\run.log
echo.
echo :: 停止旧进程
echo taskkill /f /im python.exe /fi "WINDOWTITLE eq main.py" ^> nul 2^>^&1
echo.
echo :: 激活虚拟环境
echo call "%%PROJECT_DIR%%\%%ENV_NAME%%\Scripts\activate.bat"
echo.
echo :: 后台启动项目
echo start /b python main.py ^>^> "%%LOG_FILE%%" 2^>^&1 ^< nul
echo.
echo echo ✅ 项目已启动，日志文件: %%LOG_FILE%%
echo echo 🔍 实时查看日志: notepad %%LOG_FILE%%
echo pause
) > "%START_SCRIPT%"

:: 生成 stop.bat
(
echo @echo off
echo chcp 65001 ^> nul
echo echo 正在停止 main.py 进程...
echo taskkill /f /im python.exe /fi "WINDOWTITLE eq main.py"
echo echo ✅ 项目已停止
echo pause
) > "%STOP_SCRIPT%"

:: 9. 部署完成
echo [8/8] 部署完成！
echo ============================================
echo ✅ 环境部署成功！
echo 📁 项目目录: %PROJECT_DIR%
echo 🐍 Python 版本: %PYTHON_VERSION%
echo 📦 虚拟环境: %PROJECT_DIR%%ENV_NAME%
echo 🚀 一键启动: start.bat
echo 🛑 一键停止: stop.bat
echo 📝 日志文件: %PROJECT_DIR%run.log
echo ============================================

:: 退出虚拟环境
call "%PROJECT_DIR%%ENV_NAME%\Scripts\deactivate.bat"

:: 清理安装包
del /f /q "%PROJECT_DIR%%PYTHON_INSTALLER%" > nul 2>&1

pause
endlocal