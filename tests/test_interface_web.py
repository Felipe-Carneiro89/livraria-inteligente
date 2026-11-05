from importlib import import_module
import json
import os
from pathlib import Path
import sys
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PASTA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PASTA))
interface = import_module('06_interface_web')


class TestesInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = interface.ServidorLocal(('127.0.0.1', 0), interface.Rotas)
        cls.url = f'http://127.0.0.1:{cls.servidor.server_port}'
        cls.thread = Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.thread.join(timeout=5)

    def test_pagina_e_saude_sem_chave(self):
        with urlopen(self.url) as resposta:
            self.assertEqual(resposta.status, 200)
            pagina = resposta.read().decode('utf-8')
            self.assertIn('Um novo olhar para os livros.', pagina)
            self.assertIn('CHAT AGUARDANDO CONFIGURAÇÃO', pagina)
            self.assertIn('id="pergunta-chat" disabled', pagina)
        with urlopen(self.url + '/api/saude') as resposta:
            self.assertEqual(json.load(resposta)['llm'], 'aguardando_configuracao')

    def test_nao_expoe_arquivos_ou_sql_arbitrario(self):
        for caminho in ['/.env', '/SPEC.md', '/../.env', '/api/consultar?sql=select+1']:
            with self.subTest(caminho=caminho), self.assertRaises(HTTPError) as erro:
                urlopen(self.url + caminho)
            self.assertEqual(erro.exception.code, 404)
        with self.assertRaises(HTTPError) as erro:
            urlopen(Request(self.url + '/api/painel', data=b'{"sql":"delete from ouro.livros"}', method='POST'))
        self.assertEqual(erro.exception.code, 405)

    def test_falha_nao_expoe_credencial(self):
        with patch.object(interface, 'carregar_painel', side_effect=RuntimeError('senha-simulada-nao-expor')):
            with self.assertRaises(HTTPError) as erro:
                urlopen(self.url + '/api/painel')
            self.assertEqual(erro.exception.code, 503)
            corpo = erro.exception.read().decode('utf-8')
            self.assertNotIn('senha-simulada-nao-expor', corpo)
            self.assertIn('Não foi possível consultar o banco', corpo)

    def test_consultas_fixas_usam_guardrails(self):
        consultas = [c['sql'] for c in interface.CONSULTAS.values()] + [interface.SQL_CATEGORIAS, interface.SQL_LIVROS]
        for sql in consultas:
            sem_comentarios = '\n'.join(linha.partition('--')[0] for linha in sql.splitlines())
            self.assertTrue(interface.agente.validar_sql(sem_comentarios).endswith('LIMIT 50'))

    @unittest.skipUnless(os.getenv('VALIDAR_BANCO') == '1', 'Integração opcional com Supabase')
    def test_painel_real_sem_llm(self):
        with patch.object(interface.agente, 'chamar_llm', side_effect=AssertionError('LLM não deve ser chamado')) as llm:
            with urlopen(self.url + '/api/painel', timeout=45) as resposta:
                self.assertEqual(resposta.status, 200)
                painel = json.load(resposta)
            consultas = painel['consultas']
            self.assertEqual(consultas['livros_unicos']['linhas'], [{'quantidade': 40}])
            self.assertEqual(consultas['bem_avaliados']['linhas'], [{'quantidade': 3}])
            self.assertEqual(consultas['maior_estoque']['linhas'], [{'categoria': 'Poetry', 'valor_estoque_brl': '25543.87'}])
            self.assertEqual(len(consultas['precos_por_faixa']['linhas']), 3)
            self.assertEqual(len(painel['livros']), 40)
            self.assertLessEqual(len(painel['categorias']), 50)
            self.assertFalse(any(c['categoria'] == 'Sem categoria' for c in painel['categorias']))
            self.assertFalse(painel['llm']['disponivel'])
            llm.assert_not_called()
            print('HTTP + Supabase: 40 livros, 3 bem avaliados, Poetry R$ 25.543,87 e 3 faixas; nenhuma chamada LLM.')


if __name__ == '__main__':
    unittest.main()
