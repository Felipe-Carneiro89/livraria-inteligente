import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
import json
import sys
from urllib.parse import urlsplit


agente = import_module('04_sql_agent')
CONSULTAS = {
    'maior_estoque': {
        'titulo': 'Qual categoria tem o maior valor em estoque, em reais?',
        'sql': """select categoria, round(valor_estoque_gbp * 7.20, 2) as valor_estoque_brl -- M4
from ouro.categorias
where categoria <> 'Sem categoria' -- M4
order by valor_estoque_gbp desc
limit 1""",
    },
    'bem_avaliados': {
        'titulo': 'Quantos livros bem avaliados custam menos de £20?',
        'sql': """select count(*) as quantidade
from ouro.livros
where bem_avaliado and preco_gbp < 20 -- M2""",
    },
    'livros_unicos': {
        'titulo': 'Quantos livros únicos temos na base?',
        'sql': 'select count(distinct upc) as quantidade from prata.livros',
    },
    'precos_por_faixa': {
        'titulo': 'Qual o preço médio por faixa de preço?',
        'sql': """select faixa_preco, avg(preco_gbp) as preco_medio_gbp -- M3 M4
from ouro.livros
group by faixa_preco -- M3
order by min(preco_gbp) -- M3""",
    },
}
SQL_CATEGORIAS = """select categoria, qtd_titulos, valor_estoque_gbp, pct_bem_avaliados -- M1 M2 M4
from ouro.categorias
where categoria <> 'Sem categoria' -- M4
order by valor_estoque_gbp desc, categoria"""
SQL_LIVROS = """select upc, titulo, categoria, preco_gbp, rating, estoque_qtd, bem_avaliado -- M2 M4
from ouro.livros
order by titulo, upc"""


def executar_fixa(cursor, sql):
    sem_comentarios = '\n'.join(linha.partition('--')[0] for linha in sql.splitlines())
    cursor.execute(agente.validar_sql(sem_comentarios), prepare=False)
    return cursor.fetchall()


def carregar_painel():
    with agente.abrir_leitura() as cursor:
        consultas = {nome: {**definicao, 'linhas': executar_fixa(cursor, definicao['sql'])}
                     for nome, definicao in CONSULTAS.items()}
        categorias = executar_fixa(cursor, SQL_CATEGORIAS)
        livros = executar_fixa(cursor, SQL_LIVROS)
    return {
        'atualizado_em': datetime.now(timezone.utc).isoformat(),
        'consultas': consultas,
        'categorias': categorias,
        'livros': livros,
        'limite': 50,
        'llm': {'disponivel': False, 'mensagem': 'Chat aguardando configuração'},
    }


class ServidorLocal(ThreadingHTTPServer):
    daemon_threads = True


class Rotas(BaseHTTPRequestHandler):
    def enviar(self, status, conteudo, tipo='application/json; charset=utf-8'):
        dados = conteudo.encode('utf-8') if isinstance(conteudo, str) else conteudo
        self.send_response(status)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(dados)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(dados)

    def json(self, status, dados):
        self.enviar(status, json.dumps(dados, ensure_ascii=False, default=str))

    def do_GET(self):
        caminho = urlsplit(self.path).path
        if caminho == '/':
            self.enviar(200, (agente.PASTA / 'web/index.html').read_bytes(), 'text/html; charset=utf-8')
        elif caminho == '/api/saude':
            self.json(200, {'status': 'ok', 'llm': 'aguardando_configuracao'})
        elif caminho == '/api/painel':
            try:
                self.json(200, carregar_painel())
            except Exception:
                self.json(503, {'erro': 'Não foi possível consultar o banco. Confira a conexão no .env e tente novamente.'})
        elif caminho == '/favicon.ico':
            self.enviar(204, b'')
        else:
            self.json(404, {'erro': 'Rota não encontrada.'})

    def do_POST(self):
        self.json(405, {'erro': 'Método não permitido. A interface oferece somente consultas prontas.'})

    def log_message(self, formato, *argumentos):
        return


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    argumentos = argparse.ArgumentParser(description='Interface local da Livraria Inteligente, sem chamadas LLM.')
    argumentos.add_argument('--porta', type=int, default=8000)
    opcoes = argumentos.parse_args()
    with ServidorLocal(('127.0.0.1', opcoes.porta), Rotas) as servidor:
        print(f'Livraria Inteligente: http://127.0.0.1:{servidor.server_port}', flush=True)
        print('Dados reais do Supabase; consultas somente leitura; chat aguardando configuração.', flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
