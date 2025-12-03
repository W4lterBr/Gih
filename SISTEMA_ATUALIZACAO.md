# 🔄 Sistema de Atualização Remota

## 📋 Visão Geral

O sistema de confeitaria agora possui atualização automática via GitHub, permitindo que os clientes recebam novas funcionalidades sem precisar reinstalar o software completo.

## 🔧 Configuração

### Repositório GitHub
- **Repositório:** `W4lterBr/Gih`
- **Branch:** `main`
- **URL:** `git@github.com:W4lterBr/Gih.git`

### Token de Acesso (Repositório Privado)
Se o repositório for privado, crie um arquivo `github_token.txt` na raiz com o token de acesso:
```
ghp_seu_token_aqui
```

## 📦 Como Funciona

### 1. Verificação de Atualizações
- O sistema verifica o arquivo `version.json` no GitHub
- Compara a versão local com a versão remota
- Exibe changelog com as novidades

### 2. Download e Instalação
- Baixa apenas os arquivos modificados (~500KB)
- **Arquivos atualizados:**
  - `Confeitaria.py` (código principal)
  - `core/` (lógica do sistema)
  - `ui/` (interface PyQt6)
  - `src/` (módulos auxiliares)
  - `assets/` (ícones e recursos)
  - `web/` (painel web HTML)
  - `version.json` (controle de versão)

- **Arquivos preservados:**
  - `confeitaria.db` (banco de dados)
  - `config.yaml` (configurações)
  - `github_token.txt` (token de acesso)
  - `logs/` (histórico de logs)
  - `backups/` (backups do banco)

### 3. Aplicação da Atualização
1. Faz backup dos arquivos atuais
2. Extrai novos arquivos do GitHub
3. Limpa cache do PyQt6
4. Solicita reinício do sistema

## 🎯 Para o Usuário Final

### Como Verificar Atualizações
1. Abra o sistema
2. Vá em **Configurações**
3. Role até a seção **"🔄 Atualização do Sistema"**
4. Clique em **"🔍 Verificar Atualizações"**

### Se Houver Atualização
1. Uma janela mostrará as novidades (changelog)
2. Clique em **"Sim"** para atualizar
3. Aguarde o download (~500KB)
4. Clique em **"Sim"** para reiniciar o sistema
5. Pronto! Sistema atualizado

## 💻 Para o Desenvolvedor

### Como Publicar uma Atualização

1. **Faça as alterações no código**
   ```bash
   # Edite os arquivos necessários
   # Teste localmente
   ```

2. **Atualize o version.json**
   ```json
   {
     "version": "1.12.1",  // ← Incrementar versão
     "release_date": "2025-12-03",
     "changelog": [
       "✅ Nova funcionalidade X",
       "🐛 Correção do bug Y",
       "🎨 Melhoria visual Z"
     ]
   }
   ```

3. **Atualize CURRENT_VERSION no updater.py**
   ```python
   CURRENT_VERSION = "1.12.1"  # ← Mesma versão do version.json
   ```

4. **Faça commit e push**
   ```bash
   git add .
   git commit -m "v1.12.1 - Nova funcionalidade X"
   git push origin main
   ```

5. **Pronto!** Todos os clientes poderão atualizar

### Estrutura do version.json
```json
{
  "version": "X.Y.Z",           // Versão semântica
  "release_date": "YYYY-MM-DD", // Data de lançamento
  "changelog": [                 // Lista de mudanças
    "✅ Novidade 1",
    "🐛 Correção 2",
    "🎨 Melhoria 3"
  ],
  "required_version": "1.11.0",  // Versão mínima para atualizar
  "download_url": "https://...", // URL do ZIP
  "min_python_version": "3.10"   // Python mínimo requerido
}
```

## 🔐 Segurança

### Token GitHub
- O token é armazenado localmente em `github_token.txt`
- Nunca é transmitido para servidores externos
- Apenas usado para autenticar com GitHub
- Para repositórios privados, gere um token com permissão `repo`

### Backup Automático
- Antes de cada atualização, o sistema cria backup
- Localização: pasta `_backup_[timestamp]` na raiz
- Permite rollback manual se necessário

## 🚨 Troubleshooting

### "Erro ao verificar atualizações"
- Verifique conexão com internet
- Verifique se o token está correto (se repo privado)
- Verifique logs em `AppData\Local\Confeitaria\logs\`

### "Falha ao aplicar atualização"
- Feche todos os programas que possam estar usando arquivos
- Execute o programa como administrador
- Verifique espaço em disco disponível
- Restaure backup manual se necessário

### Atualização não aparece
- Aguarde alguns minutos (cache do GitHub)
- Force refresh: feche e reabra o programa
- Verifique se `version.json` está correto no GitHub

## 📊 Versão Atual

**v1.12.0** - Sistema com:
- ✅ Dashboard completo
- ✅ 5 temas (Escuro, Claro, Rosa, Roxo, Azul)
- ✅ Login com memorização
- ✅ Preços em reais (R$)
- ✅ Configurações de empresa (nome + logo)
- ✅ Sistema de atualização remota

## 🔗 Links Úteis

- **Repositório:** https://github.com/W4lterBr/Gih
- **Issues:** https://github.com/W4lterBr/Gih/issues
- **Releases:** https://github.com/W4lterBr/Gih/releases
