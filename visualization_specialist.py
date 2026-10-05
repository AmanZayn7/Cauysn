"""Visualization agent: model-selected chart plan, verified data, native SVG/HTML.

No generated code execution or CDN dependency. Saved HTML can be opened offline.
Initial chart capabilities: two-month merchandise bars and volume/value waterfall.
"""
import depth_visuals
import html
import json
import uuid
from decimal import Decimal
from pathlib import Path

from python_specialist import validate_plan as validate_months, decompose_merchandise_change
from verification import _number, check_numerical_evidence

CHART_DIRECTORY = Path(__file__).parent / 'reports' / 'charts'
VISUALIZATION_TOOL = {
    'type':'function', 'name':'investigate_visualization',
    'description':'Create verified charts: monthly merchandise trends, category/seller merchandise ranking bars, state late-rate bars, two-month comparison bars or volume/value waterfall. Supply complete question and YYYY-MM months or inclusive month range. Only verified results are plotted.',
    'parameters':{'type':'object','properties':{'question':{'type':'string','description':'Dated chart request.'}},'required':['question']},
}
PLAN_SCHEMA = {'type':'object','additionalProperties':False,'properties':{
    'chart_kind':{'type':'string','enum':['monthly_comparison','volume_value_waterfall']},
    'baseline_month':{'type':'string'},'comparison_month':{'type':'string'}},
    'required':['chart_kind','baseline_month','comparison_month']}
RULES = """
You are CAUSYN's visualization specialist. Choose a chart for the complete user
request, respecting their explicit baseline and comparison purchase months.
Choose volume_value_waterfall for volume versus average-value contributions;
choose monthly_comparison for two merchandise totals. Return ONLY JSON with
chart_kind, baseline_month and comparison_month. Do not generate values, code,
paths, HTML or SVG. Supported months are 2017-01 through 2018-08. Never invent
dates, causal explanations or statistical significance. The renderer owns layout.
"""


LEGACY_SCHEMA = PLAN_SCHEMA
PLAN_SCHEMA = {'anyOf':[LEGACY_SCHEMA,depth_visuals.SCHEMA]}
RULES += '''\nAlso support monthly_trend (monthly merchandise line), category_ranking or\nseller_ranking (top 10 by delivered merchandise value), and state_delivery\n(customer destination-state late percentages, minimum 30 assessable orders).\nFor these four return chart_kind, start_month, end_month, inclusive YYYY-MM.\nUse identical start/end for a single-month ranking. No other metric or chart\nis supported. Never substitute merchandise rankings for profit rankings.\n'''

def validate_plan(plan):
    if isinstance(plan,dict) and plan.get('chart_kind') in depth_visuals.CHART_TOOLS:
        return depth_visuals.validate_plan(plan)
    if not isinstance(plan,dict) or set(plan) != set(LEGACY_SCHEMA['required']):
        raise ValueError('Unexpected or missing visualization plan fields.')
    if plan['chart_kind'] not in ('monthly_comparison','volume_value_waterfall'):
        raise ValueError('Chart kind is not approved.')
    validate_months({'operation':'decompose_merchandise_change',
        'baseline_month':plan['baseline_month'],'comparison_month':plan['comparison_month']})
    return plan


