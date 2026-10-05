"""Run expanded-analysis checks without API calls; optional one-case live check.

python evaluate_depth.py --self-test
python evaluate_depth.py --database
python evaluate_depth.py --live --case trend
"""
import argparse
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from depth_contracts import TOOLS, SCOPE, validate_result, validate_range
from verification import check_numerical_claims, check_numerical_evidence
import depth_visuals
from visualization_specialist import build_spec,check_chart,save_chart

QUESTIONS={
 'trend':'Create a monthly merchandise value trend chart from 2017-01 through 2018-08. Report the first and last month values. Do not forecast or infer causes.',
 'categories':'Create a category ranking chart for 2017-11 through 2017-12 by delivered merchandise value. Report the three leading categories and their merchandise values.',
 'sellers':'Create a seller ranking chart for 2017-11 through 2017-12 by delivered merchandise value. Report the leading anonymized seller ID, merchandise value and item count.',
 'states':'Create a late-delivery-rate chart by customer destination state for 2018-03. Report the state with the highest rate among states with at least 30 assessable delivered orders, its rate and denominator. Disclose the chart coverage threshold; do not infer causes.',
}


def synthetic(tool):
 args={'start_month':'2017-11','end_month':'2017-12'}
 common={**args,'currency':'BRL','scope':SCOPE,'source':'synthetic test reference','interpretation':'Arithmetic evidence, not proven causes.',
    'reference':{'delivered_orders':10,'delivered_merchandise_value':'100','assessable_delivery_orders':8,'late_orders':2}}
 if tool=='get_monthly_trend':
  rows=[{'purchase_month':month,'delivered_orders':5,'delivered_merchandise_value':v,
     'average_merchandise_value_per_order':str(Decimal(v)/5),'assessable_delivery_orders':4,'late_orders':1,'late_delivery_pct':'25'} for month,v in [('2017-11','60'),('2017-12','40')]]
 elif tool=='get_state_delivery':
  rows=[{'customer_state':'SP','delivered_orders':10,'assessable_delivery_orders':8,'late_orders':2,'late_delivery_pct':'25'}]
 else:
  key='category_label' if tool=='get_category_performance' else 'seller_id';orders='orders_containing_category' if tool=='get_category_performance' else 'orders_containing_seller'
  rows=[{key:'a','merchandise_value':'60','items_sold':6,orders:4,'average_item_value':'10'},
        {key:'b','merchandise_value':'40','items_sold':4,orders:3,'average_item_value':'10'}]
  common.update(ranking_limit=10,total_groups=2,all_items_sold=10,other_merchandise_value='0',other_items_sold=0)
 return {'tool':tool,'arguments':args,'result':{**common,'rows':rows}}


class DepthTests(unittest.TestCase):
 def test_all_contracts_and_claims(self):
  for tool,(key,units) in TOOLS.items():
   event=synthetic(tool);data=event['result'];validate_result(tool,data,event['arguments']);metric=next(iter(units))
   value=Decimal(str(data['rows'][0][metric]));unit=units[metric]
   claim={**event['arguments'],key:data['rows'][0][key],'metric':metric,'unit':unit,'value':str(value.quantize(Decimal('.01'))) if unit not in ('orders','items') else str(value),'scope':SCOPE,'evidence_index':0}
   result={'evidence':[event],'claims':[claim]}
   self.assertEqual(check_numerical_claims(result)['status'],'PASS');self.assertEqual(check_numerical_evidence(result)['status'],'PASS')
   claim[key]='invented';self.assertEqual(check_numerical_claims(result)['status'],'FAIL')
 def test_range_validation(self):
  for pair in [('2018-02','2017-01'),('2026-01','2026-02'),('2017-1','2017-12'),("2017-01'; DROP TABLE x;--",'2017-12')]:
   with self.assertRaises(ValueError):validate_range(*pair)
 def test_duplicate_group(self):
  e=synthetic('get_state_delivery');e['result']['rows']*=2
  self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'FAIL')
 def test_denominator_and_rate_tampering(self):
  for key,value in [('assessable_delivery_orders',1),('late_delivery_pct','30'),('late_orders',True)]:
   e=synthetic('get_state_delivery');e['result']['rows'][0][key]=value
   self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'FAIL')
 def test_zero_coverage(self):
  e=synthetic('get_state_delivery');d=e['result'];d['rows'][0].update(assessable_delivery_orders=0,late_orders=0,late_delivery_pct=None);d['reference'].update(assessable_delivery_orders=0,late_orders=0)
  self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'PASS')
  d['rows'][0]['late_delivery_pct']='0';self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'FAIL')
 def test_ranking_partition_and_order(self):
  for tool in ('get_category_performance','get_seller_performance'):
   e=synthetic(tool);e['result']['rows'].reverse();self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'FAIL')
   e=synthetic(tool);e['result']['other_merchandise_value']='1';self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'FAIL')
 def test_chronology_and_missing_month(self):
  e=synthetic('get_monthly_trend');e['result']['rows'].reverse();self.assertEqual(check_numerical_evidence({'evidence':[e]})['status'],'FAIL')
 def test_money_and_count_units(self):
  e=synthetic('get_seller_performance');claim={**e['arguments'],'seller_id':'a','metric':'items_sold','unit':'items','value':'6.1','scope':SCOPE,'evidence_index':0}
  self.assertEqual(check_numerical_claims({'evidence':[e],'claims':[claim]})['status'],'FAIL')
 def test_chart_mappings_and_tampering(self):
  for kind,tool in depth_visuals.CHART_TOOLS.items():
   e=synthetic(tool)
   if kind=='state_delivery':
    e['result']['rows'][0].update(delivered_orders=50,assessable_delivery_orders=40,late_orders=10)
    e['result']['reference'].update(delivered_orders=50,assessable_delivery_orders=40,late_orders=10)
   plan={'chart_kind':kind,**e['arguments']};spec=build_spec(plan,[e])
   self.assertEqual(check_chart(spec,[e])['status'],'PASS')
   with tempfile.TemporaryDirectory() as temp:
    artifact=save_chart(spec,[e],temp);text=Path(artifact['path']).read_text();self.assertIn('<svg',text);self.assertNotIn('<script',text)
   bad=copy.deepcopy(spec);bad['rows'][0]['value']='999';self.assertEqual(check_chart(bad,[e])['status'],'FAIL')
 def test_small_state_samples_omitted(self):
  e=synthetic('get_state_delivery')
  with self.assertRaises(ValueError):build_spec({'chart_kind':'state_delivery',**e['arguments']},[e])
 def test_sql_new_range_plans(self):
  from sql_specialist import validate_plan
  for tool in TOOLS:self.assertEqual(len(validate_plan({'operations':[{'tool':tool,'arguments':{'start_month':'2017-11','end_month':'2017-12'}}]})),1)
  with self.assertRaises(ValueError):validate_plan({'operations':[{'tool':'get_monthly_trend','arguments':{'start_month':'2017-12','end_month':'2017-11'}}]})


