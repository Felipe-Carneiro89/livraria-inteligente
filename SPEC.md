# SPEC.md · Como construir, etapa por etapa

> Execute **uma etapa por vez**, só quando pedido. As decisões de negócio estão no **PRD.md**; as regras técnicas (R1–R7, M1–M4) e o dicionário estão aqui. O agente SQL (Etapa 4\) e o MCP (Etapa 5\) leem o PRD.md e este arquivo inteiros a cada pergunta.

```
books.toscrape.com ──► bronze.livros ──► prata.livros ──► ouro.livros / ouro.categorias ──► agente SQL ──► MCP
     (Etapa 1)            (cru)            (Etapa 2)              (Etapa 3)                   (Etapa 4)      (Etapa 5)
```

&nbsp;

## Estado (o agente atualiza ao fim de cada etapa)

| etapa | status | decisões tomadas / observações |
| :---- | :---- | :---- |
| 1 · Scraping → bronze | ✅ concluída | Em 2026-11-04, SQL aplicado por aplicar_sql.py via ponte temporária para o MCP Supabase conectado. Duas execuções de --paginas 2 inseriram 40 linhas cada: total 80, 40 UPCs distintos. Três payloads conferidos com textos crus (Â£, star-rating e In stock). Ambiente Python 3.13 em pasta temporária curta devido ao limite de caminho do Windows; saída dos utilitários em UTF-8. Scripts priorizam MCP e aceitam DATABASE_URL como alternativa; nenhuma credencial foi salva. |
| 2 · Prata | ✅ concluída | View prata.livros criada por sql/01_prata.sql e aplicada via aplicar_sql.py / MCP. R1–R7 implementadas; 40 linhas e 40 UPCs distintos; zero nulos em preco_gbp, rating e estoque_qtd; zero categorias proibidas. Colunas e tipos conferidos. Bronze preservada com 80 linhas. Empates de _ingestao_em resolvidos pelo maior id; UPC normalizado por R7 antes da deduplicação. |
| 3 · Ouro | ✅ concluída | sql/02_ouro.sql aplicado via aplicar_sql.py / MCP. Ouro com 40 livros e 21 categorias; soma de qtd_titulos = 40, igual à prata. Zero faixas inválidas e zero divergências M1–M3. GBP nas views; M4 validada em consulta com câmbio 7,20 e exclusão de Sem categoria. Percentual de bem avaliados em escala 0–100. |
| 4 · Agente SQL | 🟡 implementada; aceite LLM pendente | 04_sql_agent.py criado; contexto integral e schema real, provedores por .env, três tentativas e guardrails implementados. 11 testes passaram, incluindo integração real somente leitura, limite de 50 linhas, timeout e consultas de referência. Nenhuma chamada a LLM. Usuário não fornecerá chave agora; acerto das quatro respostas pelo modelo permanece sem validação. Sem ✅ até esse aceite passar. |
| 5 · Servidor MCP | 🟡 implementada; aceite do cliente pendente | 05_mcp_server.py e mcp_config.exemplo.json criados. Duas verificações por cliente MCP stdio passaram: ferramentas, contexto, schema real, contagem 40, ranking de referência e limite 50; bronze e escrita recusadas. Inspector CLI também listou as três ferramentas e consultou a contagem 40. Servidor não exige chave LLM. Pendentes pergunta em linguagem natural gerando SQL em aplicativo com modelo e fluxo literal mcp dev, que requer uv ausente. |
| 6 · Interface web local | 🟡 implementada; aceite visual pendente | 06_interface_web.py e web/index.html criados. Cinco testes HTTP e Supabase passaram; página e painel retornaram HTTP 200 em localhost. Conferência visual interrompida pelo controle do navegador; sem ✅ até esse aceite. Nenhuma chamada LLM. |

&nbsp;

---

## Fonte de dados: books.toscrape.com

