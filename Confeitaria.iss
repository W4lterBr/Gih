#define MyAppName      "Confeitaria"
#define MyAppVersion   "1.15.0"
#define MyAppPublisher "DWM Systems Developer"
#define MyAppExeName   "Confeitaria.exe"
#define MyAppURL       ""  ; Pode adicionar um site aqui se desejar
#define MyAppAssoc     "confeitariadb"  ; Extensão para associação de arquivos (opcional)
#define MyAppDataDir   "{userappdata}\Confeitaria"

; CHANGELOG v1.15.0 (2026-09-06)
; ================================
; 🛠️ CORREÇÕES DE INTEGRIDADE DE DADOS
; ✅ Painel da Cozinha: editar quantidade de pedido agora ajusta o estoque corretamente
; ✅ Pedidos com múltiplos produtos ganham um ID de lote único (evita agrupar/excluir lotes errados)
; ✅ Reparo e restauração de banco atualizam o schema automaticamente
; ✅ Corrigida corrupção do campo "Tamanho" ao editar itens de Produção
; ✅ Editar data de entrega de um pedido futuro para hoje reserva o estoque na hora
; ✅ Criação de pedido com múltiplos produtos: desfaz tudo automaticamente se algum item falhar
; ✅ Corrigida condição de corrida que podia deixar estoque negativo em Movimentação
; ✅ Exclusão de usuário bloqueada para o próprio usuário logado e para o último administrador
; ✅ Edição de produto agora registra a mudança de estoque em Movimentação
; ✅ Excluir cliente com pedidos vinculados avisa em vez de falhar em silêncio
; ✅ Importar pedidos para Produção pede confirmação antes de substituir a lista atual
; ✅ Nomes de usuário e etiquetas duplicados (maiúsc./minúsc.) tratados corretamente
; 🖱️ SELEÇÃO MÚLTIPLA
; ✅ Excluir com vários itens selecionados agora remove todos (Produtos, Clientes, Movimentação, Produção)
;
; CHANGELOG v1.14.0 (2026-09-06)
; ================================
; 🔒 SEGURANÇA
; ✅ Painel da Cozinha (acesso pela rede) agora exige PIN de acesso
; ✅ Login: bloqueio automático após tentativas incorretas repetidas
; ✅ Login: senha "lembrada" agora protegida com criptografia do Windows (DPAPI)
; ✅ Recuperação de banco corrompido verifica integridade antes de substituir o original
; ⚡ LOGIN AUTOMÁTICO
; ✅ Com "Lembrar credenciais" marcado, entra direto sem precisar digitar de novo
; ✅ Segure Shift ao abrir o app para trocar de usuário
; 📦 ESTOQUE
; ✅ NOVO: tela de Movimentação - entradas, saídas, produção e perdas/quebras
; ✅ Registro de perdas de estoque com resumo financeiro do impacto
; ✅ Histórico completo, filtros por tipo/período e exportação para Excel
; ✅ Pronta Entrega: produtos esgotados ficam marcados em vez de desaparecer da lista
; 🖥️ INTERFACE
; ✅ Correção: janela desproporcional em telas com resoluções diferentes/múltiplos monitores
;
; CHANGELOG v1.13.0 (2026-03-17)
; ================================
; 🎨 PERSONALIZAÇÃO COMPLETA
; ✅ Logo customizada em TODAS as telas (Login, Header, Ícone)
; ✅ Correção: Logo não fica mais cortada no header
; ✅ Suporte a logos retangulares e quadradas (até 200x64px)
; ✅ Ícone do executável/instalador atualizado automaticamente
; ✅ Tamanho dinâmico do header com altura de 64px
; ✅ Alinhamento vertical perfeito da logo
;
; CHANGELOG v1.11.27 (2025-11-17)
; ================================
; 🔄 ATUALIZAÇÃO REMOTA FUNCIONAL
; ✅ Sistema substitui 100% do código, interface e recursos
;    - Atualiza: .py, core/, ui/, src/, assets/, web/
;    - Preserva: confeitaria.db, config.yaml, token, logs, backups
; 🧹 Limpeza automática de cache PyQt6 após atualização
;    - Força recarregamento de módulos atualizados
;    - Garante que interface sempre aparece corretamente
; 🔑 Status de licença no rodapé
;    - ✅ Em dia (verde) - Token válido
;    - ⏳ Pendente (amarelo) - Token não configurado
;    - ❌ Inadimplente (vermelho) - Token sem permissão
;    - 🌐 Sem internet (cinza) - Erro de conexão
; 📦 Token GitHub incluído automaticamente no instalador
;    - Cliente instala → licença ativa imediatamente
;    - Atualizações preservam token automaticamente
; 🚀 Workflow otimizado para distribuição
;    - Gera instalador 1x → Clientes atualizam infinitamente
;    - Desenvolvedor: git push → Disponível para todos
;    - Clientes: Configurações → Verificar Atualizações → 1 clique
;    - Downloads de ~500KB vs ~200MB de instalador completo
; 
; CHANGELOG v1.11.7 (2025-11-14)
; ===============================
; ✅ Nova funcionalidade: Restauração de Backup
;    - Botão "Restaurar Backup" nas configurações de banco de dados
;    - Seleciona arquivo ZIP de backup para restaurar
;    - Cria backup de segurança automático antes de restaurar
;    - Valida integridade do banco com PRAGMA integrity_check
;    - Restaura .db, .db-wal, .db-shm e config.yaml
;    - Mensagens claras de sucesso/erro com instruções
; ✅ Melhoria: Backup na Nuvem Manual
;    - Botão "Fazer Backup na Nuvem Agora" (verde)
;    - Envia backup para GitHub sem diálogos interruptivos
;    - Mostra apenas toast "Backup realizado com sucesso"
;    - Executa em background via QTimer (sem travamento de UI)
; ✅ Melhoria: Backups Completos
;    - Todos os backups incluem .db, .db-wal, .db-shm e config.yaml
;    - Aplica-se a: backup manual, backup automático e backup na nuvem
;    - Garante recuperação completa do estado do sistema
; ✅ Agregação visual de pedidos em lote
;    - Pedidos em lote (marcados com LOTE:) aparecem como única linha
;    - Mostra "Pedidos em lote" como produto e "Lote" como tamanho
;    - Quantidade é a soma de todos os itens do lote
; ✅ Exclusão completa de pedidos em lote
;    - Ao excluir pedido em lote, remove TODOS os itens do lote
;    - Devolve estoque de todos os produtos do lote
; ✅ Calendários legíveis no tema claro
;    - Fundo branco com texto escuro em todos os calendários
;    - Cabeçalhos e botões com cores claras visíveis
; ✅ Importação de pedidos por data selecionada
;    - Importa pedidos da data escolhida no calendário
;    - Inclui pedidos com status "Pago" além dos pendentes

