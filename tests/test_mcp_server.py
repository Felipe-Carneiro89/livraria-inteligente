from datetime import timedelta
from functools import wraps
import json
import os
from pathlib import Path
import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PASTA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PASTA))


def extrair_dados(resultado):
    if resultado.structuredContent is not None:
        return resultado.structuredContent
    return json.loads(resultado.content[0].text)


def com_sessao(funcao):
    @wraps(funcao)
    async def executar(self):
        parametros = StdioServerParameters(
            command=sys.executable,
            args=[str(PASTA / '05_mcp_server.py')],
            cwd=str(PASTA),
            env={'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'PYTHONIOENCODING': 'utf-8'},
        )
        async with stdio_client(parametros) as (leitura, escrita):
            async with ClientSession(leitura, escrita, read_timeout_seconds=timedelta(seconds=30)) as sessao:
                self.sessao = sessao
                await sessao.initialize()
                await funcao(self)
    return executar


class TestesServidorMCP(unittest.IsolatedAsyncioTestCase):
    @com_sessao
    async def test_tres_ferramentas_contexto_e_bloqueios_sem_chave(self):
        ferramentas = (await self.sessao.list_tools()).tools
        self.assertEqual({f.name for f in ferramentas}, {'ler_contexto', 'listar_schema', 'consultar'})
        for ferramenta in ferramentas:
            self.assertIn('SQL', ferramenta.description)
            self.assertTrue(ferramenta.annotations.readOnlyHint)
        contexto = await self.sessao.call_tool('ler_contexto', {})
        self.assertFalse(contexto.isError)
        texto = contexto.content[0].text
        for nome in ('PRD.md', 'SPEC.md'):
            self.assertIn((PASTA / nome).read_text(encoding='utf-8'), texto)
        for sql in ['select * from bronze.livros', 'delete from ouro.livros',
                    'select * from prata.livros; select * from bronze.livros']:
            resposta = await self.sessao.call_tool('consultar', {'sql': sql})
            self.assertTrue(resposta.isError)
        print('MCP stdio: 3 ferramentas, contexto completo e consultas proibidas recusadas; sem chave LLM.')

    @unittest.skipUnless(os.getenv('VALIDAR_BANCO') == '1', 'Integração opcional com Supabase')
    @com_sessao
    async def test_consultas_reais_em_cliente_mcp(self):
        await self.sessao.call_tool('ler_contexto', {})
        schema = await self.sessao.call_tool('listar_schema', {})
        self.assertFalse(schema.isError)
        self.assertIn('prata', str(schema))
        self.assertIn('ouro', str(schema))
        self.assertNotIn('bronze', str(schema))
        contagem = await self.sessao.call_tool('consultar', {'sql': 'select count(*) as quantidade from prata.livros'})
        self.assertFalse(contagem.isError)
        self.assertEqual(extrair_dados(contagem)['linhas'], [{'quantidade': 40}])
        sql = "select categoria, round(valor_estoque_gbp * 7.20, 2) as valor_brl from ouro.categorias where categoria <> 'Sem categoria' order by valor_estoque_gbp desc limit 1"
        print('SQL de referência mostrado antes da chamada MCP:', sql)
        ranking = await self.sessao.call_tool('consultar', {'sql': sql})
        self.assertFalse(ranking.isError)
        self.assertEqual(extrair_dados(ranking)['linhas'], [{'categoria': 'Poetry', 'valor_brl': '25543.87'}])
        limitado = await self.sessao.call_tool('consultar', {'sql': 'select * from ouro.livros union all select * from ouro.livros'})
        self.assertFalse(limitado.isError)
        self.assertEqual(len(extrair_dados(limitado)['linhas']), 50)
        print('MCP stdio + Supabase: 40 livros, Poetry R$ 25.543,87 e limite 50 confirmados. SQL de referência escrito no teste, sem geração por LLM.')


if __name__ == '__main__':
    unittest.main()
