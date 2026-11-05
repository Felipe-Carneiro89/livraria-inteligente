# PRD.md · Livraria Inteligente

## Problema

A diretoria da livraria (fictícia, com catálogo do books.toscrape.com) quer saber **o que tem em catálogo, quanto vale o estoque e o que vende bem avaliado**. Hoje, cada pergunta vira um pedido ao time de dados, que demora dias.

## Objetivo

Uma base confiável, atualizada por scraping, e um **agente que responde em português** perguntas de negócio consultando essa base — direto no terminal ou dentro do Claude, via MCP.

## Usuários

| quem | precisa de |
| :---- | :---- |
| Diretoria comercial | resposta rápida, em português, com o número certo |
| Time de dados | pipeline simples de manter e reexecutar |

&nbsp;

## Perguntas que o produto PRECISA responder

1. Qual categoria tem o maior valor em estoque, em reais?  
2. Quantos livros bem avaliados custam menos de £20?  
3. Quantos livros únicos temos na base?  
4. Qual o preço médio por faixa de preço?

## Decisões de negócio (valem para todas as etapas e para o agente)

| decisão | motivo | quem decidiu |
| :---- | :---- | :---- |
| Moeda base é **libra (GBP)**. Quando pedirem reais, câmbio fixo **£1 \= R\$ 7,20** | relatório da diretoria em reais (valor fictício da aula) | Financeiro |
| **Bem avaliado** \= 4 ou 5 estrelas | critério da diretoria comercial | Comercial |
| Rankings por categoria **excluem** `Sem categoria`, salvo pedido explícito | não é uma categoria do catálogo | Comercial |
| Bronze é **append-only**; duplicidade se resolve só na prata | preservar o que veio de cada execução | Eng. Dados |
| O agente **só lê prata e ouro**, nunca a bronze | bronze tem lixo e duplicidade | Eng. Dados |

&nbsp;

## Escopo

- **Dentro:** scraping do catálogo, camadas bronze/prata/ouro no Supabase, agente SQL de linha de comando, servidor MCP somente leitura e Interface web  
- **Fora:** Agendamento, histórico de preço, vendas (o site não tem).

## Métricas de sucesso

- O agente acerta as **4 perguntas** acima.  
- A prata não tem duplicidade: `count(*) = count(distinct upc)`.  
- O pipeline roda de novo sem quebrar nada (idempotente).  
- O agente e o MCP **nunca** leem a bronze nem escrevem no banco.