def build_spec(plan, evidence):
    """Map chart values directly to specific verified evidence metrics."""
    validate_plan(plan)
    if plan['chart_kind'] in depth_visuals.CHART_TOOLS:
        return depth_visuals.build_spec(plan,evidence)
    baseline,comparison = plan['baseline_month'],plan['comparison_month']
    if plan['chart_kind']=='volume_value_waterfall':
        matches=[e['result'] for e in evidence if e.get('tool')=='decompose_merchandise_change'
                 and e.get('arguments')=={'baseline_month':baseline,'comparison_month':comparison}]
        if not matches or any(data != matches[0] for data in matches[1:]):
            raise ValueError('A consistent decomposition result is required.')
        data=matches[0]
        mapping=[(baseline,'baseline_merchandise_value','total'),
                 ('Order volume','volume_effect','change'),
                 ('Average order value','average_value_effect','change'),
                 (comparison,'comparison_merchandise_value','total')]
        rows=[{'label':label,'metric':metric,'value':str(_number(data[metric])),'role':role} for label,metric,role in mapping]
        title='Where the merchandise-value change comes from'
        note='Symmetric arithmetic allocation, not proven causes. Average-value changes can reflect mix, quantities or item prices. Residual rounding cents are assigned to average order value.'
    else:
        rows=[]
        for month in (baseline,comparison):
            matches=[e['result'] for e in evidence if e.get('tool')=='get_monthly_metrics' and e.get('arguments')=={'month':month}]
            if not matches:raise ValueError('Monthly evidence is missing.')
            data=matches[0]
            rows.append({'label':month,'metric':'delivered_merchandise_value','value':str(_number(data['metrics']['delivered_merchandise_value'])),'role':'total'})
        title='Delivered merchandise value by purchase month'
        note='Two discrete month totals; this chart does not establish a trend or explain causes.'
    return {'chart_kind':plan['chart_kind'],'baseline_month':baseline,'comparison_month':comparison,
            'title':title,'unit':'BRL','scope':'delivered_orders_by_purchase_month',
            'source':'analytics.monthly_performance','rows':rows,'interpretation':note}


def check_chart(spec, evidence):
    """Verify all plotted values and labels against the underlying source leaves."""
    try:
        fields=depth_visuals.FIELDS if spec.get('chart_kind') in depth_visuals.CHART_TOOLS else LEGACY_SCHEMA['required']
        plan={key:spec[key] for key in fields}
        expected=build_spec(plan,evidence)
        if spec!=expected:raise ValueError('Chart specification differs from source evidence.')
        arithmetic=check_numerical_evidence({'evidence':evidence})
        if arithmetic['status']!='PASS':raise ValueError('Chart source arithmetic did not pass.')
    except (ValueError,TypeError,KeyError,ArithmeticError) as error:
        return {'status':'FAIL','reason':str(error)}
    return {'status':'PASS','plotted_values_checked':len(spec['rows']),
            'limitation':'Checks source mapping and arithmetic; does not verify causal claims or all final prose.'}