- Site público feito para treinar scraping. 50 páginas × 20 livros \= 1.000 livros.  
- Listagem: `https://books.toscrape.com/catalogue/page-{n}.html` → links em `article.product_pod h3 a`.  
- Detalhe do livro: título em `div.product_main h1`; preço em `div.product_main p.price_color`; avaliação na classe de `p.star-rating` (ex.: `star-rating Three`); tabela `table.table` com `UPC`, `Availability`, `Number of reviews`; categoria no 3º link de `ul.breadcrumb`.  
- **Encoding:** o site não declara charset. Com `requests`, o `£` costuma chegar como `Â£`. Na bronze isso fica como veio; R2 resolve na prata.  
- Campos do `payload` na bronze: `url`, `titulo`, `preco_raw`, `rating_raw`, `estoque_raw`, `upc`, `n_reviews_raw`, `categoria_raw`, `descricao`.

## Regras: bronze → prata

- **R1 · Chave e duplicidade:** chave \= `upc`. Manter só a linha com o `_ingestao_em` mais recente.  
- **R2 · Preço:** extrair só o número de `preco_raw` → `preco_gbp numeric(10,2)`. Moeda \= libra (GBP).  
- **R3 · Avaliação:** `star-rating One..Five` → `rating` 1..5.  
- **R4 · Estoque:** de `In stock (22 available)` extrair `22` → `estoque_qtd int`. Sem número \= 0\.  
- **R5 · Reviews:** `n_reviews_raw` → `n_reviews int`.  
- **R6 · Categoria:** `Default` e `Add a comment` não são categorias → `Sem categoria`.  
- **R7 · Texto:** remover espaços nas pontas.

## Métricas: ouro

- **M1 · Valor em estoque** \= `preco_gbp × estoque_qtd`.  
- **M2 · Bem avaliado** \= `rating >= 4` (decisão do PRD).  
- **M3 · Faixa de preço:** `até £20` (\< 20\) · `£20–40` (20 a \< 40\) · `acima de £40` (≥ 40).  
- **M4 · Moeda das respostas:** GBP. Se pedirem reais, câmbio do PRD (£1 \= R\$ 7,20). Rankings de categoria **excluem** `Sem categoria`, salvo pedido explícito.

## Dicionário de dados

- **prata.livros** (1 linha \= 1 livro): `upc` · `titulo` · `categoria` · `preco_gbp` · `rating` · `estoque_qtd` · `n_reviews` · `url` · `_ingestao_em`  
- **ouro.livros:** prata \+ `valor_estoque_gbp` (M1) · `faixa_preco` (M3) · `bem_avaliado` (M2, bool)  
- **ouro.categorias** (1 linha \= 1 categoria): `categoria` · `qtd_titulos` · `preco_medio_gbp` · `rating_medio` · `estoque_unidades` · `valor_estoque_gbp` · `pct_bem_avaliados`

---

## Etapa 1 · Scraping → bronze

### Registro da validação — 2026-11-04

- `python aplicar_sql.py sql/00_bronze.sql`: aplicado com sucesso pelo MCP Supabase, sem apagar ou alterar dados existentes.
- `python 01_scraper_bronze.py --paginas 2`: 40 linhas inseridas; execução `ffd92ae90b3948cf9621152813af9a85`.
- Segunda execução do mesmo comando: mais 40 linhas; execução `8b8ad92f5aee4ec7b1bd4c0ae3f7e353`.
- Contagens via `aplicar_sql.py --query`: primeira carga = 40 linhas / 40 UPCs; segunda carga = 80 linhas / 40 UPCs. Cada execução contém 40 linhas.
- Três payloads completos lidos pelo utilitário. Exemplos preservados: `Â£51.77`, `star-rating Three`, `In stock (22 available)`.
- Dependências instaladas em ambiente virtual Python 3.13 na pasta temporária `livraria-etapa1-venv`; a instalação na pasta do projeto excedeu o limite de caminho do Windows.
- A autenticação MCP da sessão não é herdada automaticamente pelo Python. Nesta validação, o agente operou uma ponte temporária de pedidos/respostas JSON, selecionada por `MCP_PONTE_DIR`, sem credenciais. Fora da sessão, configurar `SUPABASE_MCP_URL` e, se necessário, `SUPABASE_MCP_TOKEN`, ou `DATABASE_URL`, no `.env`. A ponte exige o agente ativo e não é um servidor MCP da Etapa 5.
- Criado `.gitignore` para excluir `.env`, ambientes locais, cache Python e a pasta local de ponte. Nenhuma etapa seguinte foi executada.

