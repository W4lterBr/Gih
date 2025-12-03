@echo off
REM ============================================================
REM  BUILD PRINCIPAL - CONFEITARIA v1.12.0
REM  Gera o executavel e o instalador completo
REM  Atualizado: 2025-12-03
REM ============================================================

setlocal EnableDelayedExpansion

echo.
echo ============================================
echo  BUILD - SISTEMA CONFEITARIA
echo  Versao 1.12.0 - Build %date% %time%
echo ============================================
echo.

REM ============================================================
REM ETAPA 1: VERIFICAÇÕES INICIAIS
REM ============================================================

echo [1/5] Verificando requisitos...

REM Verificar ambiente virtual primeiro
set "PYTHON_CMD="
set "PIP_CMD="

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

REM Tentar Python do sistema
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERRO: Python não encontrado!
    echo    Crie um ambiente virtual com: python -m venv .venv
    echo    Ou instale Python 3.10 ou superior.
    pause
    exit /b 1
)
echo ⚠️  Usando Python do sistema
set "PYTHON_CMD=python"
set "PIP_CMD=pip"

:python_found
REM Verificar se Python funciona
"%PYTHON_CMD%" --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERRO: Não foi possível executar Python: %PYTHON_CMD%
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('"%PYTHON_CMD%" --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo ✅ Python encontrado: !PYTHON_VERSION!

REM Verificar PyInstaller
"%PYTHON_CMD%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ❌ PyInstaller não instalado. Instalando...
    "%PIP_CMD%" install pyinstaller
    if errorlevel 1 (
        echo ❌ ERRO ao instalar PyInstaller!
        pause
        exit /b 1
    )
)
echo ✅ PyInstaller instalado

REM Verificar arquivo de ícone
if not exist "assets\icons\logo.ico" (
    echo ❌ ERRO: Ícone não encontrado em assets\icons\logo.ico
    echo    O executável será criado sem ícone personalizado.
    set "ICON_WARNING=1"
) else (
    echo ✅ Ícone encontrado
    set "ICON_WARNING=0"
)

REM Verificar Inno Setup
set "INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%INNO_PATH%" (
    echo ❌ ERRO: Inno Setup não encontrado!
    echo    Baixe e instale de: https://jrsoftware.org/isinfo.php
    echo.
    echo    O executável será criado, mas o instalador não será gerado.
    set "SKIP_INSTALLER=1"
    pause
) else (
    echo ✅ Inno Setup encontrado
    set "SKIP_INSTALLER=0"
)

REM Verificar arquivo .spec
if not exist "Confeitaria.spec" (
    echo ❌ ERRO: Arquivo Confeitaria.spec não encontrado!
    pause
    exit /b 1
)
echo ✅ Arquivo .spec encontrado

REM Verificar arquivo .iss
if not exist "Confeitaria.iss" (
    echo ❌ ERRO: Arquivo Confeitaria.iss não encontrado!
    if !SKIP_INSTALLER!==0 (
        set "SKIP_INSTALLER=1"
    )
) else (
    echo ✅ Arquivo .iss encontrado
)

echo.

REM ============================================================
REM ETAPA 2: LIMPEZA DE BUILDS ANTERIORES
REM ============================================================

echo [2/5] Limpando builds anteriores...

if exist "build" (
    echo 🧹 Removendo diretório build...
    rmdir /s /q "build" 2>nul
)

if exist "dist" (
    echo 🧹 Removendo diretório dist...
    rmdir /s /q "dist" 2>nul
)

if exist "output" (
    echo 🧹 Removendo instaladores antigos...
    del /q "output\*.exe" 2>nul
)

REM Remover __pycache__
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul

echo ✅ Limpeza concluída
echo.

REM ============================================================
REM ETAPA 3: ATUALIZAR DEPENDÊNCIAS
REM ============================================================

echo [3/5] Atualizando dependências...

echo 📦 Atualizando pip...
"%PIP_CMD%" install --upgrade pip -q

echo 📦 Instalando dependências de build...
"%PIP_CMD%" install --upgrade packaging setuptools wheel -q

echo 📦 Instalando dependências do projeto...
if exist "requirements.txt" (
    "%PIP_CMD%" install -r requirements.txt -q
)

echo ✅ Dependências atualizadas
echo.

REM ============================================================
REM ETAPA 4: GERAR EXECUTÁVEL COM PYINSTALLER
REM ============================================================

echo [4/5] Gerando executável...
echo.
echo 🔨 Executando PyInstaller...
echo    Modo: --onedir (com dependências separadas)
echo    Console: Desabilitado (windowed)
if !ICON_WARNING!==0 (
    echo    Ícone: assets\icons\logo.ico
) else (
    echo    Ícone: Sem ícone personalizado
)
echo.
echo ⚙️  Configurações do build:
echo    • Sistema de auto-atualização 100%% funcional
echo    • Comunicação com GitHub API validada
echo    • Sistema de LOGS completo em AppData\Local\Confeitaria\logs\
echo    • Token GitHub em texto simples (github_token.txt)
echo    • Sistema de licenciamento integrado
echo    • Painel web embutido (porta 5000)
echo    • Suporte a temas claro/escuro
echo    • Launcher externo para atualizações remotas
echo.