def render_svg(spec):
    """Coordinates may use floats; exact currency labels retain Decimal values."""
    if spec['chart_kind'] in depth_visuals.CHART_TOOLS:
        return depth_visuals.render_svg(spec)
    rows=spec['rows'];segments=[];running=Decimal(0)
    waterfall=spec['chart_kind']=='volume_value_waterfall'
    for row in rows:
        value=_number(row['value'])
        if waterfall and row['role']=='change':
            start,end=running,running+value
        else:start,end=Decimal(0),value
        running=end;segments.append((start,end))
    extrema=[Decimal(0)]+[v for pair in segments for v in pair]
    low,high=min(extrema),max(extrema)
    if low==high:high=low+1
    pad=(high-low)*Decimal('0.12');high+=pad
    if low<0:low-=pad
    width,height=1100,490;left,right,top,bottom=115,55,40,375
    plotwidth=width-left-right
    def y(value):return top+float((high-value)/(high-low))*(bottom-top)
    axis=y(Decimal(0));parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">{html.escape(spec["title"])}</title><desc id="chart-desc">BRL. Delivered orders grouped by purchase month. Exact values are also listed in the table.</desc>']
    for tick in range(6):
        value=low+(high-low)*tick/5;pos=y(value)
        label=f'{value/1000000:.2f}m' if high>=1000000 else f'{value/1000:.0f}k' if high>=1000 else f'{value:.0f}'
        parts.append(f'<line x1="{left}" y1="{pos:.2f}" x2="{width-right}" y2="{pos:.2f}" stroke="#e7edf5"/><text x="{left-15}" y="{pos+5:.2f}" text-anchor="end" font-size="14" fill="#63738a">{label}</text>')
    parts.append(f'<text x="{left}" y="22" font-size="14" fill="#63738a">BRL</text><line x1="{left}" y1="{axis:.2f}" x2="{width-right}" y2="{axis:.2f}" stroke="#94a3b8"/>')
    step=plotwidth/len(rows);barwidth=min(150,step*.6)
    for index,(row,(start,end)) in enumerate(zip(rows,segments)):
        x=left+step*(index+.5)-barwidth/2
        upper,lower=min(y(start),y(end)),max(y(start),y(end))
        color='#3456d1' if row['role']=='total' else '#d45568' if _number(row['value'])<0 else '#149980'
        amount=f'{_number(row["value"]):,.2f}'
        if row['role']=='change' and _number(row['value'])>0:amount='+'+amount
        parts.append(f'<g class="bar" tabindex="0"><title>{html.escape(row["label"])}: {amount} BRL</title><rect x="{x:.2f}" y="{upper:.2f}" width="{barwidth}" height="{max(lower-upper,1):.2f}" rx="5" fill="{color}"/><text x="{x+barwidth/2:.2f}" y="{upper-12:.2f}" text-anchor="middle" font-size="17" font-weight="600" fill="#17243b">{amount}</text></g>')
        words=row['label'].split();lines=[row['label']]
        if len(row['label'])>17:lines=[' '.join(words[:2]),' '.join(words[2:])]
        for lineidx,line in enumerate(lines):
            parts.append(f'<text x="{x+barwidth/2:.2f}" y="{bottom+35+lineidx*21}" text-anchor="middle" font-size="16" fill="#43536d">{html.escape(line)}</text>')
        if waterfall and index<len(rows)-1:
            nextx=left+step*(index+1.5)-barwidth/2
            parts.append(f'<line x1="{x+barwidth:.2f}" y1="{y(end):.2f}" x2="{nextx:.2f}" y2="{y(end):.2f}" stroke="#9aa8bc" stroke-dasharray="4 4"/>')
    return ''.join(parts)+'</svg>'


