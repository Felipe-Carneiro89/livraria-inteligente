import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import sys
from urllib.parse import urljoin
from uuid import uuid4

from bs4 import BeautifulSoup
import requests

from aplicar_sql import PASTA, executar_sql


def ler_pagina(url):
    resposta = requests.get(url, headers={'User-Agent': 'LivrariaInteligente-Aula/1.0'}, timeout=30)
    resposta.raise_for_status()
    return BeautifulSoup(resposta.text, 'html.parser')


def listar_livros(numero):
    url = f'https://books.toscrape.com/catalogue/page-{numero}.html'
    pagina = ler_pagina(url)
    links = pagina.select('article.product_pod h3 a')
    if not links:
        raise ValueError(f'Nenhum livro encontrado na página {numero}.')
    return [urljoin(url, link['href']) for link in links]


def extrair_livro(url):
    pagina = ler_pagina(url)
    tabela = {linha.th.get_text(): linha.td.get_text() for linha in pagina.select('table.table tr')}
    descricao = pagina.select_one('#product_description + p')
    return {
        'url': url,
        'titulo': pagina.select_one('div.product_main h1').get_text(),
        'preco_raw': pagina.select_one('div.product_main p.price_color').get_text(),
        'rating_raw': ' '.join(pagina.select_one('p.star-rating')['class']),
        'estoque_raw': tabela['Availability'],
        'upc': tabela['UPC'],
        'n_reviews_raw': tabela['Number of reviews'],
        'categoria_raw': pagina.select('ul.breadcrumb a')[2].get_text(),
        'descricao': descricao.get_text() if descricao else '',
    }


def literal_sql(texto):
    delimitador = f'$livraria_{uuid4().hex}$'
    while delimitador in texto:
        delimitador = f'$livraria_{uuid4().hex}$'
    return delimitador + texto + delimitador


def gravar_livros(livros, execucao_id):
    valores = []
    for livro in livros:
        valores.append('(' + ','.join([
            literal_sql(livro['url']),
            literal_sql(json.dumps(livro, ensure_ascii=False)) + '::jsonb',
            literal_sql(execucao_id),
        ]) + ')')
    sql = 'insert into bronze.livros (fonte_url, payload, _execucao_id) values ' + ','.join(valores)
    executar_sql(sql)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    argumentos = argparse.ArgumentParser(description='Raspa os detalhes e acrescenta livros na bronze.')
    argumentos.add_argument('--paginas', type=int, default=50)
    opcoes = argumentos.parse_args()
    if not 1 <= opcoes.paginas <= 50:
        argumentos.error('--paginas deve estar entre 1 e 50.')
    executar_sql((PASTA / 'sql/00_bronze.sql').read_text(encoding='utf-8'), '00_bronze')
    with ThreadPoolExecutor(max_workers=8) as executor:
        urls = [url for lote in executor.map(listar_livros, range(1, opcoes.paginas + 1)) for url in lote]
        livros = list(executor.map(extrair_livro, urls))
    execucao_id = uuid4().hex
    gravar_livros(livros, execucao_id)
    print(json.dumps({'execucao_id': execucao_id, 'linhas_inseridas': len(livros)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
