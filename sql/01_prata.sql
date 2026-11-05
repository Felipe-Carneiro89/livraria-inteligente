create schema if not exists prata;

create or replace view prata.livros as
with livros_recentes as (
    select distinct on (btrim(payload->>'upc')) payload, _ingestao_em -- R1 R7
    from bronze.livros
    order by btrim(payload->>'upc'), _ingestao_em desc, id desc -- R1 R7
)
select
    btrim(payload->>'upc') as upc, -- R7
    btrim(payload->>'titulo') as titulo, -- R7
    case when btrim(payload->>'categoria_raw') in ('Default', 'Add a comment') then 'Sem categoria' else btrim(payload->>'categoria_raw') end as categoria, -- R6 R7
    regexp_replace(payload->>'preco_raw', '[^0-9.]', '', 'g')::numeric(10,2) as preco_gbp, -- R2
    case btrim(payload->>'rating_raw') -- R3 R7
        when 'star-rating One' then 1 -- R3
        when 'star-rating Two' then 2 -- R3
        when 'star-rating Three' then 3 -- R3
        when 'star-rating Four' then 4 -- R3
        when 'star-rating Five' then 5 -- R3
    end as rating, -- R3
    coalesce(substring(payload->>'estoque_raw' from '[0-9]+')::int, 0) as estoque_qtd, -- R4
    btrim(payload->>'n_reviews_raw')::int as n_reviews, -- R5 R7
    btrim(payload->>'url') as url, -- R7
    _ingestao_em
from livros_recentes;
