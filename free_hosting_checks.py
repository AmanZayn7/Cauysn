"""Offline checks for the free-hosting adapter. Not a hosted database test."""
import os
import unittest
from unittest.mock import MagicMock,patch
from deployment_config import WebSettings
from web_access import PostgresAccessStore,create_access_store

DSN='postgresql://causyn_web:test-only@db.example/neondb?sslmode=require'

class FreeHostingChecks(unittest.TestCase):
    def test_state_credentials_are_separate(self):
        for user in ('neondb_owner','causyn_reader'):
            with self.assertRaises(ValueError):PostgresAccessStore(DSN.replace('causyn_web',user))
        with self.assertRaises(ValueError):PostgresAccessStore(DSN.replace('require','disable'))

    def test_store_selection_never_creates_schema_or_connects(self):
        with patch.dict(os.environ,{'CAUSYN_STATE_DATABASE_URL':DSN}),patch('psycopg.connect') as connect:
            store=create_access_store('/not-used')
        self.assertIsInstance(store,PostgresAccessStore)
        connect.assert_not_called()

    def test_render_origin_auto_config(self):
        with patch.dict(os.environ,{'CAUSYN_ENV':'production','CAUSYN_LIVE_ENABLED':'false',
            'RENDER_EXTERNAL_URL':'https://causyn.onrender.com','CAUSYN_ACCESS_CODE':'test-only-private-code-32-chars'},clear=True):
            settings=WebSettings()
            self.assertEqual(settings.origin,'https://causyn.onrender.com')
            self.assertTrue(settings.secure_cookie)

    def test_free_live_cannot_use_ephemeral_sqlite(self):
        with patch.dict(os.environ,{'CAUSYN_ENV':'production','CAUSYN_LIVE_ENABLED':'true',
            'CAUSYN_REQUIRE_DURABLE_STATE':'true'},clear=True):
            with self.assertRaisesRegex(ValueError,'CAUSYN_STATE_DATABASE_URL'):WebSettings()

    def test_quota_uses_transaction_lock_and_does_not_charge_denied_admission(self):
        store=PostgresAccessStore(DSN)
        connection=MagicMock();connection.execute.return_value.fetchone.return_value=(20,)
        with patch.object(store,'connection') as factory:
            factory.return_value.__enter__.return_value=connection
            self.assertFalse(store.admit('owner-digest',20,5))
        queries=[call.args[0] for call in connection.execute.call_args_list]
        self.assertTrue(queries[0].startswith('SELECT pg_advisory_xact_lock'))
        self.assertFalse(any(query.startswith('INSERT') for query in queries))

    def test_persistent_chart_is_owner_scoped(self):
        store=PostgresAccessStore(DSN);connection=MagicMock()
        connection.execute.return_value.fetchone.return_value=('<html>verified</html>',)
        with patch.object(store,'connection') as factory:
            factory.return_value.__enter__.return_value=connection
            self.assertEqual(store.get_chart('owner-hash','chart.html'),'<html>verified</html>')
        query,params=connection.execute.call_args.args
        self.assertIn('owner=%s AND name=%s',query)
        self.assertEqual(params[:2],('owner-hash','chart.html'))

    def test_invalid_chart_is_rejected_before_connection(self):
        store=PostgresAccessStore(DSN)
        with patch.object(store,'connection') as connection:
            with self.assertRaises(ValueError):store.save_chart('owner','../escape.html','contents')
            with self.assertRaises(ValueError):store.save_chart('owner','chart.html','x'*2_000_001)
        connection.assert_not_called()

    def test_plain_cookie_not_saved(self):
        store=PostgresAccessStore(DSN);connection=MagicMock()
        with patch.object(store,'connection') as factory:
            factory.return_value.__enter__.return_value=connection
            token=store.new_session()
        params=connection.execute.call_args.args[1]
        self.assertEqual(params[0],store.digest(token))
        self.assertNotEqual(params[0],token)

if __name__=='__main__':unittest.main(verbosity=2)
