# Livraria Inteligente

Projeto didático de Business Intelligence com scraping de books.toscrape.com, arquitetura bronze/prata/ouro no PostgreSQL do Supabase, agente SQL, servidor MCP e interface web local.

## Estado atual

- Bronze, prata e ouro implementadas e validadas na base de demonstração: 80 registros crus e 40 livros únicos, coletados das duas primeiras páginas em duas execuções.
- Interface web com dados reais, indicadores, ranking de categorias, catálogo com busca e as quatro consultas prontas do projeto. Funciona sem chave de LLM; chat desabilitado.
- Agente SQL implementado com contexto e guardrails; aceite com provedor LLM pendente de chave e modelo.
- Servidor MCP validado por cliente stdio e Inspector CLI; aceite de geração de SQL por modelo em aplicativo MCP pendente.
- Validação visual da interface pendente. Os testes HTTP e de banco passaram.

Os requisitos, regras de negócio, resultados e pendências estão em [PRD.md](PRD.md) e [SPEC.md](SPEC.md). As regras para agentes estão em [AGENTS.md](AGENTS.md).

## Preparar o ambiente

Use Python 3.11 ou superior. No Windows, prefira clonar em uma pasta com caminho curto para evitar limites de comprimento na criação do ambiente virtual.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.exemplo .env
```

Copie o exemplo apenas se ainda não houver `.env`. Preencha `DATABASE_URL` no `.env` com a conexão do seu Supabase. Não versione esse arquivo nem coloque credenciais no exemplo.

As tabelas e views precisam existir no banco configurado. Os comandos abaixo alteram o schema e o scraper acrescenta registros crus; as outras camadas são views:

```powershell
.\.venv\Scripts\python.exe aplicar_sql.py sql/00_bronze.sql
.\.venv\Scripts\python.exe 01_scraper_bronze.py --paginas 2
.\.venv\Scripts\python.exe aplicar_sql.py sql/01_prata.sql
.\.venv\Scripts\python.exe aplicar_sql.py sql/02_ouro.sql
```

Cada execução do scraper insere novos registros. Duplicidades são resolvidas na view prata; não se apagam dados da bronze. Os arquivos SQL são idempotentes.

## Abrir a interface local, sem LLM

```powershell
.\.venv\Scripts\python.exe 06_interface_web.py
```

Abra **http://127.0.0.1:8000**. Para outra porta, acrescente `--porta 8001`. O backend usa a conexão do `.env`; o navegador recebe apenas resultados das consultas fixas. A interface não chama APIs de LLM nem aceita SQL arbitrário.

## Agente SQL — configuração futura

Quando houver acesso a um provedor, preencha no `.env`:

- `LLM_PROVIDER`: `openai` ou `anthropic`.
- `LLM_MODEL`: um modelo disponível na conta.
- `OPENAI_API_KEY` ou `ANTHROPIC_API_KEY`: somente a chave do provedor escolhido.

```powershell
.\.venv\Scripts\python.exe 04_sql_agent.py
```

O agente realiza chamadas ao provedor configurado. Sem chave, encerra antes de chamá-lo. A opção `--sem-contexto` serve para comparação didática; mantém os bloqueios de execução.

## Servidor MCP — sem chave LLM no servidor

```powershell
.\.venv\Scripts\python.exe 05_mcp_server.py
```

O transporte é stdio, destinado a um cliente MCP. As ferramentas são `ler_contexto`, `listar_schema` e `consultar(sql)`. Consulte [mcp_config.exemplo.json](mcp_config.exemplo.json) e ajuste `command` para o seu Python e `args` para o caminho absoluto de `05_mcp_server.py`. O exemplo contém os caminhos do ambiente em que o projeto foi preparado; não contém credenciais.

O cliente fornece o modelo. O servidor usa apenas `DATABASE_URL` do `.env` para consultar prata/ouro e não chama APIs OpenAI ou Anthropic.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para incluir testes com o Supabase real:

```powershell
$env:VALIDAR_BANCO = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes de referência usam a amostra de 40 livros documentada no SPEC. Uma coleta maior ou alteração na base pode exigir ajuste dessas expectativas. Testes simulados de controle de fluxo não representam aceite da capacidade de geração de SQL do LLM.

## Dados e regras

A moeda base é GBP; conversão didática fixa de £1 para R$ 7,20. Livros bem avaliados têm 4 ou 5 estrelas. Rankings excluem `Sem categoria`, salvo pedido explícito. Não há dados de vendas.

Os dados do Supabase, credenciais, ambientes virtuais e arquivos temporários não fazem parte deste repositório.
