"""Offline deployment regression tests. No database, Gemini requests or Docker needed."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings
# Retain the project's existing httpx; the web framework still supports it here.
warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")
from unittest.mock import patch

from starlette.testclient import TestClient
from deployment_config import WebSettings, database_options
from web_access import AccessStore
import web_app


class DeploymentChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            'CAUSYN_ENV': 'production', 'CAUSYN_PUBLIC_ORIGIN': 'https://causyn.example',
            'CAUSYN_ACCESS_CODE': 'test-only-access-code-with-32-characters',
            'CAUSYN_LIVE_ENABLED': 'true', 'GEMINI_API_KEY': 'test-only-no-network',
            'DATABASE_URL': 'postgresql://causyn_reader:private-test-password@db.example/causyn?sslmode=verify-full',
            'CAUSYN_RUNTIME_DIR': self.temp.name, 'CAUSYN_DAILY_LIVE_LIMIT': '2',
            'CAUSYN_HOURLY_SESSION_LIMIT': '2'}, clear=True)
        self.environment.start()
        web_app.JOBS.clear(); web_app.JOB_OWNERS.clear(); web_app.JOB_CREATED.clear()
        self.store = AccessStore(Path(self.temp.name) / 'state' / 'access.sqlite3')
        self.settings = WebSettings()
        self.client = TestClient(web_app.create_app(self.settings, self.store), base_url=self.settings.origin)
        self.origin = {'Origin': self.settings.origin}

    def tearDown(self):
        self.client.close()
        self.environment.stop()
        self.temp.cleanup()
        web_app.JOBS.clear(); web_app.JOB_OWNERS.clear(); web_app.JOB_CREATED.clear()

    def post(self, path, payload):
        return self.client.post(path, json=payload, headers=self.origin)

    def login(self):
        response = self.post('/api/login', {'access_code': self.settings.access_code})
        self.assertEqual(response.status_code, 200)
        return response

    def start_live(self):
        # No worker thread or external network call is allowed in this suite.
        with patch('web_app.threading.Thread') as worker:
            response = self.post('/api/investigate', {'mode': 'live', 'question': 'Compare 2017-11 and 2017-12'})
        return response, worker

    def test_production_requires_https_and_secret(self):
        with patch.dict(os.environ, {'CAUSYN_PUBLIC_ORIGIN': 'http://causyn.example'}):
            with self.assertRaises(ValueError): WebSettings()
        with patch.dict(os.environ, {'CAUSYN_ACCESS_CODE': 'short'}):
            with self.assertRaises(ValueError): WebSettings()

    def test_production_requires_database_tls(self):
        with patch.dict(os.environ, {'DATABASE_URL':'postgresql://causyn_reader@db.example/causyn?sslmode=disable'}):
            with self.assertRaises(ValueError): WebSettings()

    def test_production_requires_live_credentials(self):
        with patch.dict(os.environ, {'DATABASE_URL': ''}):
            with self.assertRaises(ValueError): WebSettings()

    def test_health_makes_no_agent_import(self):
        self.assertEqual(self.client.get('/healthz').json(), {'status': 'ok'})

    def test_host_and_origin_rejected(self):
        self.assertEqual(self.client.get('/api/config', headers={'Host':'evil.example'}).status_code, 403)
        response = self.client.post('/api/login', json={'access_code': self.settings.access_code}, headers={'Origin':'https://evil.example'})
        self.assertEqual(response.status_code, 403)

    def test_security_headers(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        for name in ('content-security-policy','x-content-type-options','referrer-policy','strict-transport-security'):
            self.assertIn(name, response.headers)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_public_config_contains_no_credentials(self):
        response = self.client.get('/api/config')
        for secret in (self.settings.access_code, os.environ['GEMINI_API_KEY'], 'private-test-password'):
            self.assertNotIn(secret, response.text)
        self.assertFalse(response.json()['authenticated'])

    def test_public_demo_is_zero_api_and_no_job(self):
        response = self.post('/api/investigate', {'mode':'demo', 'demo_id':'definition', 'question':web_app.PRESETS['definition']['question']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['usage']['api_requests'], 0)
        self.assertTrue(response.json()['result']['is_demo'])
        self.assertFalse(web_app.JOBS)

    def test_demo_cannot_smuggle_custom_question(self):
        response = self.post('/api/investigate', {'mode':'demo','demo_id':'definition','question':'Run a paid investigation'})
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_live_cannot_start_worker(self):
        response, worker = self.start_live()
        self.assertEqual(response.status_code, 401)
        worker.assert_not_called()

    def test_bad_access_code_and_login_throttle(self):
        for _ in range(10):
            self.assertEqual(self.post('/api/login', {'access_code':'wrong'}).status_code, 401)
        self.assertEqual(self.post('/api/login', {'access_code':self.settings.access_code}).status_code, 429)

    def test_secure_http_only_cookie(self):
        cookie = self.login().headers['set-cookie'].lower()
        for flag in ('httponly', 'secure', 'samesite=strict'):
            self.assertIn(flag, cookie)
        self.assertTrue(self.client.get('/api/config').json()['authenticated'])

    def test_logout_revokes_copied_cookie(self):
        self.login()
        copied = self.client.cookies.get('causyn_session')
        self.assertEqual(self.client.post('/api/logout',headers=self.origin).status_code,200)
        self.client.cookies.set('causyn_session', copied)
        self.assertFalse(self.client.get('/api/config').json()['authenticated'])

    def test_authenticated_job_is_private_to_issuing_session(self):
        self.login()
        response, worker = self.start_live()
        self.assertEqual(response.status_code, 202)
        worker.return_value.start.assert_called_once()
        job_id = response.json()['id']
        self.assertEqual(self.client.get('/api/jobs/'+job_id).status_code, 200)
        self.login()  # A second owner session does not inherit the first job.
        self.assertEqual(self.client.get('/api/jobs/'+job_id).status_code, 404)

    def test_concurrent_live_rejected_without_another_worker(self):
        self.login(); self.start_live()
        response, worker = self.start_live()
        self.assertEqual(response.status_code, 409)
        worker.assert_not_called()

    def test_live_disable_overrides_owner_login(self):
        self.login(); self.settings.live=False
        response, worker = self.start_live()
        self.assertEqual(response.status_code, 403)
        worker.assert_not_called()

    def test_daily_limit_survives_store_restart(self):
        self.assertTrue(self.store.admit('first', 2, 10))
        self.assertTrue(self.store.admit('second', 2, 10))
        reopened = AccessStore(self.store.path)
        self.assertFalse(reopened.admit('third', 2, 10))

    def test_session_limit_does_not_block_other_session(self):
        self.assertTrue(self.store.admit('first', 20, 1))
        self.assertFalse(self.store.admit('first', 20, 1))
        self.assertTrue(self.store.admit('second', 20, 1))

    def test_oversized_chunked_and_nonobject_requests_rejected(self):
        response=self.client.post('/api/investigate',content=(b'x'*13000,),headers={**self.origin,'Content-Type':'application/json'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.post('/api/investigate',[]).status_code,400)

    def test_private_chart_requires_owned_result(self):
        self.login(); response,_=self.start_live(); job_id=response.json()['id']
        directory=Path(self.temp.name)/'reports'/'charts'; directory.mkdir(parents=True)
        path=directory/'verified_2017-11_2017-12_abc.html'; path.write_text('<html>verified</html>')
        endpoint='/api/charts/'+path.name
        self.assertEqual(self.client.get(endpoint).status_code,404)
        web_app.JOBS[job_id].update(status='complete', result={'artifacts':[{'path':str(path)}]})
        self.assertEqual(self.client.get(endpoint).status_code,200)
        self.login()
        self.assertEqual(self.client.get(endpoint).status_code,404)

    def test_database_defaults_and_url_override(self):
        with patch.dict(os.environ, {'DATABASE_URL':''}):
            options=database_options()
            self.assertEqual(options['user'],'causyn_reader')
            self.assertEqual(options['host'],'localhost')
        options=database_options()
        self.assertEqual(options['host'],'db.example')
        self.assertEqual(options['sslmode'],'verify-full')
        self.assertEqual(options['connect_timeout'],5)

    def test_zero_decimal_json_round_trip(self):
        from decimal import Decimal
        from analytics_tools import encode_value
        from depth_contracts import number
        encoded=json.dumps({'rate':Decimal('0E-20')},default=encode_value)
        decoded=json.loads(encoded)
        self.assertEqual(number(decoded['rate']),Decimal('0'))
        self.assertNotIn('E-',encoded)

    def test_sessions_expire(self):
        token=self.store.new_session()
        with self.store.connection() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertIsNone(self.store.owner(token))


if __name__ == '__main__':
    unittest.main(verbosity=2)
