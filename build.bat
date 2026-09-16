@echo off
setlocal enabledelayedexpansion

:: Set UTF-8 encoding
chcp 65001 >nul 2>&1

echo ========================================
echo Publish Helper EXE Builder
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.9+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] Python found - %%i
echo.

:: Clean old builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo [OK] Cleaned old builds
echo.

:: Install PyInstaller
:: 注意：必须用 "python -m pip" 而不是直接 pip.exe。直接调用 pip 时，它绑定的可能
:: 是另一个（已卸载/损坏的）Python 安装，会出现 "Unable to create process" 报错。
echo Installing PyInstaller...
python -m pip install pyinstaller -q
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)
echo [OK] PyInstaller installed
echo.

:: Install dependencies
echo Installing dependencies...
python -m pip install -r requirements.txt -q
echo [OK] Dependencies installed
echo.

:: Run PyInstaller
echo Packaging... This may take a few minutes.
python -m PyInstaller --clean publish-helper.spec
if errorlevel 1 (
    echo [ERROR] Packaging failed!
    pause
    exit /b 1
)
echo [OK] Packaging complete
echo.

:: Verify output
echo Verifying output...
if exist "dist\Publish Helper.exe" (
    echo [OK] Single EXE created - all dependencies included
    echo      The EXE contains all Python runtime and libraries
) else (
    echo [ERROR] EXE not found!
    pause
    exit /b 1
)
echo.

echo ========================================
echo SUCCESS! Build complete.
echo Output: dist\Publish Helper.exe
echo ========================================
echo.
pause