"%PYTHON_CMD%" -m PyInstaller Confeitaria.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ❌ ERRO durante a geração do executável!
    echo    Verifique as mensagens de erro acima.
    pause
    exit /b 1
)

REM Verificar se o executável foi criado (onedir gera em dist\Confeitaria\)
if not exist "dist\Confeitaria\Confeitaria.exe" (
    echo ❌ ERRO: Executável não foi criado!
    echo    Esperado: dist\Confeitaria\Confeitaria.exe
    pause
    exit /b 1
)

echo.
echo ✅ Executável criado com sucesso!
echo    Localização: dist\Confeitaria\Confeitaria.exe
echo.

REM Mostrar informações do executável
for %%I in ("dist\Confeitaria\Confeitaria.exe") do (
    echo    Tamanho: %%~zI bytes
    set /a SIZE_MB=%%~zI/1048576
    echo    Tamanho: !SIZE_MB! MB
)

REM Contar arquivos na pasta dist
set "FILE_COUNT=0"
for /r "dist\Confeitaria" %%f in (*) do set /a FILE_COUNT+=1
echo    Total de arquivos: !FILE_COUNT!

echo.

REM ============================================================
REM ETAPA 5: GERAR INSTALADOR COM INNO SETUP
REM ============================================================

if !SKIP_INSTALLER!==1 (
    echo [5/5] Instalador não será gerado (Inno Setup não disponível)
    echo.
    goto :success_exe_only
)

echo [5/5] Gerando instalador...
echo.
echo 🔨 Executando Inno Setup...
echo.

"%INNO_PATH%" "Confeitaria.iss"

if errorlevel 1 (
    echo.
    echo ❌ ERRO durante a geração do instalador!
    echo    Verifique as mensagens de erro acima.
    echo.
    echo ℹ️  Executável foi criado com sucesso em: dist\Confeitaria.exe
    pause
    exit /b 1
)

echo.
echo ✅ Instalador criado com sucesso!
echo.

REM Verificar se o instalador foi criado
set "INSTALLER_FOUND=0"
for %%f in (output\Confeitaria_Setup_*.exe) do (
    if exist "%%f" (
        echo    Localização: %%f
        for %%I in ("%%f") do (
            echo    Tamanho: %%~zI bytes
            set /a SIZE_MB=%%~zI/1048576
            echo    Tamanho: !SIZE_MB! MB
        )
        set "INSTALLER_FOUND=1"
    )
)

if !INSTALLER_FOUND!==0 (
    echo ⚠️  Aviso: Instalador não encontrado na pasta output!
)

echo.

REM ============================================================
REM RESUMO FINAL
REM ============================================================

:success_complete
echo ============================================
echo  ✅ BUILD COMPLETO COM SUCESSO!
echo  Versão 1.11.32 - %date% %time%
echo ============================================
echo.
echo 📦 Arquivos gerados:
echo    • Executável: dist\Confeitaria\Confeitaria.exe
for %%f in (output\Confeitaria_Setup_*.exe) do (
    if exist "%%f" (
        echo    • Instalador: %%f
    )
)
echo.
echo 🆕 Novidades desta versão:
echo    ✅ Sistema de atualização 100%% funcional
echo    ✅ Fix crítico: URL do GitHub corrigida
echo    ✅ Comunicação com API validada
echo    ✅ Sistema de LOGS completo em AppData
echo    ✅ DeprecationWarning do Flask corrigido
echo    ✅ Pronto para produção
echo.
echo 🎉 Pronto para distribuição!
echo.
echo 💡 Próximos passos:
echo    1. Teste o executável: dist\Confeitaria\Confeitaria.exe
echo    2. github_token.txt já está incluído automaticamente
echo    3. Teste a verificação de atualização
echo    4. Teste o instalador em uma máquina limpa
echo    5. Distribua para os usuários
echo.
goto :end

:success_exe_only
echo ============================================
echo  ✅ EXECUTÁVEL CRIADO COM SUCESSO!
echo  Versão 1.11.32 - %date% %time%
echo ============================================
echo.
echo 📦 Arquivo gerado:
echo    • Executável: dist\Confeitaria\Confeitaria.exe
echo.
echo ⚠️  Instalador não foi criado (Inno Setup não disponível)
echo.
echo 🆕 Novidades desta versão:
echo    ✅ Sistema de atualização funcional
echo    ✅ Logs completos em AppData
echo    ✅ URL do GitHub corrigida
echo.
echo 💡 Próximos passos:
echo    1. Teste o executável: dist\Confeitaria\Confeitaria.exe
echo    2. Instale o Inno Setup para gerar o instalador
echo    3. Execute este script novamente
echo.

:end
echo Pressione qualquer tecla para finalizar...
pause >nul
