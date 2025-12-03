# 🚀 Guia Rápido - Sistema de Atualização

## ⚡ Para Usuários

### Como Atualizar o Sistema

1. **Abra o sistema** e faça login
2. Clique em **"Configurações"** (último item do menu)
3. Role até **"🔄 Atualização do Sistema"**
4. Clique em **"🔍 Verificar Atualizações"**
5. Se houver atualização:
   - Leia as novidades
   - Clique em **"Sim"** para atualizar
   - Aguarde o download (~500KB)
   - Clique em **"Sim"** para reiniciar
6. **Pronto!** Sistema atualizado

### Observações
- ✅ Seus dados NÃO serão apagados
- ✅ Configurações serão mantidas
- ✅ Backups serão preservados
- ⚠️ Certifique-se de ter internet ativa

---

## 💻 Para Desenvolvedores

### Como Publicar uma Atualização

#### 1️⃣ Prepare o Código
```bash
# Faça as alterações necessárias
# Teste localmente: .venv\Scripts\python.exe Confeitaria.py
```

#### 2️⃣ Atualize a Versão

**Arquivo: `version.json`**
```json
{
  "version": "1.12.1",  // ← Incrementar aqui
  "release_date": "2025-12-03",
  "changelog": [
    "✅ Sua nova funcionalidade",
    "🐛 Correção de bug",
    "🎨 Melhoria visual"
  ]
}
```

**Arquivo: `core/updater.py`** (linha ~23)
```python
CURRENT_VERSION = "1.12.1"  // ← Mesmo valor do version.json
```

#### 3️⃣ Commit e Push
```bash
git add .
git commit -m "v1.12.1 - Descrição da atualização"
git push origin main
```

#### 4️⃣ Pronto!
- Todos os clientes verão a atualização disponível
- Download automático de ~500KB
- Instalação em 1 clique

---

## 🔧 Configuração Inicial (Primeira vez)

### Para Repositório Privado

1. **Gere um token no GitHub:**
   - Acesse: https://github.com/settings/tokens
   - Clique em "Generate new token" → "Classic"
   - Marque a permissão: `repo` (Full control)
   - Clique em "Generate token"
   - **Copie o token** (ghp_...)

2. **Configure o token:**
   - Abra o arquivo `github_token.txt`
   - Cole o token
   - Salve e feche

3. **Teste a conexão:**
   ```bash
   .venv\Scripts\python.exe test_updater.py
   ```

### Para Repositório Público
- Não precisa de token
- Sistema funciona automaticamente
- Apenas certifique-se que o repositório está público

---

## 🧪 Testando o Sistema

### Testar Localmente
```bash
# Ativa o ambiente virtual
.venv\Scripts\activate

# Executa os testes
python test_updater.py
```

**Saída esperada:**
```
🔧 CONFIGURAÇÃO DO SISTEMA
======================================================================
Versão atual:     1.12.0
Repositório:      W4lterBr/Gih
Branch:           main
Token GitHub:     ✅ Configurado
======================================================================

🔐 STATUS DA LICENÇA
======================================================================
Status: ✅ Licença em dia
======================================================================

🔄 VERIFICAÇÃO DE ATUALIZAÇÕES
======================================================================
✅ Sistema está atualizado!
   Versão: 1.12.0
======================================================================
```

---

## 🔄 Fluxo Completo de Atualização

```
┌─────────────────────────────────────────────────────────┐
│  1. DESENVOLVEDOR                                       │
│     • Faz alterações no código                         │
│     • Atualiza version.json (v1.12.1)                  │
│     • Atualiza core/updater.py (CURRENT_VERSION)       │
│     • git commit + push                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  2. GITHUB                                              │
│     • Recebe o push                                     │
│     • Atualiza repositório W4lterBr/Gih                │
│     • version.json disponível                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  3. CLIENTE                                             │
│     • Abre Configurações                                │
│     • Clica "Verificar Atualizações"                   │
│     • Sistema consulta GitHub                           │
│     • Compara versão local (1.12.0) vs remota (1.12.1)│
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  4. DOWNLOAD                                            │
│     • Baixa ZIP do repositório (~500KB)                │
│     • Faz backup dos arquivos atuais                   │
│     • Extrai arquivos novos                             │
│     • Preserva banco de dados e configs                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  5. INSTALAÇÃO                                          │
│     • Limpa cache do PyQt6                             │
│     • Substitui código antigo pelo novo                 │
│     • Mantém dados do usuário                           │
│     • Solicita reinício                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  6. SISTEMA ATUALIZADO ✅                               │
│     • Cliente reinicia o programa                       │
│     • Nova versão carregada (1.12.1)                   │
│     • Todas as novas funcionalidades disponíveis       │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 Checklist de Atualização

### Antes de Publicar
- [ ] Código testado localmente
- [ ] `version.json` atualizado
- [ ] `core/updater.py` CURRENT_VERSION atualizado
- [ ] Changelog preenchido com mudanças
- [ ] Sem erros de sintaxe (pylint/flake8)
- [ ] Banco de dados compatível (sem breaking changes)

### Ao Publicar
- [ ] `git add .`
- [ ] `git commit -m "vX.Y.Z - Descrição"`
- [ ] `git push origin main`
- [ ] Verificar no GitHub se push foi bem-sucedido

### Após Publicar
- [ ] Testar atualização em máquina de teste
- [ ] Avisar usuários sobre nova versão
- [ ] Documentar issues conhecidas (se houver)

---

## ❓ FAQ

**P: Quanto tempo demora a atualização?**
R: ~30 segundos com internet boa (download de ~500KB)

**P: Meus dados serão perdidos?**
R: Não! Banco de dados, configurações e backups são preservados

**P: E se der erro na atualização?**
R: Um backup automático é criado antes. Pode restaurar manualmente

**P: Preciso estar logado como admin?**
R: Não, funciona com usuário comum

**P: Funciona sem internet?**
R: Não, precisa de conexão para verificar e baixar

**P: Posso cancelar durante o download?**
R: Não recomendado. Aguarde a conclusão (é rápido)

---

## 🆘 Suporte

- **Issues:** https://github.com/W4lterBr/Gih/issues
- **Logs:** `%LOCALAPPDATA%\Confeitaria\logs\`
- **Backup manual:** Restaure da pasta `_backup_[timestamp]`