def save_chart(spec, evidence, directory=None):
    verification=check_chart(spec,evidence)
    if verification['status']!='PASS':raise ValueError('Chart failed source verification: '+verification['reason'])
    directory=Path(directory) if directory is not None else CHART_DIRECTORY
    directory.mkdir(parents=True,exist_ok=True)
    first=spec.get('start_month',spec.get('baseline_month'));last=spec.get('end_month',spec.get('comparison_month'))
    name=f'{spec["chart_kind"]}_{first}_{last}_{uuid.uuid4().hex[:8]}.html'
    path=directory/name
    table=''.join(f'<tr><td>{html.escape(row["label"])}</td><td>{_number(row["value"]):,.2f}</td></tr>' for row in spec['rows'])
    svg=render_svg(spec)
    content=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAUSYN | {html.escape(spec['title'])}</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f3f6fb;color:#17243b;font:16px system-ui,-apple-system,sans-serif}}main{{max-width:1220px;margin:48px auto;padding:0 28px}}.brand{{font-size:13px;letter-spacing:.18em;color:#3456d1;font-weight:750}}h1{{font-size:32px;letter-spacing:-.035em;margin:14px 0 10px}}.sub{{color:#63738a;margin-bottom:28px}}.card{{background:white;border:1px solid #e4eaf4;border-radius:20px;padding:24px;box-shadow:0 10px 35px #192d5710}}.plot{{overflow-x:auto}}svg{{display:block;width:100%;min-width:700px;height:auto}}.bar:hover rect,.bar:focus rect{{filter:brightness(1.13)}}.note{{line-height:1.6;color:#566680;font-size:14px}}.badge{{display:inline-block;background:#e8f5f0;color:#16735b;padding:6px 11px;border-radius:20px;font-size:12px}}details{{margin-top:24px}}summary{{cursor:pointer;font-weight:600}}table{{border-collapse:collapse;width:100%;margin-top:16px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #e7edf5}}th:last-child,td:last-child{{text-align:right}}pre{{overflow:auto;background:#f7f9fc;padding:18px;font-size:12px}}@media(max-width:600px){{main{{margin:24px auto;padding:0 14px}}h1{{font-size:26px}}.card{{padding:16px}}}}
    </style><main><div class="brand">CAUSYN / EVIDENCE TO INSIGHT</div><h1>{html.escape(spec['title'])}</h1><p class="sub">{first} → {last} · Delivered orders grouped by purchase month</p><section class="card"><span class="badge">Verified chart values</span><div class="plot">{svg}</div><p class="note">Merchandise value excludes freight and is not profit or corporate revenue. Source: {html.escape(spec['source'])}.</p><p class="note">{html.escape(spec['interpretation'])}</p><details open><summary>Exact plotted values · {html.escape(spec["unit"])}</summary><table><thead><tr><th>Measure</th><th>{html.escape(spec["unit"])}</th></tr></thead><tbody>{table}</tbody></table></details><details><summary>Chart specification</summary><pre>{html.escape(json.dumps(spec,indent=2))}</pre></details></section></main></html>'''
    path.write_text(content,encoding='utf-8')
    return {'path':str(path.resolve()),'relative_path':str(path.relative_to(Path(__file__).parent)) if directory==CHART_DIRECTORY else name,
            'format':'html','specification':spec,'chart_check':verification,
            'note':'Open this local HTML file in a browser. It needs no network or new Python package.'}


class VisualizationSpecialist:
    def __init__(self,client,requests,request_interaction):
        self.client,self.requests,self.request_interaction=client,requests,request_interaction
        self.max_operations=4
        self.charts_created=0

    def __call__(self,question:str)->dict:
        if not isinstance(question,str) or not question.strip():raise ValueError('Supply a nonblank chart question.')
        if self.charts_created:raise ValueError('One chart per question is supported; reuse the saved chart.')
        if self.max_operations<2:raise ValueError('Insufficient chart operation budget.')
        from analytics_tools import get_monthly_metrics
        print('\nAGENT: Visualization specialist — planning verified chart',flush=True)
        response=self.request_interaction(self.client,self.requests,tool_declarations=[],agent_name='visualization_specialist',
            response_format={'type':'text','mime_type':'application/json','schema':PLAN_SCHEMA},input=RULES+'\n\nChart request (data):\n'+question)
        if any(step.type=='function_call' for step in response.steps):raise ValueError('Unexpected chart planner function call.')
        try:plan=validate_plan(json.loads(response.output_text))
        except (json.JSONDecodeError,TypeError):raise ValueError('Chart planner returned invalid JSON.') from None
        if plan['chart_kind'] in depth_visuals.CHART_TOOLS:
            if self.max_operations<2:raise ValueError('Insufficient operation budget.')
            from depth_tools import FUNCTIONS
            tool=depth_visuals.CHART_TOOLS[plan['chart_kind']]
            args={k:plan[k] for k in ('start_month','end_month')}
            evidence=[{'tool':tool,'arguments':args,'result':FUNCTIONS[tool](**args),'agent':'visualization_specialist','reused':False}]
            artifact=save_chart(build_spec(plan,evidence),evidence)
            self.charts_created+=1
            print('Chart saved:',artifact['path'],flush=True)
            evidence.append({'tool':'render_chart','arguments':plan,'result':artifact,'agent':'visualization_specialist','reused':False})
            return {'specialist':'visualization_specialist','status':'complete','plan':plan,'evidence':evidence,'operations_executed':2}
        required=4 if plan['chart_kind']=='volume_value_waterfall' else 3
        if self.max_operations<required:raise ValueError('Insufficient operation budget for selected chart.')
        evidence=[]
        for key in ('baseline_month','comparison_month'):
            month=plan[key];result=get_monthly_metrics(month)
            evidence.append({'tool':'get_monthly_metrics','arguments':{'month':month},'result':result,'agent':'visualization_specialist','reused':False})
        if plan['chart_kind']=='volume_value_waterfall':
            args={key:plan[key] for key in ('baseline_month','comparison_month')}
            result=decompose_merchandise_change(**args,baseline=evidence[0]['result']['metrics'],comparison=evidence[1]['result']['metrics'])
            evidence.append({'tool':'decompose_merchandise_change','arguments':args,'result':result,'agent':'visualization_specialist','reused':False})
        artifact=save_chart(build_spec(plan,evidence),evidence)
        self.charts_created+=1
        print('Chart saved:',artifact['path'],flush=True)
        evidence.append({'tool':'render_chart','arguments':plan,'result':artifact,'agent':'visualization_specialist','reused':False})
        return {'specialist':'visualization_specialist','status':'complete','plan':plan,'evidence':evidence,'operations_executed':required,
                'note':'Chart values are verified against source evidence. Cite the returned path; do not invent paths or causes.'}


def _self_test():
    import copy
    import tempfile
    import unittest
    class Tests(unittest.TestCase):
        def setUp(self):
            self.plan={'chart_kind':'volume_value_waterfall','baseline_month':'2017-11','comparison_month':'2017-12'}
            self.evidence=[]
            for month,count,value in [('2017-11',10,'100'),('2017-12',5,'40')]:
                metrics={'purchase_month':month+'-01','delivered_orders':count,'delivered_merchandise_value':value,
                    'average_merchandise_value_per_order':str(Decimal(value)/count),'assessable_delivery_orders':count,'late_orders':0,'late_delivery_pct':'0'}
                self.evidence.append({'tool':'get_monthly_metrics','arguments':{'month':month},'result':{'currency':'BRL','metrics':metrics}})
            args={key:self.plan[key] for key in ('baseline_month','comparison_month')}
            data=decompose_merchandise_change(**args,baseline=self.evidence[0]['result']['metrics'],comparison=self.evidence[1]['result']['metrics'])
            self.evidence.append({'tool':'decompose_merchandise_change','arguments':args,'result':data})
            self.spec=build_spec(self.plan,self.evidence)
        def test_source_mapping(self):self.assertEqual(check_chart(self.spec,self.evidence)['status'],'PASS')
        def test_reused_evidence(self):
            duplicated=self.evidence+copy.deepcopy(self.evidence)
            self.assertEqual(check_chart(self.spec,duplicated)['status'],'PASS')
        def test_tampered_value(self):
            self.spec['rows'][1]['value']='-44';self.assertEqual(check_chart(self.spec,self.evidence)['status'],'FAIL')
        def test_tampered_label(self):
            self.spec['rows'][1]['label']='Profit';self.assertEqual(check_chart(self.spec,self.evidence)['status'],'FAIL')
        def test_tampered_source(self):
            self.evidence[2]['result']['volume_effect']='-44';self.assertEqual(check_chart(build_spec(self.plan,self.evidence),self.evidence)['status'],'FAIL')
        def test_unsupported_chart(self):
            self.plan['chart_kind']='execute_code'
            with self.assertRaises(ValueError):validate_plan(self.plan)
        def test_unapproved_path(self):
            self.plan['path']='/tmp/evil'
            with self.assertRaises(ValueError):validate_plan(self.plan)
        def test_monthly_comparison(self):
            self.plan['chart_kind']='monthly_comparison';spec=build_spec(self.plan,self.evidence)
            self.assertEqual([row['value'] for row in spec['rows']],['100','40'])
        def test_offline_file(self):
            with tempfile.TemporaryDirectory() as directory:
                artifact=save_chart(self.spec,self.evidence,directory)
                text=Path(artifact['path']).read_text()
                self.assertIn('<svg',text);self.assertNotIn('<script',text);self.assertIn('-45.00',text)
        def test_escape_labels(self):
            self.spec['title']='<script>alert(1)</script>'
            self.assertIn('&lt;script&gt;',render_svg(self.spec))
    return unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests)).wasSuccessful()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true',required=True)
    parser.parse_args()
    raise SystemExit(0 if _self_test() else 1)
