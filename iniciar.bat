@echo off
title YouTube Omni-Extractor
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo.
echo  ==============================================
echo   YouTube Omni-Extractor - Ambiente ativado!
echo  ==============================================
echo.
echo  Comandos rapidos:
echo    python app.py   -^> Interface web (http://127.0.0.1:5000)
echo    python main.py  -^> Terminal (menu interativo)
echo.
cmd /k
