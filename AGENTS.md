# AGENTS.md · Regras da casa

> Vale para qualquer agente de código (Claude Code, Codex, Cursor, Gemini CLI) que trabalhar nesta pasta.

## 0. Antes de QUALQUER tarefa
1. **Leia o `PRD.md` (o porquê) e o `SPEC.md` (o como) inteiros.** Sempre, mesmo que já tenha lido nesta sessão.
2. Se algo conflitar: **SPEC.md > PRD.md**. Se faltar informação, **pergunte**. Não presuma.

## 1. Como trabalhamos aqui
- **Uma etapa por vez.** Só execute a etapa que eu pedir. Nunca adiante a próxima.
- Antes de codar, escreva um plano curto (máx. 5 linhas) com os arquivos que vai criar ou alterar.
- **Você mesmo** cria os arquivos, aplica o SQL no banco (`aplicar_sql.py`) e roda as validações. Não me peça para rodar.
- Ao terminar a etapa:
  1. rode os **critérios de aceite** da etapa (SPEC.md) e mostre o resultado;
  2. marque a etapa como ✅ na tabela **Estado** do `SPEC.md` e registre ali qualquer decisão que você tomou;
  3. **pare** e espere minha aprovação.

## 2. Stack (não troque sem perguntar)
- Python 3.11+ · `requests` · `beautifulsoup4` · `psycopg[binary]` (v3) · `python-dotenv` · `mcp[cli]`
- LLM: `openai` ou `anthropic`, escolhido por variável de ambiente
- Banco: PostgreSQL no **Supabase**. Prata e ouro em **SQL puro** (views).
- Nenhuma outra biblioteca sem perguntar (nada de pandas, LangChain ou ORM).

## 3. Estrutura de pastas
```
01_scraper_bronze.py · aplicar_sql.py · 04_sql_agent.py · 05_mcp_server.py
sql/00_bronze.sql · sql/01_prata.sql · sql/02_ouro.sql
requirements.txt · .env (nunca versionar) · .env.exemplo
```

## 4. Convenções
- Nomes em português, `snake_case`. Schemas: `bronze`, `prata`, `ouro`.
- SQL **idempotente**: `create schema if not exists`, `create or replace view`.
- Toda linha de SQL que aplica uma regra leva o comentário `-- R<n>` ou `-- M<n>` (ex.: `-- R2`).
- Funções pequenas, com nome que diz o que fazem. Sem comentários óbvios.

## 5. Proibido
- Credencial no código ou em markdown. Tudo vem do `.env`.
- Alterar ou apagar dados da `bronze`.
- Inventar coluna, tabela ou regra que não esteja no `SPEC.md`.
- Avançar de etapa sem aprovação.

## 6. Definição de pronto
Critérios de aceite passando **e** Estado do `SPEC.md` atualizado. Sem os dois, a etapa não terminou.
