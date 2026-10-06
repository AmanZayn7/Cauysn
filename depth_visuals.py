"""Verified line and ranking charts. Data mappings are deterministic."""
import html
from decimal import Decimal
from depth_contracts import validate_range, validate_result, number

CHART_TOOLS={'monthly_trend':'get_monthly_trend','category_ranking':'get_category_performance',
             'seller_ranking':'get_seller_performance','state_delivery':'get_state_delivery'}
FIELDS={'chart_kind','start_month','end_month'}
SCHEMA={'type':'object','additionalProperties':False,'properties':{
    'chart_kind':{'type':'string','enum':list(CHART_TOOLS)},'start_month':{'type':'string'},'end_month':{'type':'string'}},'required':sorted(FIELDS)}

def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!=FIELDS or plan['chart_kind'] not in CHART_TOOLS: raise ValueError('Invalid range chart plan.')
    validate_range(plan['start_month'],plan['end_month'])
    return plan

def build_spec(plan,evidence):
    validate_plan(plan);kind=plan['chart_kind'];tool=CHART_TOOLS[kind]
    args={k:plan[k] for k in ('start_month','end_month')}
    matches=[e['result'] for e in evidence if e.get('tool')==tool and e.get('arguments')==args]
    if not matches or any(r!=matches[0] for r in matches): raise ValueError('Missing or conflicting range evidence.')
    data=validate_result(tool,matches[0],args)
    metric='late_delivery_pct' if kind=='state_delivery' else 'delivered_merchandise_value' if kind=='monthly_trend' else 'merchandise_value'
    key={'monthly_trend':'purchase_month','category_ranking':'category_label','seller_ranking':'seller_id','state_delivery':'customer_state'}[kind]
    selected=[r for r in data['rows'] if kind!='state_delivery' or number(r['assessable_delivery_orders'])>=30]
    if not selected: raise ValueError('No states meet the chart coverage threshold.')
    rows=[{'label':r[key],'value':str(number(r[metric])),'metric':metric,'role':'level',
           **({'assessable_delivery_orders':str(r['assessable_delivery_orders']),'late_orders':str(r['late_orders'])} if kind=='state_delivery' else {})} for r in selected]
    return {**plan,'title':{'monthly_trend':'Monthly delivered merchandise value','category_ranking':'Leading categories by merchandise value',
        'seller_ranking':'Leading sellers by merchandise value','state_delivery':'Late-delivery rate by customer state'}[kind],
        'source':data['source'],'unit':'percent' if kind=='state_delivery' else 'BRL',
        'scope':data['scope'],'rows':rows,'interpretation':data['interpretation']}

def render_svg(spec):
    rows=spec['rows'];trend=spec['chart_kind']=='monthly_trend';height=360 if trend else 80+len(rows)*37
    pieces=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 580 {height}" role="img" aria-label="{html.escape(spec["title"],quote=True)}"><title>{html.escape(spec["title"])}</title>']
    high=max(number(r['value']) for r in rows) or Decimal(1);high*=Decimal('1.15')
    if spec['unit']=='percent': high=Decimal(100)
    if trend:
        left,right,top,bottom=66,545,28,285
        y=lambda v:bottom-float(number(v)/high)*(bottom-top)
        x=lambda i:left+(right-left)*i/max(1,len(rows)-1)
        for t in range(5):
            v=high*t/4;py=y(v)
            pieces.append(f'<line x1="{left}" x2="{right}" y1="{py}" y2="{py}" stroke="#e7edf5"/><text x="{left-8}" y="{py+4}" text-anchor="end" fill="#566680" font-size="10">{v/1000:.0f}k</text>')
        points=' '.join(f'{x(i):.2f},{y(r["value"]):.2f}' for i,r in enumerate(rows))
        pieces.append(f'<polyline points="{points}" fill="none" stroke="#6d5bd0" stroke-width="2.5"/>')
        step=max(1,(len(rows)+4)//5)
        for i,r in enumerate(rows):
            pieces.append(f'<circle tabindex="0" cx="{x(i)}" cy="{y(r["value"])}" r="4" fill="#6d5bd0"><title>{html.escape(r["label"])}: {number(r["value"]):,.2f} BRL</title></circle>')
            if i%step==0 or i==len(rows)-1: pieces.append(f'<text x="{x(i)}" y="310" text-anchor="middle" fill="#566680" font-size="10">{r["label"]}</text>')
    else:
        for i,r in enumerate(rows):
            y=48+i*37;amount=number(r['value']);width=float(amount/high)*290
            label=r['label']
            display=label[:8]+'…' if spec['chart_kind']=='seller_ranking' else label if len(label)<=25 else label[:24]+'…'
            amount_text=f'{amount:,.2f}'+('%' if spec['unit']=='percent' else '')
            title=f'{label}: {amount_text} {spec["unit"]}'
            if spec['unit']=='percent':title+=f'; {r["late_orders"]} late / {r["assessable_delivery_orders"]} assessable orders'
            pieces.append(f'<g tabindex="0"><title>{html.escape(title)}</title><text x="180" y="{y+17}" text-anchor="end" fill="#43536d" font-size="11">{html.escape(display)}</text><rect x="192" y="{y}" width="{width:.2f}" height="24" rx="3" fill="#8274d8"/><text x="{200+width:.2f}" y="{y+17}" fill="#17243b" font-size="11">{amount_text}</text></g>')
    pieces.append(f'<text x="20" y="19" fill="#566680" font-size="11">{spec["unit"]}</text></svg>')
    return ''.join(pieces)
