@echo off
REM ============================================================
REM  BUILD COMPLETO - CONFEITARIA v1.12.1
REM  Verifica, prepara e gera executável + instalador
REM  Sistema Local com Banco de Dados Incluído
REM  Atualizado: 2025-12-05
REM ============================================================

setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo.
echo ════════════════════════════════════════════════════════
echo  🍰 BUILD COMPLETO - SISTEMA CONFEITARIA v1.12.1
echo  Sistema Local com Banco de Dados Populado
echo ════════════════════════════════════════════════════════
echo.

REM ============================================================
REM ETAPA 1: VERIFICAR BANCO DE DADOS
REM ============================================================

echo [1/6] 🗄️  Verificando banco de dados...
echo.

if not exist "confeitaria.db" (
    echo ❌ ERRO: Banco de dados não encontrado!
    echo.
    echo 💡 Criando banco de dados com dados de exemplo...
    echo    (40 clientes, 40 produtos, 100 pedidos)
    echo.
    
    REM Detectar Python
    set "PYTHON_CMD="
    if exist ".venv\Scripts\python.exe" (
        set "PYTHON_CMD=.venv\Scripts\python.exe"
    ) else if exist "venv310\Scripts\python.exe" (
        set "PYTHON_CMD=venv310\Scripts\python.exe"
    ) else if exist "C:\Users\Nasci\AppData\Local\Programs\Python\Python312\python.exe" (
        set "PYTHON_CMD=C:\Users\Nasci\AppData\Local\Programs\Python\Python312\python.exe"
    ) else (
        where python.exe >nul 2>&1
        if not errorlevel 1 (
            for /f "delims=" %%i in ('where python.exe') do set "PYTHON_CMD=%%i"
        ) else (
            echo ❌ ERRO: Python não encontrado!
            echo    Por favor, execute manualmente: python populate_database.py
            pause
            exit /b 1
        )
    )
    
    REM Executar script de população
    "%PYTHON_CMD%" populate_database.py
    if errorlevel 1 (
        echo ❌ ERRO ao criar banco de dados!
        echo    Execute manualmente com: "%PYTHON_CMD%" populate_database.py
        pause
        exit /b 1
    )
    echo.
)

echo ✅ Banco de dados encontrado: confeitaria.db

REM Verificar tamanho
for %%F in (confeitaria.db) do set size=%%~zF
set /a sizeMB=%size% / 1048576
echo    📊 Tamanho: %sizeMB% MB
echo.

REM Procurar ambiente virtual
if exist ".venv\Scripts\python.exe" (
    echo ✅ Ambiente virtual encontrado: .venv
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    set "PIP_CMD=.venv\Scripts\pip.exe"
    goto :python_found
)

if exist "venv310\Scripts\python.exe" (
    echo ✅ Ambiente virtual encontrado: venv310
    set "PYTHON_CMD=venv310\Scripts\python.exe"
    set "PIP_CMD=venv310\Scripts\pip.exe"
    goto :python_found
)

REM Tentar Python do Nasci
if exist "C:\Users\Nasci\AppData\Local\Programs\Python\Python312\python.exe" (
    echo ✅ Python encontrado: Python 3.12
    set "PYTHON_CMD=C:\Users\Nasci\AppData\Local\Programs\Python\Python312\python.exe"
    set "PIP_CMD=C:\Users\Nasci\AppData\Local\Programs\Python\Python312\Scripts\pip.exe"
    goto :python_found
)

REM Buscar Python no PATH
where python.exe >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where python.exe') do (
        set "PYTHON_CMD=%%i"
        set "PIP_CMD=pip"
        goto :python_found
    )
)

echo ❌ ERRO: Python não encontrado!
echo    Instale Python 3.10+ ou crie ambiente virtual
pause
exit /b 1 do sistema
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERRO: Python não encontrado!
    echo    Instale Python 3.10+ ou crie ambiente virtual
    pause
    exit /b 1
)
echo ⚠️  Usando Python do sistema
set "PYTHON_CMD=python"
set "PIP_CMD=pip"

:python_found
for /f "tokens=*" %%V in ('"%PYTHON_CMD%" --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo ✅ !PYTHON_VERSION!

REM Verificar PyInstaller
"%PYTHON_CMD%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  PyInstaller não instalado. Instalando...
    "%PIP_CMD%" install pyinstaller
    if errorlevel 1 (
        echo ❌ ERRO ao instalar PyInstaller
        pause
        exit /b 1
    )
)
echo ✅ PyInstaller instalado
echo.

REM ============================================================
REM ETAPA 3: VERIFICAR INNO SETUP
REM ============================================================

echo [3/6] 📦 Verificando Inno Setup...
echo.

