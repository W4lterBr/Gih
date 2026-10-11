# Confeitaria Desktop (Tauri)

A interface nova da Confeitaria, no mesmo padrão do **Busca XML Desktop**: janela nativa
(Tauri 2 + WebView2 do Windows), interface React + TypeScript e a identidade visual DWM
(claro/escuro). Substituiu a interface PyQt6 da versão 1.x (código na tag `pyqt-final`).

As **regras de negócio continuam em Python**, na raiz do projeto (`../core/`), servidas pelo
motor `../servico_local.py` (rotas em `../api/`): reserva e baixa de estoque, lotes de pedido,
auditoria, migrações do banco, painel da cozinha. O banco é o mesmo da versão 1.x.

## Como rodar

Pré-requisitos (já instalados nesta máquina): Node 24, Rust (rustup, stable), Visual Studio
Build Tools com C++ e o Python do projeto (com os pacotes de `../requirements.txt`).

```powershell
npm install
npm run tauri dev     # app com recarga ao salvar; o Tauri inicia o motor (py servico_local.py)
```

Para desenvolver só a interface no navegador, com um motor iniciado à mão:

```powershell
# terminal 1 (raiz do projeto) — SEMPRE com uma cópia do banco
$env:CONFEITARIA_TOKEN="dev"; $env:CONFEITARIA_DB="C:\Temp\copia.db"; py servico_local.py --porta 51888
# terminal 2 (desktop\)
$env:VITE_MOTOR_PORTA="51888"; $env:VITE_MOTOR_TOKEN="dev"; npm run dev
```

> Em desenvolvimento o motor usa o banco configurado em `../data/config.yaml`. Para testar,
> defina `CONFEITARIA_DB` com uma cópia (o Tauri passa as variáveis de ambiente para o motor).

## Arquitetura