**Entrega:** `requirements.txt`, `.env.exemplo`, `sql/00_bronze.sql`, `01_scraper_bronze.py`, `aplicar_sql.py`

Requisitos

- Tabela `bronze.livros` (`id bigserial`, `fonte_url text`, `payload jsonb`, `_execucao_id text`, `_ingestao_em timestamptz default now()`).  
- Raspar a **página de detalhe** de cada livro (a listagem não tem UPC nem estoque). Campos do `payload`: ver "Fonte de dados".  
- **Bronze é cru:** grava os textos exatamente como vieram. Nenhuma limpeza.  
- **Append-only:** cada execução insere de novo, sem upsert.  
- Parâmetro `--paginas N` (20 livros por página). Até 8 requisições em paralelo, com `User-Agent` próprio.  
- Conexão via MCP do supabase (priorize assim) ou \`DATABASE\_URL\` do \`.env\`. O script cria a tabela se ela não existir.  
- `aplicar_sql.py`: utilitário que **o próprio agente usa** nas etapas seguintes. `python aplicar_sql.py sql/arquivo.sql` executa o arquivo; `python aplicar_sql.py --query "select ..."` imprime o resultado.

Critérios de aceite

- `python 01_scraper_bronze.py --paginas 2` grava 40 linhas.  
- Rodar 2× → `select count(*), count(distinct payload->>'upc') from bronze.livros` \= 80 e 40\.  
- `select payload from bronze.livros limit 3` mostra os textos crus (`£`/`Â£`, `star-rating Three`, `In stock (N available)`).

---

## Etapa 2 · Prata

### Registro da validação — 2026-11-04

- `python aplicar_sql.py sql/01_prata.sql`: aplicado com sucesso via ponte MCP. A primeira chamada local expirou aguardando a resposta, embora a migração tenha sido aplicada; a reaplicação idempotente terminou com sucesso.
- Critérios de aceite consultados com `aplicar_sql.py --query`: 40 linhas, 40 UPCs distintos, zero preços nulos, zero ratings nulos, zero estoques nulos e zero categorias `Default` ou `Add a comment`.
- `information_schema.columns`: as nove colunas correspondem ao dicionário; `preco_gbp` é `numeric(10,2)` e rating, estoque e reviews são inteiros.
- Conferência de R1: zero divergências entre a ingestão selecionada pela view e a maior `_ingestao_em` por UPC na bronze.
- Decisões técnicas: espaços nas pontas do UPC removidos antes da deduplicação; em empate de `_ingestao_em`, maior `id` como desempate determinístico. Sem limpeza adicional de encoding fora das regras especificadas.
- Bronze preservada com 80 linhas. Etapa 3 não executada.

**Entrega:** `sql/01_prata.sql` (view `prata.livros`), aplicado no banco pelo agente: `python aplicar_sql.py sql/01_prata.sql`

Requisitos

- Aplicar **R1 a R7**, com `-- R<n>` em cada linha que aplica regra.  
- Colunas exatamente como no dicionário.

Critérios de aceite

- `count(*) = count(distinct upc)`.  
- Nenhum `preco_gbp`, `rating` ou `estoque_qtd` nulo.  
- Nenhuma categoria `Default` ou `Add a comment`.

---

## Etapa 3 · Ouro

### Registro da validação — 2026-11-04

- `python aplicar_sql.py sql/02_ouro.sql`: aplicado com sucesso pelo MCP Supabase, sem chave de LLM.
- Critérios de aceite consultados via `aplicar_sql.py --query`: prata = 40 livros; ouro = 40 livros; soma de `qtd_titulos` = 40; 21 categorias; zero faixas inválidas.
- Faixas observadas: `até £20` = 8 livros, `£20–40` = 17 e `acima de £40` = 15. Zero divergências nas fórmulas M1, M2 e M3.
- Colunas das duas views conferidas no `information_schema`, correspondendo ao dicionário.
- M4: valores das views mantidos em GBP. Ranking consultado com exclusão de `Sem categoria` e multiplicação por 7,20: Poetry, £3.547,76, equivalente a R$ 25.543,87 na amostra atual.
- Decisões: manter todas as categorias na view para preservar a reconciliação; aplicar a exclusão apenas nos rankings. `pct_bem_avaliados` expresso de 0 a 100. Exemplo de consulta M4 documentado no SQL sem criar colunas adicionais.
- Credencial encontrada no `.env.exemplo` foi preservada no `.env` local; exemplo sanitizado. `.env` continua excluído pelo `.gitignore`. Nenhuma credencial foi registrada neste documento.
- Etapa 4 não executada; restrição de ausência de chave de LLM registrada na tabela Estado.

**Entrega:** `sql/02_ouro.sql` (views `ouro.livros` e `ouro.categorias`), aplicado com `python aplicar_sql.py sql/02_ouro.sql`

Requisitos

- Métricas **M1 a M4**, com `-- M<n>` em cada linha que aplica métrica.  
- `ouro.livros` \= prata \+ `valor_estoque_gbp`, `faixa_preco`, `bem_avaliado`.  
- `ouro.categorias` \= 1 linha por categoria (colunas no dicionário).

Critérios de aceite

- `sum(qtd_titulos)` em `ouro.categorias` \= `count(*)` em `prata.livros`.  
- `faixa_preco` só tem os 3 valores definidos em M3.

---

## Etapa 4 · Agente SQL

### Implementação e validação parcial — 2026-11-04

- Criado `04_sql_agent.py`; atualizados `requirements.txt` e `.env.exemplo`; testes em `tests/test_sql_agent.py` usando somente `unittest` da biblioteca padrão.
- Adicionados ao `.env` local apenas campos ausentes de configuração LLM, com chaves vazias, preservando a conexão existente. SDKs OpenAI e Anthropic instalados no ambiente temporário e imports conferidos. Nenhuma API LLM foi chamada.
- Contexto reconstruído a cada pergunta: PRD e SPEC inteiros do disco, instruções e colunas reais de prata/ouro. `--sem-contexto` omite os documentos e expõe metadados de todos os schemas para comparação; as restrições de execução continuam ativas nos dois modos.
- Execução pelo psycopg / DATABASE_URL: transação read only, `statement_timeout = 10s`, `search_path = pg_catalog`, consulta envolvida em SELECT com LIMIT 50. O agente não reutiliza o executor administrativo de SQL do pipeline.
- Validação conservadora aceita SELECT/WITH sobre as três views existentes, incluindo CTEs simples e subconsultas. Recusa escrita, múltiplos comandos, bronze, outras relações, comentários, funções fora da lista e conversões não permitidas. Não é um parser PostgreSQL completo: sintaxe fora desse subconjunto é recusada e devolvida ao modelo para correção.
- Fluxo: um bloco SQL, até três tentativas com erro devolvido ao modelo, impressão de SQL e resultado, seguida de resposta em português. Perguntas ambíguas podem retornar pedido de esclarecimento sem executar SQL. Sem chave ou modelo configurado, encerra antes de consultar o LLM.
- Validação: `VALIDAR_BANCO=1` e `python -m unittest discover -s tests -v`, no ambiente temporário, resultaram em **11 testes aprovados**. Integração conferiu read only ligado, timeout 10s, limite real de 50 linhas e schema real. Testes locais conferiram bloqueios SQL, contexto integral, ausência de chave e até três tentativas com respostas simuladas exclusivamente para teste de controle de fluxo.
- Referências SQL executadas sem LLM: Poetry = R$ 25.543,87 em estoque; 3 livros bem avaliados abaixo de £20; 40 livros únicos; médias GBP por faixa: até £20 = 16,68375, £20–40 = 29,68 e acima de £40 = 50,688. Isso valida a base e os SELECTs escritos nos testes, não a capacidade do modelo de produzi-los.
- **Aceite pendente:** gerar SQL e respostas corretas para as quatro perguntas usando um provedor real, com contexto ligado. Exige chave, modelo e acesso ao provedor; a etapa não está marcada como concluída.
- Para usar depois: preencher `LLM_PROVIDER`, `LLM_MODEL` e a chave do provedor escolhido no `.env` já existente. Não substituir esse arquivo pelo exemplo, para preservar a conexão do banco. Executar `python 04_sql_agent.py` no ambiente com as dependências instaladas; neste Windows o interpretador preparado está em `$env:TEMP\livraria-etapa1-venv\Scripts\python.exe`.
- Integrações baseadas na [documentação oficial OpenAI Python](https://developers.openai.com/api/reference/python) e na [referência oficial Anthropic Messages](https://platform.claude.com/docs/en/api/python/messages/create). Sem alteração do banco ou execução da Etapa 5.

**Entrega:** `04_sql_agent.py`

Requisitos

- Loop: pergunta → LLM gera **um** SQL em bloco ```` ```sql ```` → executa → LLM responde em português.  
- **Contexto do agente (o coração da etapa):** o system prompt é montado a cada execução com  
  1. instruções do agente (papel, só prata/ouro, um SELECT por vez, perguntar se ambíguo);  
  2. o **`PRD.md` e o `SPEC.md` inteiros**, lidos do disco (os mesmos arquivos que construíram o pipeline);  
  3. o **schema real** de `prata` e `ouro`, lido do `information_schema`.  
