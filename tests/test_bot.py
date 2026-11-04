from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import bot
from main import create_app
from pc_builder.catalog import CATALOG
from pc_builder.prices import Quote, SourceUnavailable


class BotTests(unittest.TestCase):
    def test_budget_accepts_plain_and_turkish_number_formats(self):
        for value, expected in (('40000', '40000'), ('40.000', '40000'), ('40.000,50', '40000.50'), ('40000.50', '40000.50')):
            with self.subTest(value=value):
                self.assertEqual(bot.arguments(['--budget', value]).budget, Decimal(expected))

    def test_invalid_arguments_are_rejected_before_network_work(self):
        for args in (['--budget', 'NaN'], ['--budget', '14999'], ['--budget', '150001'],
                     ['--budget', '20000.001'], ['--port', '-1'], ['--port', '65536'],
                     ['--resolution', '8k'], ['--output', 'file.json']):
            with self.subTest(args=args), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                bot.arguments(args)
            self.assertEqual(error.exception.code, 2)

    def test_cli_prints_links_and_writes_valid_json(self):
        source = Mock()
        now = datetime.now(timezone.utc).isoformat()
        url = 'https://www.akakce.com/ekran-karti/en-ucuz-test-fiyati,12345.html'
        source.quotes.return_value = {part.id: Quote(Decimal('3000.25'), url, part.name, now) for part in CATALOG}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'build.json'
            args = bot.arguments(['--budget', '40.000', '--resolution', '1440p', '--output', str(output)])
            terminal = StringIO()
            with redirect_stdout(terminal):
                self.assertEqual(bot.run_cli(args, source=source), 0)
            result = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(len(result['parts']), 7)
        self.assertLessEqual(result['total'], 40000)
        self.assertIn(url, terminal.getvalue())
        self.assertIn('21.001,75 TL', terminal.getvalue())

    def test_source_failure_does_not_create_output_or_leak_details(self):
        source = Mock()
        source.quotes.side_effect = SourceUnavailable('private connection details')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'build.json'
            args = bot.arguments(['--budget', '40000', '--output', str(output)])
            errors = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(errors):
                self.assertEqual(bot.run_cli(args, source=source), 2)
            self.assertFalse(output.exists())
            self.assertNotIn('private', errors.getvalue())

    def test_existing_user_file_is_preserved_without_fetching(self):
        source = Mock()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'build.json'
            output.write_text('my existing data', encoding='utf-8')
            args = bot.arguments(['--budget', '40000', '--output', str(output)])
            with redirect_stderr(StringIO()):
                self.assertEqual(bot.run_cli(args, source=source), 4)
            self.assertEqual(output.read_text(encoding='utf-8'), 'my existing data')
            source.quotes.assert_not_called()

    def test_local_server_binds_only_loopback_and_restricts_host(self):
        app = create_app()
        server = Mock()
        server.server_port = 8765
        server.__enter__ = Mock(return_value=server)
        server.__exit__ = Mock(return_value=False)
        factory = Mock(return_value=server)
        with redirect_stdout(StringIO()):
            self.assertEqual(bot.run_web(bot.arguments(['--no-browser']), app, factory), 0)
        factory.assert_called_once_with('127.0.0.1', 8765, app, threaded=True)
        self.assertEqual(app.test_client().get('/api/health', headers={'Host': 'untrusted.example'}).status_code, 400)
        self.assertEqual(app.test_client().get('/api/health', headers={'Host': '127.0.0.1:8765'}).status_code, 200)

    def test_port_conflict_has_actionable_error(self):
        errors = StringIO()
        with redirect_stderr(errors):
            code = bot.run_web(bot.arguments(['--no-browser']), create_app(), Mock(side_effect=OSError))
        self.assertEqual(code, 4)
        self.assertIn('--port 0', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
