# Confeitaria — Gestão de Pedidos

Sistema de pedidos, produção e estoque para confeitarias. Versão 2.0: interface desktop
no padrão do **Busca XML Desktop** (Tauri + React) com as regras de negócio em Python.
Um mesmo código atende vários clientes (Gih, Marilia…): nome e logo vêm da tabela
`company` (Configurações → Empresa), nunca fixos no código.

## Estrutura

```
app/
├── desktop/              Interface (Tauri 2 + React/TypeScript) — ver desktop/README.md
├── servico_local.py      Motor: serviço HTTP local que a interface inicia em segundo plano
├── api/                  Rotas do motor (pedidos, produção, estoque, relatórios, banco, licença…)
├── core/                 Regras e dados: banco SQLite, migrações, estoque, auditoria,
│                         configuração, licença DWM, painel da cozinha (web_server.py)
├── web/                  Painel da cozinha (celular/tablet na mesma rede, porta 5000)
├── assets/icons/         Logo padrão (neutro);  assets/clientes/<nome>/ logos de cada cliente
├── tests/                Testes do motor e da licença (sempre com cópia de banco)
├── tools/                populate_database.py (gera banco de demonstração)
├── motor.spec            Empacotamento do motor (PyInstaller) para o instalador
├── requirements.txt      Dependências do motor
└── version.json          Versão e novidades
```

Fora do git (locais): `data/` (banco e config.yaml em desenvolvimento), `backups/`,
`Backup_Clientes/`, `logs/`, `build/`, `dist/`.

## Desenvolvimento

```powershell
py -m pip install -r requirements.txt
cd desktop
npm install
npm run tauri dev
```

Detalhes da interface, da arquitetura e da licença DWM em [desktop/README.md](desktop/README.md).

> Teste sempre com uma **cópia** do banco: defina `CONFEITARIA_DB=C:\Temp\copia.db` (e,
> para não tocar no config.yaml real, `CONFEITARIA_DATA_DIR=C:\Temp\dados`).

## Testes

```powershell
py tests\test_servico_local.py C:\Temp\copia.db    # todas as rotas do motor
py tests\test_licenca.py                           # licença DWM (servidor falso)
py tests\test_licenca_motor.py C:\Temp\copia.db    # somente leitura de ponta a ponta
```

## Instalador

```powershell
cd desktop
powershell -ExecutionPolicy Bypass -File scripts\gerar-instalador.ps1
```

Gera `desktop\Output\Confeitaria_<versão>_x64-setup.exe` (por usuário, sem admin). Não há
atualizador automático: cada versão nova é um instalador novo. Instalado, o app usa a mesma
pasta de dados da versão 1.x (`%LOCALAPPDATA%\Confeitaria`), então atualizar não perde dados.

## Versão anterior

A interface PyQt (versão 1.x) foi removida; o código está na tag `pyqt-final` do git.
