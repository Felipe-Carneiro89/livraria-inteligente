import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch


PASTA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PASTA))
spec = importlib.util.spec_from_file_location('agente', PASTA / '04_sql_agent.py')
agente = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agente)

CONSULTAS = [
    "select categoria, round(valor_estoque_gbp * 7.20, 2) as valor_brl from ouro.categorias where categoria <> 'Sem categoria' order by valor_estoque_gbp desc limit 1",
    'select count(*) as quantidade from ouro.livros where bem_avaliado and preco_gbp < 20',
    'select count(distinct upc) as quantidade from prata.livros',
    'select faixa_preco, avg(preco_gbp) as preco_medio_gbp from ouro.livros group by faixa_preco order by faixa_preco',
]


class TestesProtecoes(unittest.TestCase):
    def test_consultas_de_referencia_e_cte(self):
        for sql in CONSULTAS + [
            'with base as (select * from ouro.livros) select count(*) from base;',
            'select * from "ouro"."livros"',
            "select titulo from prata.livros where titulo = 'livro; bronze -- exemplo'",
        ]:
            with self.subTest(sql=sql):
                self.assertTrue(agente.validar_sql(sql).endswith('LIMIT 50'))

    def test_recusa_escrita_bronze_e_escapes(self):
        exemplos = [
            'select * from bronze.livros',
            'select * from "bronze"."livros"',
            'select * from prata.livros; delete from bronze.livros',
            'with x as (delete from ouro.livros returning *) select * from x',
            'select * into public.copia from ouro.livros',
            'select * from ouro.livros for update',
            'select pg_sleep(30) from ouro.livros',
            "select pg_read_file('/etc/passwd') from ouro.livros",
            "select set_config('transaction_read_only','off',false) from ouro.livros",
            'select public.funcao() from ouro.livros',
            'select * from public.usuarios',
            'select * from livros',
            'select * from ouro.livros, public.usuarios',
            'select * from ouro.livros join ouro.categorias using (categoria), public.usuarios',
            'select * from (select * from public.usuarios) x join ouro.livros on true',
            'select * from ouro.livros where exists (select 1 from bronze.livros)',
            'select * from ouro.livros union table public.usuarios',
            'select * from ouro.livros -- comentário',
            'select /* comentário */ * from ouro.livros',
            "select $$texto$$ from ouro.livros",
            "select titulo::regclass from ouro.livros",
            "select titulo::text.dominio from ouro.livros",
            "select e'texto' from ouro.livros",
            'copy ouro.livros to stdout',
        ]
        for sql in exemplos:
            with self.subTest(sql=sql), self.assertRaises(agente.ConsultaRecusada):
                agente.validar_sql(sql)

    def test_limite_envolve_inclusive_union_e_limit_maior(self):
        for sql in ['select * from ouro.livros limit 1000',
                    'select * from ouro.livros union all select * from ouro.livros']:
            self.assertTrue(agente.validar_sql(sql).startswith('SELECT * FROM ('))
            self.assertTrue(agente.validar_sql(sql).endswith('LIMIT 50'))

    def test_blocos_e_esclarecimento(self):
        self.assertIsNone(agente.extrair_sql('Você deseja preço em GBP ou BRL?'))
        self.assertEqual(agente.extrair_sql('```sql\nselect * from ouro.livros\n```'), 'select * from ouro.livros')
        for texto in ['```sql\nselect 1\n```\n```sql\nselect 2\n```', '```python\nprint(1)\n```']:
            with self.assertRaises(agente.ConsultaRecusada):
                agente.extrair_sql(texto)

    def test_ausencia_de_chave_nao_chama_modelo(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'openai', 'OPENAI_API_KEY': '', 'LLM_MODEL': ''}):
            with patch.object(agente, 'chamar_llm') as chamar:
                with self.assertRaisesRegex(ValueError, 'OPENAI_API_KEY'):
                    agente.responder('Quantos livros?')
                chamar.assert_not_called()

    def test_contexto_inteiro_a_cada_pergunta(self):
        with patch.object(agente, 'listar_schema', return_value=[]):
            texto = agente.montar_contexto()
            for nome in ['PRD.md', 'SPEC.md']:
                self.assertIn((PASTA / nome).read_text(encoding='utf-8'), texto)
            sem = agente.montar_contexto(True)
            self.assertNotIn('DOCUMENTO PRD.md', sem)
            agente.listar_schema.assert_called_with(True)

    def test_tres_tentativas_sem_simular_aceite_llm(self):
        with patch.object(agente, 'configurar_llm'), patch.object(agente, 'montar_contexto', return_value='contexto'):
            with patch.object(agente, 'chamar_llm', return_value='```sql\nselect * from bronze.livros\n```') as chamar:
                with redirect_stdout(io.StringIO()) as saida:
                    agente.responder('Pergunta de teste')
                self.assertEqual(chamar.call_count, 3)
                self.assertIn('3 tentativas', saida.getvalue())
                self.assertIn('Erro da consulta:', chamar.call_args.args[1][-1]['content'])


@unittest.skipUnless(os.getenv('VALIDAR_BANCO') == '1', 'Integração opcional com o banco real')
class TestesBanco(unittest.TestCase):
    def test_configuracao_read_only_e_timeout(self):
        with agente.abrir_leitura() as cursor:
            cursor.execute('show transaction_read_only')
            self.assertEqual(cursor.fetchone()['transaction_read_only'], 'on')
            cursor.execute('show statement_timeout')
            self.assertEqual(cursor.fetchone()['statement_timeout'], '10s')

    def test_limite_real(self):
        dados = agente.consultar('select * from ouro.livros union all select * from ouro.livros')
        self.assertEqual(len(dados), 50)

    def test_contexto_com_schema_real(self):
        contexto = agente.montar_contexto()
        self.assertIn('"table_schema": "ouro"', contexto)
        self.assertIn('"table_schema": "prata"', contexto)
        schema = agente.listar_schema()
        self.assertEqual({coluna['table_schema'] for coluna in schema}, {'prata', 'ouro'})

    def test_quatro_consultas_de_referencia_sem_llm(self):
        resultados = [agente.consultar(sql) for sql in CONSULTAS]
        self.assertEqual(resultados[0][0]['categoria'], 'Poetry')
        self.assertEqual(resultados[0][0]['valor_brl'], Decimal('25543.87'))
        self.assertEqual(resultados[1][0]['quantidade'], 3)
        self.assertEqual(resultados[2][0]['quantidade'], 40)
        self.assertEqual({linha['faixa_preco'] for linha in resultados[3]}, {'até £20', '£20–40', 'acima de £40'})
        print('Referências SQL (não são aceite do LLM):', resultados)


if __name__ == '__main__':
    unittest.main()