def database_checks():
 from depth_tools import FUNCTIONS
 events=[]
 for tool,func in FUNCTIONS.items():
  args={'start_month':'2017-01','end_month':'2018-08'};data=func(**args)
  expected={'delivered_orders':96211,'delivered_merchandise_value':Decimal('13181027.13'),'assessable_delivery_orders':96203,'late_orders':6531}
  if data['reference']!=expected:raise ValueError('Monthly reference differs from established audit baseline.')
  event={'tool':tool,'arguments':args,'result':data};events.append(event)
  kind=next(k for k,v in depth_visuals.CHART_TOOLS.items() if v==tool)
  artifact=save_chart(build_spec({'chart_kind':kind,**args},[event]),[event])
  print('PASS:',tool,'known baseline, reconciliation and saved chart:',artifact['path'])
 return {'evidence':events,'evidence_check':check_numerical_evidence({'evidence':events})}


def live_check(case):
 from agent import answer_question
 result=answer_question(QUESTIONS[case]);kind={'trend':'monthly_trend','categories':'category_ranking','sellers':'seller_ranking','states':'state_delivery'}[case]
 for key in ('numerical_check','evidence_check','chart_check'):
  if result.get(key,{}).get('status')!='PASS':raise ValueError(key+' did not pass.')
 if result.get('ai_review',{}).get('verdict')!='PASS':raise ValueError('AI reviewer did not approve.')
 charts=[e['result']['specification'] for e in result['evidence'] if e.get('tool')=='render_chart']
 if len(charts)!=1 or charts[0]['chart_kind']!=kind:raise ValueError('Wrong or missing chart.')
 expected=('2018-03','2018-03') if case=='states' else ('2017-01','2018-08') if case=='trend' else ('2017-11','2017-12')
 if (charts[0]['start_month'],charts[0]['end_month'])!=expected:raise ValueError('Wrong chart reporting range.')
 print('PASS:',case,'live source checks and AI review. Manual answer review remains necessary.')
 print('\nANSWER\n'+result['answer']);print('\nUSAGE\n'+json.dumps(result['usage'],default=str,indent=2))
 return result


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--self-test',action='store_true');group.add_argument('--database',action='store_true');group.add_argument('--live',action='store_true')
 parser.add_argument('--case',choices=QUESTIONS,default='trend');args=parser.parse_args()
 if args.self_test:
  sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DepthTests)).wasSuccessful() else 1)
 try:
  result=database_checks() if args.database else live_check(args.case)
  directory=Path(__file__).parent/'evaluations'/'results';directory.mkdir(parents=True,exist_ok=True)
  path=directory/('depth_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
  path.write_text(json.dumps(result,default=str,indent=2));print('Report saved:',path)
 except Exception as error:
  print('FAIL:',str(error),file=sys.stderr);sys.exit(1)
