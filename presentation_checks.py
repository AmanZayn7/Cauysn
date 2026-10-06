"""Offline saved-report formatting, dark theme, escaping and source checks."""
import copy
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from chart_presentation import nice_ticks, compact, category_label
from evaluate_depth import synthetic
from visualization_specialist import build_spec, check_chart, save_chart, render_svg
from deployment_config import WebSettings
from web_access import AccessStore
warnings.filterwarnings('ignore', message='Using `httpx` with `starlette.testclient` is deprecated.*')
from starlette.testclient import TestClient
from web_app import create_app


class PresentationChecks(unittest.TestCase):
    def test_round_ticks_and_consistent_suffixes(self):
        _,high,ticks=nice_ticks(0,'987765.37')
        self.assertEqual(str(high),'1250000.0')
        self.assertEqual([compact(v) for v in ticks],['0','250k','500k','750k','1M','1.25M'])

    def test_category_sentence_case(self):
        self.assertEqual(category_label('garden_tools'),'Garden tools')
        self.assertEqual(category_label('sports_leisure'),'Sports leisure')

    def test_dark_saved_chart_and_safe_back_link(self):
        event=synthetic('get_monthly_trend');plan={'chart_kind':'monthly_trend',**event['arguments']}
        spec=build_spec(plan,[event])
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'CAUSYN_PUBLIC_ORIGIN':'https://causyn.example'}):
            artifact=save_chart(spec,[event],directory)
            text=Path(artifact['path']).read_text()
            self.assertIn('background:#0e0d17',text)
            self.assertIn('fill="#b4bfd3"',text)
            self.assertIn('href="https://causyn.example"',text)
            self.assertIn('Back to Causyn',text)
            self.assertEqual(artifact['specification'],spec)
            self.assertEqual(artifact['chart_check']['status'],'PASS')

    def test_invalid_back_link_cannot_inject_script(self):
        event=synthetic('get_monthly_trend');spec=build_spec({'chart_kind':'monthly_trend',**event['arguments']},[event])
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'CAUSYN_PUBLIC_ORIGIN':'javascript:alert(1)'}):
            text=Path(save_chart(spec,[event],directory)['path']).read_text()
            self.assertNotIn('javascript:',text)
            self.assertIn('href="https://causyn.onrender.com"',text)

    def test_display_labels_do_not_change_evidence_or_mapping(self):
        event=synthetic('get_category_performance')
        event['result']['rows'][0]['category_label']='garden_tools'
        event['result']['rows'][1]['category_label']='sports_leisure'
        original=copy.deepcopy(event)
        spec=build_spec({'chart_kind':'category_ranking',**event['arguments']},[event])
        svg=render_svg(spec)
        self.assertIn('Garden tools',svg);self.assertIn('garden_tools',svg)
        self.assertEqual(event,original);self.assertEqual(check_chart(spec,[event])['status'],'PASS')

    def test_new_static_script_is_allowlisted_and_ordered(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'CAUSYN_ENV':'local','CAUSYN_PUBLIC_LIVE':'false','CAUSYN_ACCESS_CODE':''},clear=True):
            app=create_app(WebSettings(),AccessStore(Path(directory)/'state.sqlite3'))
            with TestClient(app,base_url='http://127.0.0.1:8765') as client:
                page=client.get('/').text
                self.assertLess(page.index('/presentation.js'),page.index('/app.js'))
                response=client.get('/presentation.js');self.assertEqual(response.status_code,200)
                self.assertIn('CausynPresentation',response.text)


if __name__=='__main__':unittest.main(verbosity=2)
