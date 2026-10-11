# 📦 GUIA DE DISTRIBUIÇÃO - Sistema Confeitaria v1.12.1

## 🎯 **Objetivo**
Este guia explica como gerar o instalador do sistema com o banco de dados incluído para distribuição em outros computadores.

---

## ✅ **Pré-requisitos**

### 1. **Banco de Dados Preparado**
   ```bash
   # Verifique se existe
   dir confeitaria.db
   
   # Se não existir, crie com dados de exemplo:
   python populate_database.py
   ```

### 2. **Dependências Instaladas**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

### 3. **Inno Setup Instalado**
   - Baixe: https://jrsoftware.org/isinfo.php
   - Instale em: `C:\Program Files (x86)\Inno Setup 6\`

---

## 🚀 **Passos para Gerar o Instalador**

### **Passo 1: Verificar Preparação**
```bash
prepare_distribution.bat
```
Este script verifica:
- ✅ Banco de dados existe
- ✅ Tamanho do banco
- ✅ Quantidade de registros
- ✅ Arquivos necessários

### **Passo 2: Gerar Executável e Instalador**
```bash
build.bat
```
Este script:
1. ✅ Verifica Python e PyInstaller
2. ✅ Limpa builds anteriores
3. ✅ Compila com PyInstaller (usando Confeitaria.spec)
4. ✅ **Inclui o banco de dados confeitaria.db**
5. ✅ Gera instalador com Inno Setup
6. ✅ Cria: `output\Confeitaria_Setup_1.12.1.exe`

### **Passo 3: Testar o Instalador**
1. Copie `output\Confeitaria_Setup_1.12.1.exe` para outro local
2. Execute o instalador
3. Verifique se o sistema abre com os dados

---

## 📁 **O que é Incluído no Instalador?**

### **Código e Módulos**
```
✅ Confeitaria.py          # Código principal
✅ launcher.py             # Inicializador
✅ core/                   # Lógica de negócio
✅ ui/                     # Interface gráfica
✅ web/                    # Painel web
✅ data/                   # Configurações
✅ assets/                 # Ícones e recursos
```

### **Banco de Dados** 🗄️
```
✅ confeitaria.db          # Banco populado com:
   - 40 Clientes
   - 40 Produtos com preços
   - 100 Pedidos (últimos 12 meses)
   - R$ 14.965,90 em vendas
```

### **Configurações**
```
✅ version.json            # Versão 1.12.1
✅ data/config.yaml        # Configurações base
```

---

## 🖥️ **Instalação em Outro Computador**

### **O que acontece na instalação:**
1. Instalador copia todos os arquivos para: `C:\Users\<Usuario>\AppData\Local\Confeitaria\`
2. **Banco de dados é copiado automaticamente** ✅
3. Cria atalho no Menu Iniciar
4. Cria atalho na Área de Trabalho (opcional)
5. Sistema está pronto para uso!

### **Primeiro Login:**
```
Usuário: admin
Senha: admin
```
⚠️ **Importante:** Alterar senha após primeiro acesso!

---

## 🔄 **Atualizar Banco em Instalações Existentes**

Se você já distribuiu o sistema e quer atualizar apenas o banco de dados:

### **Opção 1: Substituição Manual**
1. Localize o banco no outro PC:
   ```
   %LOCALAPPDATA%\Confeitaria\confeitaria.db
   ```
2. Substitua pelo novo `confeitaria.db`

### **Opção 2: Backup e Restauração**
1. Faça backup do banco atualizado (ZIP)
2. No outro PC: Configurações → Banco de Dados → Restaurar Backup
3. Selecione o arquivo ZIP

---

## 📊 **Verificar Dados Após Instalação**

No sistema instalado, vá para:
- **Dashboard**: Ver estatísticas gerais
- **Clientes**: Listar 40 clientes
- **Produtos**: Ver 40 produtos com preços
- **Pedidos**: Consultar 100 pedidos

---

## 🛠️ **Solução de Problemas**

### **"Banco de dados não encontrado"**
```bash
# Verifique se existe antes de compilar
dir confeitaria.db

# Se não existir, crie:
python populate_database.py
```

### **"PyInstaller não encontrado"**
```bash
pip install pyinstaller
```

### **"Inno Setup não encontrado"**
- Instale de: https://jrsoftware.org/isinfo.php
- Certifique-se que está em: `C:\Program Files (x86)\Inno Setup 6\`

### **"Executável não funciona"**
```bash
# Teste antes de gerar instalador:
cd dist\Confeitaria
Confeitaria.exe
```

---

## 📋 **Checklist Final**

Antes de distribuir, verifique:

- [ ] ✅ Banco de dados existe (`confeitaria.db`)
- [ ] ✅ Banco tem dados (40 clientes, 40 produtos, 100 pedidos)
- [ ] ✅ `prepare_distribution.bat` executado com sucesso
- [ ] ✅ `build.bat` executado sem erros
- [ ] ✅ Instalador criado em `output\Confeitaria_Setup_1.12.1.exe`
- [ ] ✅ Instalador testado em máquina limpa
- [ ] ✅ Sistema abre e mostra dados no Dashboard
- [ ] ✅ Login funciona (admin/admin)

---

## 🎉 **Pronto para Distribuir!**

Agora você pode:
1. ✅ Copiar `Confeitaria_Setup_1.12.1.exe` para qualquer computador
2. ✅ Enviar por email, pen drive, ou compartilhar na rede
3. ✅ Instalar em quantos computadores precisar
4. ✅ Todos terão os mesmos dados iniciais!

---

## 📞 **Suporte**

Para dúvidas ou problemas:
- Verifique os logs em: `%LOCALAPPDATA%\Confeitaria\logs\`
- Revise os passos deste guia
- Teste o instalador antes de distribuir

---

**Sistema Confeitaria v1.12.1 - Sistema Local**
*© 2025 DWM Systems Developer*
