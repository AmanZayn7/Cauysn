"""Add validated range totals to a draft before its normal checks and AI review.

No database, model request, fabricated total, or automatic rewrite of model
claims. Incorrect existing claims/prose remain visible to the original checks.
"""
from decimal import Decimal, ROUND_HALF_UP
from depth_contracts import TOOLS, SCOPE, validate_result


def add_period_totals(payload, evidence):
    answer=payload['answer']
    claims=list(payload['claims'])
    periods={}
    for index,event in enumerate(evidence):
        tool=event.get('tool'); data=event.get('result')
        if tool not in TOOLS or not isinstance(data,dict) or 'error' in data:
            continue
        validate_result(tool,data,event.get('arguments',{}))
        period=(data['start_month'],data['end_month'])
        reference=data['reference']
        pair=(Decimal(str(reference['delivered_merchandise_value'])),int(reference['delivered_orders']))
        if period in periods:
            if periods[period]!=pair:
                raise ValueError('Range tools disagree on period totals.')
            continue
        periods[period]=pair
        money=pair[0].quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        answer+=(f'\n\n### Tool-backed period totals: {period[0]} through {period[1]}\n'
                 f'\n- Delivered merchandise value: R$ {money:,.2f} (BRL)'
                 f'\n- Delivered orders: {pair[1]:,}'
                 '\n\nThese totals cover all delivered orders grouped by purchase month, '
                 'not just groups plotted in a ranking. Merchandise excludes freight '
                 'and is not profit or corporate revenue.'
                 f' Source: {data.get("source","reporting tool evidence")}.')
        for metric,unit,value in (
                ('delivered_merchandise_value','BRL',str(money)),
                ('delivered_orders','orders',str(pair[1]))):
            claim={'evidence_index':index,'aggregation':'period_total',
                   'start_month':period[0],'end_month':period[1],
                   'metric':metric,'unit':unit,'scope':SCOPE,'value':value}
            if claim not in claims:
                claims.append(claim)
    return {'answer':answer,'claims':claims}
