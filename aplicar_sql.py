import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

from dotenv import load_dotenv


PASTA = Path(__file__).resolve().parent
load_dotenv(PASTA / '.env')


def executar_ponte(sql, migracao):
    """Usa a ponte de arquivos temporária operada pelo agente conectado ao MCP."""
    pasta = Path(os.environ['MCP_PONTE_DIR'])
    identificador = uuid4().hex
    pedido = pasta / f'{identificador}.pedido.json'
    resposta = pasta / f'{identificador}.resposta.json'
    temporario = pasta / f'{identificador}.tmp'
    temporario.write_text(json.dumps({'query': sql, 'migracao': migracao}), encoding='utf-8')
    temporario.replace(pedido)
    prazo = time.monotonic() + 180
    while not resposta.exists():
        if time.monotonic() > prazo:
            raise TimeoutError('A ponte MCP não respondeu; confira o resultado antes de repetir uma carga.')
        time.sleep(0.2)
    resultado = json.loads(resposta.read_text(encoding='utf-8-sig'))
    if resultado.get('isError'):
        raise RuntimeError(json.dumps(resultado, ensure_ascii=False))
    return resultado


async def executar_mcp(sql, migracao):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    token = os.getenv('SUPABASE_MCP_TOKEN')
    cabecalhos = {'Authorization': f'Bearer {token}'} if token else None
    async with streamablehttp_client(os.environ['SUPABASE_MCP_URL'], headers=cabecalhos) as (leitura, escrita, _):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            ferramenta = 'apply_migration' if migracao else 'execute_sql'
            argumentos = {'query': sql}
            if migracao:
                argumentos['name'] = migracao
            resultado = await sessao.call_tool(ferramenta, argumentos)
            if resultado.isError:
                raise RuntimeError(str(resultado.content))
            return resultado.model_dump(mode='json')


def executar_sql(sql, migracao=None):
    if os.getenv('MCP_PONTE_DIR'):
        return executar_ponte(sql, migracao)
    if os.getenv('SUPABASE_MCP_URL'):
        return asyncio.run(executar_mcp(sql, migracao))
    if not os.getenv('DATABASE_URL'):
        raise RuntimeError('Configure o MCP Supabase ou DATABASE_URL no .env. A conexão do agente não é herdada pelo Python.')
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL']) as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description:
                colunas = [coluna.name for coluna in cursor.description]
                return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
            return {'linhas_afetadas': cursor.rowcount}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    argumentos = argparse.ArgumentParser(description='Aplica SQL via MCP Supabase ou DATABASE_URL.')
    grupo = argumentos.add_mutually_exclusive_group(required=True)
    grupo.add_argument('arquivo', nargs='?')
    grupo.add_argument('--query')
    opcoes = argumentos.parse_args()
    sql = Path(opcoes.arquivo).read_text(encoding='utf-8') if opcoes.arquivo else opcoes.query
    migracao = Path(opcoes.arquivo).stem if opcoes.arquivo else None
    print(json.dumps(executar_sql(sql, migracao), ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