```
┌──────────────────────────── Confeitaria Desktop ─────────────────────────────┐
│ src/ (React + TS)                 src-tauri/ (Rust)                          │
│ telas, diálogos, paleta Ctrl+K ─▶ motor_info (porta + token), abrir arquivo, │
│ fetch http://127.0.0.1:<porta>    mostrar na pasta, abrir URL, instância única│
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ HTTP local (token por sessão)
┌──────────────▼───────────────────────────────────────────────────────────────┐
│ servico_local.py + api/  ─ regras de core/ ─ SQLite (mesmo banco da v1.x)   │
│ tarefas: painel da cozinha (Flask :5000), reserva de estoque 1/h, backup auto │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Motor** (`src-tauri/src/motor.rs`): ao abrir, o Tauri inicia o motor escondido
  (`CREATE_NO_WINDOW`), numa porta livre de 127.0.0.1, com token aleatório. Instalado, usa
  `<instalação>\motor\confeitaria-motor.exe`; em desenvolvimento, o Python do projeto
  (`.venv`, senão o lançador `py`). Saída em `%LOCALAPPDATA%\Confeitaria\logs\servico_local.log`.
- **Proteções do motor:** só `127.0.0.1`, cabeçalho `X-Token` obrigatório, CORS só da janela,
  login exigido nas rotas, rotas de administrador conferem o perfil. Encerra quando a janela
  fecha (vigia o PID), sem interromper uma gravação.
- **Uma requisição por vez** no banco (trava no motor): as regras de estoque não intercalam.

## Telas

| Tela | O que tem |
|---|---|
| Início | entregas de hoje, pedidos por dia, mais pedidos, estoque baixo |
| Pedidos | período (hoje/amanhã/7 dias/todos/datas), busca, pagamento/etiqueta, painel lateral, ações em massa, etiquetas, relatório PDF/Excel |
| Produção | lista da cozinha editável em linha, importar pedidos do dia, estoque × encomendas, painel da cozinha |
| Pronta entrega / Produtos | estoque com esgotados e mínimos; cadastro com vários tamanhos |
| Clientes | cadastro, pedido rápido, histórico |
| Movimentação | entradas/saídas/produção/perdas, desfazer, exportar Excel |
| Relatórios | entregas do dia, fechamento por cliente, produção e estoque (PDF/Excel) |
| Configurações | empresa e logo, usuários, banco e backup, painel da cozinha, aparência, minha conta |

Atalhos: `Ctrl K` comandos · `Ctrl N` novo pedido · `Ctrl 1`–`8` telas · `/` buscar ·
`F5` recarregar · `Del` excluir marcados · `Ctrl Enter` salvar pedido.

## Licença DWM (faturas)

Implementa a "Documentação de Faturas" da DWM do jeito que ela prescreve para **apps
instalados no cliente**: sem a credencial HMAC da API de Assinaturas (a documentação proíbe —
o segredo seria extraível e daria acesso às assinaturas de todos os clientes do produto). O app
usa o endpoint de licença do cliente (`/api/licenca-cliente/status`, contrato em
`Site DWM/DWM-SISTEMA/API_LICENCA_CLIENTE.md`, o mesmo do Busca NF-e): a única credencial é o
**token de licença daquele cliente** (`clients.license_token`), que só enxerga as faturas dele.

| Situação na DWM | No app |
|---|---|
| sem token ativado | funciona normalmente; faixa discreta "Ativar" (para administradores) |
| `liberado` | normal |
| `tolerancia` (vencida há até 7 dias) | normal + faixa com a fatura, "Pagar fatura" e "Já paguei" |
| `bloqueado` (vencida há mais de 7 dias, ou cliente inativo) | **somente leitura**: vê, imprime, exporta e faz backup; criar/editar/excluir é recusado pelo motor (HTTP 423) e pelo painel da cozinha |
| sem internet | vale a última confirmação por até 7 dias; depois exige uma consulta com sucesso |

Lógica em `../core/licenca.py` (motor), rotas em `../api/licenca.py`, tela em
`src/views/LicencaView.tsx` e faixa em `src/licenca.tsx`. Proteções:

- token só no cabeçalho `X-License-Token`, só por HTTPS com certificado verificado; conferido
  com a DWM **antes** de ser salvo; guardado com DPAPI (`licenca.dat` na pasta de dados);
  nunca vai para log (só os 4 últimos caracteres) nem volta inteiro para a interface;
- cache do último status também com DPAPI (adulterar o arquivo não libera; apagar o arquivo
  com a licença já ativada pede reativação em vez de voltar ao modo "sem token");
- relógio do Windows atrasado não estende a validade; a hora da confirmação é a do servidor;
- consulta a cada 4 h, "Já paguei" no máximo a cada 30 s, para por 15 min após um 429; um 401
  isolado não trava (só repetido por 24 h);
- não dá para remover o token com a licença bloqueada; só administrador ativa/troca/remove.

**Do lado da DWM:** cada confeitaria precisa ter o `license_token` gerado no cadastro de
cliente (o mesmo do Busca). O status é calculado pelas faturas do **cliente** — uma fatura
vencida de outro produto do mesmo cliente também bloqueia aqui.

Testes: `py ..\tests\test_licenca.py` (20 casos, servidor falso) e
`py ..\tests\test_licenca_motor.py C:\Temp\copia.db` (somente leitura de ponta a ponta).

## Testes

```powershell
py ..\tests\test_servico_local.py C:\Temp\copia.db   # percorre todas as rotas do motor
npx tsc --noEmit                                      # tipos da interface
```

## Instalador

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gerar-instalador.ps1             # motor + instalador
powershell -ExecutionPolicy Bypass -File scripts\gerar-instalador.ps1 -PularMotor # só o app
```

Saída em `Output\` (instalador NSIS por usuário, sem admin). O motor vem de `../motor.spec`
(PyInstaller) e é copiado para `src-tauri\motor\` (fora do git). Sem atualizador automático:
cada versão nova é um instalador novo.

## Diferenças em relação à versão 1.x (PyQt)

- Corrigido: editar pedido não perde mais a etiqueta; edição de pedido e de lote é atômica;
  busca inclui a etiqueta; "Todos" não tem limite de datas; segunda-feira é avisada no
  diálogo (sem perder o que foi digitado); credenciais só são lembradas depois de conferidas;
  editar na Pronta entrega salva (antes sempre falhava); "Importar pedidos" inclui
  "Pagamento na Retirada"; filtro de etiqueta do Fechamento funciona; Relatórios acessível.
- Backup usa cópia consistente do SQLite; restaurar fecha a conexão antes e reabre sem
  reiniciar; backup automático respeita a configuração; logo vai para a pasta de dados.
- Não trazidos (decisão pendente com o responsável): backup em nuvem via repositório GitHub
  compartilhado entre clientes e "Configurar Rede Local" (ativava Convidado sem senha).
- Os 5 temas coloridos viraram claro/escuro com a identidade DWM, como no Busca XML.
