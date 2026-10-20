"""Run with python3 -m unittest discover -s tests -p test_sources.py -v."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'sources/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class SourceTests(unittest.TestCase):
    def write_vector(self, samples):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'vector.json'
        path.write_text(json.dumps({'status': 'success', 'data': {'resultType': 'vector', 'result': samples}}))
        return path

    def test_exposition_escaping_and_no_source_timestamp(self):
        sample = {'metric': {'__name__': 'example', 'path': 'a\\b\nc"d'}, 'value': [1792530998.493, '12.5']}
        data = replay.render(replay.load_samples(self.write_vector([sample]))).decode()
        self.assertIn('path="a\\\\b\\nc\\"d"} 12.5\n', data)
        self.assertNotIn('1792530998', data)

    def test_duplicate_series_rejected(self):
        sample = {'metric': {'__name__': 'example', 'host': 'demo'}, 'value': [1, '1']}
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            replay.load_samples(self.write_vector([sample, sample]))

    def test_invalid_names_shape_and_values_rejected(self):
        for sample in [
            {'metric': {'__name__': 'bad name'}, 'value': [1, '1']},
            {'metric': {'__name__': 'good', 'bad-label': 'x'}, 'value': [1, '1']},
            {'metric': {'__name__': 'good'}, 'value': [1, True]},
            {'metric': {'__name__': 'good'}, 'value': [1, 'not-a-number']},
            {'metric': {'__name__': 'good'}, 'value': [1, 'inf']},
        ]:
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                replay.load_samples(self.write_vector([sample]))

    def test_prometheus_nonfinite_spelling(self):
        for value in ('NaN', '+Inf', '-Inf'):
            self.assertEqual(replay.sample_value(value), value)
        with self.assertRaises(ValueError):
            replay.sample_value('Infinity')

    def test_committed_fixtures_match_manifest_and_schema(self):
        manifest = json.loads((replay.FIXTURES / 'manifest.json').read_text())
        expected = {'fhs': 103, 'node': 9989, 'switch': 8641}
        for name, count in expected.items():
            with self.subTest(source=name):
                path = replay.FIXTURES / f'{name}.json'
                samples = replay.load_samples(path)
                record = manifest['sources'][name]
                self.assertEqual(len(samples), count)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['fixture_sha256'])
                self.assertEqual(len({s['metric']['__name__'] for s in samples}), record['metric_names'])
                self.assertEqual(sum(x['series'] for x in record['schema']), count)
                for key, cardinality in record['label_value_cardinality'].items():
                    self.assertEqual(len({s['metric'][key] for s in samples if key in s['metric']}), cardinality, key)
        fhs = replay.load_samples(replay.FIXTURES / 'fhs.json')
        node = replay.load_samples(replay.FIXTURES / 'node.json')
        self.assertEqual({s['metric']['node_name'] for s in fhs}, {'demo-server-01'})
        self.assertEqual({s['metric']['node_name'] for s in node}, {'demo-server-01'})
        self.assertEqual({s['metric']['job'] for s in node}, {'node'})
        self.assertIn('cpu_temperature_celcius', {s['metric']['__name__'] for s in fhs})

    def test_http_each_source_exact_line_count_and_unknown_path(self):
        for name in ('fhs', 'node', 'switch'):
            with self.subTest(source=name):
                samples = replay.load_samples(replay.FIXTURES / f'{name}.json')
                payload = replay.render(samples)
                server = ThreadingHTTPServer(('127.0.0.1', 0), replay.make_handler(payload))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base = f'http://127.0.0.1:{server.server_port}'
                    with urlopen(base + '/metrics') as response:
                        self.assertIn('version=0.0.4', response.headers['Content-Type'])
                        actual = response.read()
                    self.assertEqual(actual, payload)
                    self.assertEqual(len([line for line in actual.splitlines() if not line.startswith(b'#')]), len(samples))
                    with urlopen(base + '/-/ready') as response:
                        self.assertEqual(response.read(), b'OK\n')
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(base + '/not-a-metric')
                    self.assertEqual(failure.exception.code, 404)
                    failure.exception.close()
                finally:
                    server.shutdown()  # Only the in-process test HTTP service, never the host.
                    server.server_close()
                    thread.join()

    @unittest.skipUnless(os.environ.get('PROMETHEUS_ORIGINAL_EXPORT_DIR'), 'Optional private originals are not required by the public bundle')
    def test_exact_numeric_and_schema_parity_with_private_originals(self):
        original_dir = Path(os.environ['PROMETHEUS_ORIGINAL_EXPORT_DIR'])
        for name in ('fhs', 'node', 'switch'):
            with self.subTest(source=name):
                original = replay.load_samples(original_dir / f'{name}-prometheus-sample.json')
                sanitized = replay.load_samples(replay.FIXTURES / f'{name}.json')
                self.assertEqual([s['value'] for s in original], [s['value'] for s in sanitized])
                self.assertEqual([s['metric'].keys() for s in original], [s['metric'].keys() for s in sanitized])
                self.assertEqual([s['metric']['__name__'] for s in original], [s['metric']['__name__'] for s in sanitized])


if __name__ == '__main__':
    unittest.main()
