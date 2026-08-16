@echo off
title YouTube Omni-Extractor ? Setup
cd /d "%~dp0"
echo.
echo  ==============================================
echo   YouTube Omni-Extractor ? Configuracao inicial
echo  ==============================================
echo.

REM 1. Ambiente virtual
if not exist .venv (
    echo [1/4] Criando ambiente virtual Python...
    python -m venv .venv
) else (
    echo [1/4] Ambiente virtual ja existe. Pulando.
)

REM 2. Dependencias Python
echo [2/4] Instalando dependencias Python...
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

REM 3. Deno (runtime JavaScript obrigatorio para o yt-dlp)
where deno >nul 2>&1
if %errorlevel% neq 0 (
    echo [3/4] Instalando Deno ^(runtime JS obrigatorio^)...
    powershell -Command "irm https://deno.land/install.ps1 | iex"
) else (
    echo [3/4] Deno ja instalado. Pulando.
)

REM 4. Arquivo .env
if not exist .env (
    echo [4/4] Criando .env a partir do .env.example...
    copy .env.example .env >nul
    echo      Edite o arquivo .env antes de usar o extrator.
) else (
    echo [4/4] .env ja existe. Pulando.
)

echo.
echo  ==============================================
echo   Setup concluido!
echo.
echo   Proximos passos:
echo     1. Coloque seu cookies.txt na raiz do projeto
echo     2. Edite o .env se necessario
echo     3. Execute: iniciar.bat
echo  ==============================================
echo.
pause