set "INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%INNO_PATH%" (
    echo ⚠️  Inno Setup não encontrado
    echo    Download: https://jrsoftware.org/isinfo.php
    echo.
    echo    O executável será criado, mas sem instalador.
    set "SKIP_INSTALLER=1"
    timeout /t 3 >nul
) else (
    echo ✅ Inno Setup encontrado
    set "SKIP_INSTALLER=0"
)
echo.

REM ============================================================
REM ETAPA 4: LIMPAR BUILDS ANTERIORES
REM ============================================================

echo [4/6] 🧹 Limpando builds anteriores...
echo.

if exist "build" (
    echo    Removendo pasta build...
    rmdir /s /q "build" 2>nul
)

if exist "dist" (
    echo    Removendo pasta dist...
    rmdir /s /q "dist" 2>nul
)

if exist "output" (
    echo    Limpando pasta output...
    del /q "output\*.exe" 2>nul
)

REM Limpar cache Python
if exist "__pycache__" rmdir /s /q "__pycache__" 2>nul
if exist "core\__pycache__" rmdir /s /q "core\__pycache__" 2>nul
if exist "ui\__pycache__" rmdir /s /q "ui\__pycache__" 2>nul

echo ✅ Limpeza concluída
echo.

REM ============================================================
REM ETAPA 5: COMPILAR COM PYINSTALLER
REM ============================================================

echo [5/6] 🔨 Compilando executável com PyInstaller...
echo.
echo    Isso pode levar alguns minutos...
echo.

"%PYTHON_CMD%" -m PyInstaller --clean --noconfirm Confeitaria.spec

if errorlevel 1 (
    echo.
    echo ❌ ERRO na compilação!
    echo    Verifique os logs acima para detalhes.
    pause
    exit /b 1
)

echo.
echo ✅ Executável compilado com sucesso!

REM Verificar se executável foi criado
if not exist "dist\Confeitaria\Confeitaria.exe" (
    echo ❌ ERRO: Executável não encontrado em dist\Confeitaria\
    pause
    exit /b 1
)

echo    📍 Local: dist\Confeitaria\Confeitaria.exe
echo.

REM ============================================================
REM ETAPA 6: GERAR INSTALADOR COM INNO SETUP
REM ============================================================

if "%SKIP_INSTALLER%"=="1" (
    echo [6/6] ⏭️  Pulando criação do instalador
    echo.
    goto :final
)

echo [6/6] 📦 Gerando instalador com Inno Setup...
echo.

"%INNO_PATH%" "Confeitaria.iss"

if errorlevel 1 (
    echo.
    echo ❌ ERRO ao criar instalador!
    pause
    exit /b 1
)

echo.
echo ✅ Instalador criado com sucesso!

if exist "output\Confeitaria_Setup_1.12.1.exe" (
    echo    📍 Local: output\Confeitaria_Setup_1.12.1.exe
    for %%F in (output\Confeitaria_Setup_1.12.1.exe) do set installer_size=%%~zF
    set /a installer_mb=!installer_size! / 1048576
    echo    📊 Tamanho: !installer_mb! MB
) else (
    echo ⚠️  Instalador não encontrado no local esperado
)
echo.

:final
REM ============================================================
REM RESUMO FINAL
REM ============================================================

echo.
echo ════════════════════════════════════════════════════════
echo  ✅ BUILD CONCLUÍDO COM SUCESSO!
echo ════════════════════════════════════════════════════════
echo.
echo 📦 ARQUIVOS GERADOS:
echo.
echo    1️⃣  Executável:
echo       📁 dist\Confeitaria\Confeitaria.exe
echo       ✅ Pronto para uso local
echo.

if "%SKIP_INSTALLER%"=="0" (
    echo    2️⃣  Instalador:
    echo       📁 output\Confeitaria_Setup_1.12.1.exe
    echo       ✅ Pronto para distribuição
    echo.
)

echo 🗄️  BANCO DE DADOS INCLUÍDO:
echo    ✅ 40 Clientes
echo    ✅ 40 Produtos com preços
echo    ✅ 100 Pedidos (últimos 12 meses)
echo    ✅ Dados de demonstração prontos
echo.
echo 🚀 PRÓXIMOS PASSOS:
echo.

if "%SKIP_INSTALLER%"=="0" (
    echo    • Distribuir: output\Confeitaria_Setup_1.12.1.exe
    echo    • Instalar em qualquer computador Windows
    echo    • Login: admin / admin
) else (
    echo    • Testar: dist\Confeitaria\Confeitaria.exe
    echo    • Copiar pasta dist\Confeitaria\ para distribuir
    echo    • Login: admin / admin
)
echo.
echo ════════════════════════════════════════════════════════
echo.
pause