- Flag `--sem-contexto`: só a instrução mínima \+ o schema de **todas** as tabelas (para comparar em aula).  
- Guardrails: só `SELECT`/`WITH`, transação `read only`, `statement_timeout` de 10 s, `limit 50`, até 3 tentativas com o erro devolvido ao LLM.  
- Provedor e modelo por `.env`: `LLM_PROVIDER` (openai|anthropic), `LLM_MODEL`.  
- Imprimir o SQL gerado, o resultado e a resposta.

Critérios de aceite

- Acerta as 4 perguntas do PRD com o contexto ligado.  
- Nunca consulta `bronze` com o contexto ligado.

---

## Etapa 5 · Servidor MCP

### Implementação e validação parcial — 2026-11-04

- `05_mcp_server.py` usa FastMCP da biblioteca `mcp`, com transporte stdio e somente três ferramentas: `ler_contexto`, `listar_schema` e `consultar(sql)`.
- Cada descrição orienta a leitura do contexto antes do SQL e sua apresentação ao usuário antes da execução. O contexto lê os dois documentos inteiros do disco em cada chamada. O schema lista somente prata e ouro.
- `consultar` reutiliza os guardrails da Etapa 4: read only, timeout 10s, SELECT/WITH validado e limite externo 50. Erros de banco são apresentados sem expor a string de conexão. O servidor não chama LLM nem precisa das chaves OpenAI/Anthropic.
- `tests/test_mcp_server.py`: **2 testes aprovados** com `VALIDAR_BANCO=1`, usando um cliente MCP real que inicia o servidor como subprocesso por stdio, com chaves LLM vazias. Conferidos: três ferramentas; PRD e SPEC completos; schema prata/ouro; contagem 40; ranking de referência Poetry / R$ 25.543,87; limite 50; recusas de bronze, escrita e comandos múltiplos.
- O ranking foi enviado como SQL explícito pelo teste após leitura do contexto e schema. Isso verifica transporte, banco e M4, mas não substitui o aceite de geração de SQL por um modelo a partir da pergunta 1.
- `mcp_config.exemplo.json` contém a entrada `mcpServers.livraria_inteligente` para Claude Desktop / Claude Code. JSON e caminhos conferidos, sem credenciais. O servidor localiza o `.env` pela pasta do projeto, independentemente da pasta de trabalho do cliente.
- A configuração aponta para o Python 3.13 já preparado em pasta temporária curta, devido ao limite de caminhos do Windows. Se esse ambiente for removido ou o projeto mudar de pasta, ajustar `command` e `args` para os novos caminhos. Esse exemplo ainda não foi instalado na configuração global de um aplicativo.
- Para Claude Desktop, incorporar a entrada `livraria_inteligente` em `mcpServers` na configuração existente, preservando os outros servidores. Para Claude Code, a mesma estrutura pode ser usada em `.mcp.json` do projeto. Nenhuma chave ou senha deve ser colocada nesse JSON; a conexão continua no `.env`.
- O comando `mcp dev` desta versão depende de `uv`, ausente no ambiente. Sem instalar essa ferramenta adicional, foi validado o mesmo servidor por cliente SDK e pelo Inspector CLI usando o interpretador preparado diretamente. `npx.cmd --yes @modelcontextprotocol/inspector --cli --config mcp_config.exemplo.json --server livraria_inteligente --method tools/list` listou exatamente as três ferramentas. A chamada `tools/call` com `--tool-name consultar` e `--tool-arg "sql=select count(*) as quantidade from prata.livros"` retornou quantidade 40 e `isError=false`. Navegador não foi aberto. O fluxo literal `mcp dev` permanece pendente de `uv`. A [documentação oficial do SDK v1](https://py.sdk.modelcontextprotocol.io/v1/) foi conferida, mantendo a dependência existente `mcp<2`.
- **Aceite pendente:** em aplicativo MCP com modelo, fazer a pergunta 1 do PRD e conferir a geração de consulta em ouro.categorias com câmbio 7,20 e exclusão de Sem categoria. O servidor em si não exige chave LLM; esse modelo é fornecido pelo aplicativo cliente. A etapa permanece sem ✅ até concluir os critérios pendentes.

**Entrega:** `05_mcp_server.py`, `mcp_config.exemplo.json`

Requisitos

- Servidor MCP (biblioteca `mcp`, FastMCP, transporte stdio) com 3 ferramentas: `ler_contexto` (devolve PRD.md \+ SPEC.md), `listar_schema` (prata e ouro via `information_schema`) e `consultar(sql)` (um SELECT, até 50 linhas).  
- Mesmos guardrails do agente: transação `read only`, `statement_timeout` 10 s, só `SELECT`/`WITH`, `bronze` proibida.  
- A descrição de cada ferramenta diz ao modelo **quando** usá-la (ler o contexto antes de escrever SQL; mostrar o SQL ao usuário).  
- `mcp_config.exemplo.json`: exemplo de configuração para Claude Desktop / Claude Code, sem segredo no arquivo.

Critérios de aceite

- `mcp dev 05_mcp_server.py` lista as 3 ferramentas e `consultar("select count(*) from prata.livros")` devolve o número.  
- Em um cliente MCP, a pergunta 1 do PRD gera uma consulta em `ouro.categorias` com câmbio 7,20 e sem `Sem categoria`.  
- `consultar("select * from bronze.livros")` é recusado.

---

## Etapa 6 · Interface web local — autorizada em 2026-11-04

### Registro de implementação e validação

- Em 2026-11-04, criados `06_interface_web.py`, `web/index.html` e `tests/test_interface_web.py`. Cinco testes passaram: página e saúde; rotas restritas; POST recusado; erro sem exposição de credencial; dados reais sem LLM.
- O servidor foi iniciado em segundo plano em `http://127.0.0.1:8000`; conferidos HTTP 200 para página e painel, com 40 livros. Para reiniciar, usar `python 06_interface_web.py` no ambiente preparado.
- A verificação visual ficou pendente: o navegador integrado estava indisponível e o controle do Chrome foi interrompido automaticamente por não conseguir confirmar a URL atual. Não foram validados visualmente atualização, busca ou layout responsivo.
- Em 2026-11-05, antes do versionamento, a suíte completa com `VALIDAR_BANCO=1` passou: **18 testes**, incluindo agente, cliente MCP e interface. Sem chamadas LLM. Isso não remove as pendências de aceite com modelo ou de conferência visual.

**Entrega:** `06_interface_web.py`, `web/index.html`, `tests/test_interface_web.py`.

Requisitos

- Servir somente em `127.0.0.1`, porta padrão 8000, com `http.server` da biblioteca padrão. Sem framework ou dependência adicional.
- Página em português, responsiva, com indicadores e resultados das quatro perguntas do PRD, ranking de categorias e catálogo dos livros disponíveis (até 50 linhas por consulta).
- Buscar dados reais do Supabase pelo backend Python, usando DATABASE_URL do `.env`, transação read only, timeout 10s e os guardrails existentes. Não modificar dados nem criar novas tabelas, colunas ou métricas de negócio.
- Exibir as quatro consultas fixas e seus resultados; categorias e catálogo usam as colunas já previstas no dicionário. Rankings excluem Sem categoria e conversão para reais usa 7,20.
- Botão para atualizar dados e busca local por título/categoria na listagem recebida. Indicar claramente o limite de 50 livros exibidos e a hora de atualização.
- O chat fica desabilitado com indicação de que aguarda configuração; nenhuma chamada LLM será feita, mesmo que uma chave seja preenchida futuramente, até integrar o chat em etapa própria.
- Backend serve apenas a página e rotas fixas de dados/saúde. Não expor `.env`, documentos locais ou execução de SQL enviado pelo navegador. Falhas de banco devem aparecer sem credenciais, com opção de tentar novamente.
- Não publicar: a entrega solicitada é local. Manter o servidor iniciado para o usuário abrir o endereço.

Critérios de aceite

- `GET /` retorna HTML e `GET /api/painel` retorna os resultados reais das quatro consultas, sem chave LLM.
- Amostra atual: 40 livros únicos, 3 bem avaliados abaixo de £20, Poetry com R$ 25.543,87; médias por faixa coerentes com a ouro.
- Consultas retornam até 50 linhas, sem acesso direto à bronze, escrita ou chamadas ao LLM. Rotas fora da lista retornam 404; POST retorna 405.
- Erro de banco simulado retorna mensagem genérica sem expor a conexão ou senha.
- Verificação no navegador: indicadores carregam, atualização funciona, busca filtra a lista, chat desabilitado e layout legível em tela larga e estreita.
- Registrar as validações e o endereço local nesta etapa e marcar ✅ somente após os critérios passarem.

---

## Versionamento GitHub — solicitado em 2026-11-05

- Conta autenticada confirmada: `Felipe-Carneiro89`. Destino definido para repositório privado `livraria-inteligente`, branch `main`.
- Criado `README.md` com preparação do ambiente, execução local, MCP, testes e pendências.
- `.gitignore` protege `.env` e variantes, ambientes virtuais, cache Python, logs e ponte temporária; `.env.exemplo` permanece versionável, com campos de credenciais vazios.
- Conferidos os 20 arquivos previstos para o primeiro commit: nenhum segredo conhecido do `.env`, padrão de token reconhecido ou arquivo temporário encontrado. Nenhum dado do Supabase é incluído no repositório.
- Suíte completa antes do envio: 18 testes aprovados. As etapas 4, 5 e 6 continuam com os aceites pendentes já documentados.
