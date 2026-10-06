"""Offline regressions for the supported chart prompt's omitted period totals."""
import copy
import json
import unittest
from decimal import Decimal
from answer_completeness import add_period_totals
from depth_contracts import SCOPE, months_in_range
from evaluate_depth import synthetic
from verification import check_numerical_claims
from agent import verify_final_response
from verifier_specialist import build_packet


class TotalsTests(unittest.TestCase):
    def setUp(self):
        self.event=synthetic('get_monthly_trend')
        self.draft={'answer':'The monthly trend chart shows an observed decline, not a proven cause.', 'claims':[]}

    def complete(self):
        return add_period_totals(self.draft,[self.event])

    def test_omitted_totals_are_added_before_verification(self):
        result=verify_final_response(json.dumps(self.draft),[self.event])
        self.assertIn('R$ 100.00',result['answer'])
        self.assertIn('Delivered orders: 10',result['answer'])
        self.assertEqual(result['numerical_check']['status'],'PASS')
        self.assertEqual(result['evidence_check']['status'],'PASS')
        self.assertEqual(len(result['claims']),2)

    def test_original_twenty_month_prompt_baseline_formatting(self):
        # Synthetic row distribution: tests the established baseline's formatting
        # and coverage, not the real database or its monthly distribution.
        event=copy.deepcopy(self.event);args={'start_month':'2017-01','end_month':'2018-08'}
        event['arguments']=args;data=event['result'];data.update(args)
        rows=[]
        for index,month in enumerate(months_in_range(**args)):
            n=100 if index<19 else 94311
            value=Decimal('100') if index<19 else Decimal('13179127.13')
            rows.append({'purchase_month':month,'delivered_orders':n,
                         'delivered_merchandise_value':str(value),
                         'average_merchandise_value_per_order':str(value/n),
                         'assessable_delivery_orders':n,'late_orders':0,'late_delivery_pct':'0'})
        data['rows']=rows
        data['reference']={'delivered_orders':96211,'delivered_merchandise_value':'13181027.13',
                           'assessable_delivery_orders':96211,'late_orders':0}
        result=verify_final_response(json.dumps(self.draft),[event])
        self.assertIn('13,181,027.13',result['answer']);self.assertIn('96,211',result['answer'])
        self.assertIn('2017-01 through 2018-08',result['answer'])

    def test_tampered_reference_is_not_reported(self):
        self.event['result']['reference']['delivered_merchandise_value']='101'
        with self.assertRaises(RuntimeError):verify_final_response(json.dumps(self.draft),[self.event])

    def test_reviewer_receives_completed_answer_and_checked_claims(self):
        draft=verify_final_response(json.dumps(self.draft),[self.event])
        packet=build_packet('Create a monthly trend chart and report period totals.',draft)
        self.assertIn('Delivered orders: 10',packet['draft_answer'])
        self.assertEqual(len(packet['structured_claims']),2)
        self.assertEqual(packet['local_checks']['numerical_check']['status'],'PASS')

    def test_wrong_period_unit_and_value_claims_rejected(self):
        for field,value in [('start_month','2017-10'),('unit','percent'),('value','101.00'),
                            ('aggregation','sum_all_rows'),('category_label','a'),('scope','profit')]:
            payload=self.complete();payload['claims'][0][field]=value
            self.assertEqual(check_numerical_claims({**payload,'evidence':[self.event]})['status'],'FAIL')

    def test_invalid_existing_claim_is_not_silently_repaired(self):
        self.draft['claims']=[{**self.event['arguments'],'aggregation':'period_total','scope':SCOPE,
                              'evidence_index':0,'metric':'delivered_orders','unit':'orders','value':'999'}]
        with self.assertRaises(RuntimeError):verify_final_response(json.dumps(self.draft),[self.event])

    def test_original_prose_is_preserved_for_reviewer(self):
        self.draft['answer']='A promotion caused the decline. Total: 999.'
        self.assertTrue(self.complete()['answer'].startswith(self.draft['answer']))

    def test_non_depth_answers_unchanged(self):
        self.assertEqual(add_period_totals(self.draft,[]),self.draft)

    def test_failed_tool_does_not_fabricate_totals(self):
        self.event['result']={'error':'failed'}
        self.assertEqual(self.complete(),self.draft)

    def test_category_totals_use_reference_not_overlapping_orders(self):
        event=synthetic('get_category_performance')
        result=verify_final_response(json.dumps(self.draft),[event])
        self.assertIn('Delivered orders: 10',result['answer'])
        self.assertNotIn('Delivered orders: 7',result['answer'])
        self.assertEqual(result['numerical_check']['status'],'PASS')

    def test_same_period_is_reported_once_and_input_unmodified(self):
        original=copy.deepcopy(self.draft)
        payload=add_period_totals(self.draft,[self.event,copy.deepcopy(self.event)])
        self.assertEqual(payload['answer'].count('Tool-backed period totals:'),1)
        self.assertEqual(self.draft,original)

    def test_conflicting_valid_range_references_rejected(self):
        second=synthetic('get_monthly_trend');row=second['result']['rows'][0]
        row['delivered_merchandise_value']='61';row['average_merchandise_value_per_order']='12.2'
        second['result']['reference']['delivered_merchandise_value']='101'
        with self.assertRaises(ValueError):add_period_totals(self.draft,[self.event,second])


if __name__=='__main__': unittest.main(verbosity=2)
