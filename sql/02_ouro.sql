create schema if not exists ouro;

create or replace view ouro.livros as
select
    upc,
    titulo,
    categoria,
    preco_gbp, -- M4
    rating,
    estoque_qtd,
    n_reviews,
    url,
    _ingestao_em,
    preco_gbp * estoque_qtd as valor_estoque_gbp, -- M1 M4
    case -- M3
        when preco_gbp < 20 then 'até £20' -- M3
        when preco_gbp < 40 then '£20–40' -- M3
        else 'acima de £40' -- M3
    end as faixa_preco, -- M3
    rating >= 4 as bem_avaliado -- M2
from prata.livros;

create or replace view ouro.categorias as
select
    categoria,
    count(*) as qtd_titulos,
    avg(preco_gbp) as preco_medio_gbp, -- M4
    avg(rating) as rating_medio,
    sum(estoque_qtd) as estoque_unidades,
    sum(valor_estoque_gbp) as valor_estoque_gbp, -- M1 M4
    100.0 * count(*) filter (where bem_avaliado) / count(*) as pct_bem_avaliados -- M2
from ouro.livros
group by categoria;

-- As views mantêm todas as categorias para reconciliar os totais. -- M4
-- Nas respostas, usar GBP; converter para BRL somente quando solicitado. -- M4
-- Exemplo de ranking em reais, excluindo Sem categoria salvo pedido explícito: -- M4
-- select categoria, valor_estoque_gbp * 7.20 as valor_estoque_brl -- M4
-- from ouro.categorias
-- where categoria <> 'Sem categoria' -- M4
-- order by valor_estoque_gbp desc
-- limit 1;