; Diretórios do projeto - usando o diretório onde o .iss está localizado
#define ProjectRoot    ExtractFilePath(SourcePath)
#define DistDir       ProjectRoot + "dist"
#define AssetsDir     ProjectRoot + "assets"
#define IconsDir      AssetsDir + "\icons"
#define ImagesDir     AssetsDir + "\images"

; Caminhos dos executáveis
#define ExeInFolder   DistDir + "\Confeitaria\" + MyAppExeName
#define ExeOneFile    DistDir + "\" + MyAppExeName

; Verificação em tempo de compilação - valida apenas durante o build
#if FileExists(ExeOneFile)
  #pragma message "Build detectado: PyInstaller --onefile em " + ExeOneFile
#elif FileExists(ExeInFolder)
  #pragma message "Build detectado: PyInstaller --onedir em " + ExeInFolder
#else
  #error "ERRO: Nenhum executável encontrado! Execute build_complete.bat primeiro."
#endif

[Setup]
AppId={{A1B2C3D4-5E6F-47A8-9B0C-D1E2F3A4B5C6}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Mostrar aviso se versão antiga encontrada
AppMutex=ConfeitariaAppMutex2023
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Confeitaria_Setup_{#MyAppVersion}
SetupIconFile={#IconsDir}\logo.ico
UninstallDisplayIcon={app}\assets\icons\logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ShowLanguageDialog=auto
CloseApplications=force
RestartApplications=no
AlwaysShowDirOnReadyPage=yes
UsedUserAreasWarning=no

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
portuguese.BeveledLabel=Português
english.BeveledLabel=English

[CustomMessages]
portuguese.LaunchProgram=Iniciar o %1
english.LaunchProgram=Launch %1

portuguese.AssocFileExtension=Associar arquivos %1 com o %2
english.AssocFileExtension=Associate %1 files with %2

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "associatedb"; Description: "{cm:AssocFileExtension,'.cdb',{#MyAppName}}"; GroupDescription: "Associação de arquivos:"

[Dirs]
; Diretório principal do app
Name: "{app}"
; Diretório de dados do usuário
Name: "{#MyAppDataDir}"; Permissions: users-full
Name: "{#MyAppDataDir}\data"; Permissions: users-full
Name: "{#MyAppDataDir}\logs"; Permissions: users-full
Name: "{#MyAppDataDir}\backups"; Permissions: users-full

[Files]
; Executável principal - tenta ambos os tipos de build (apenas um existirá)
Source: "{#ExeOneFile}"; DestDir: "{app}"; Flags: ignoreversion signonce skipifsourcedoesntexist
Source: "{#ExeInFolder}"; DestDir: "{app}"; Flags: ignoreversion signonce skipifsourcedoesntexist

; Arquivos do build onedir (se existir)
Source: "{#DistDir}\Confeitaria\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Recursos visuais (sempre incluir)
Source: "{#IconsDir}\*"; DestDir: "{app}\assets\icons"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "{#ImagesDir}\*"; DestDir: "{app}\assets\images"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

; Painel Web (HTML/CSS/JS)
Source: "{#ProjectRoot}web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; ========================================
; CRÍTICO: Código Python EXTERNO (Atualizável + Protegido)
; ========================================
; Confeitaria.py DEVE ficar FORA do .exe para ser atualizado remotamente!
; O launcher.py (dentro do .exe) carrega o Confeitaria.pyc (bytecode compilado)
; .pyc = mais rápido + dificulta engenharia reversa
Source: "{#ProjectRoot}Confeitaria.py"; DestDir: "{app}"; Flags: ignoreversion confirmoverwrite

; ========================================
; Arquivos de Configuração
; ========================================
Source: "{#ProjectRoot}version.json"; DestDir: "{app}"; Flags: ignoreversion confirmoverwrite

; Banco de dados inicial (apenas se não existir)
Source: "{#ProjectRoot}confeitaria.db"; DestDir: "{#MyAppDataDir}\data"; Flags: onlyifdoesntexist skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icons\logo.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icons\logo.ico"; Tasks: desktopicon

[Registry]
; Registrar protocolo customizado (confeitaria://)
Root: HKA; Subkey: "Software\Classes\{#MyAppAssoc}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppName} Database"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyAppAssoc}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\{#MyAppAssoc}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; Configurações do app
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "DataPath"; ValueData: "{#MyAppDataDir}"

[Run]
; Executar o app após a instalação
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent skipifdoesntexist

[UninstallDelete]
; Limpar arquivos do programa
Type: filesandordirs; Name: "{app}"
; Não remover dados do usuário por padrão
;Type: filesandordirs; Name: "{#MyAppDataDir}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;

  // Verificar se uma instância está rodando
  if CheckForMutexes('ConfeitariaAppMutex2023') then
  begin
    MsgBox('Uma instância do {#MyAppName} está em execução.' + #13#10 +
           'Por favor, feche o programa antes de continuar.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  
  // Verificar se uma instância está rodando antes de desinstalar
  if CheckForMutexes('ConfeitariaAppMutex2023') then
  begin
    MsgBox('Uma instância do {#MyAppName} está em execução.' + #13#10 +
           'Por favor, feche o programa antes de desinstalar.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Criar arquivo de configuração inicial se necessário
    SaveStringToFile(ExpandConstant('{#MyAppDataDir}\config.ini'),
      '; Configuração inicial do {#MyAppName}' + #13#10 +
      'DataPath=' + ExpandConstant('{#MyAppDataDir}\data') + #13#10 +
      'LogPath=' + ExpandConstant('{#MyAppDataDir}\logs') + #13#10 +
      'Version={#MyAppVersion}' + #13#10,
      False);
  end;
end;

[InstallDelete]
; Limpar arquivos antigos antes da instalação
Type: files; Name: "{app}\*.old"
Type: files; Name: "{app}\*.bak"
Type: files; Name: "{app}\*.log"
