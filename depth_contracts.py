"""Contracts for range analyses; pure validation, no API or database access."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TOOLS = {
    'get_monthly_trend': ('purchase_month', {'delivered_orders':'orders', 'delivered_merchandise_value':'BRL',
        'average_merchandise_value_per_order':'BRL', 'assessable_delivery_orders':'orders', 'late_orders':'orders', 'late_delivery_pct':'percent'}),
    'get_category_performance': ('category_label', {'merchandise_value':'BRL', 'items_sold':'items', 'orders_containing_category':'orders', 'average_item_value':'BRL'}),
    'get_seller_performance': ('seller_id', {'merchandise_value':'BRL', 'items_sold':'items', 'orders_containing_seller':'orders', 'average_item_value':'BRL'}),
    'get_state_delivery': ('customer_state', {'delivered_orders':'orders', 'assessable_delivery_orders':'orders', 'late_orders':'orders', 'late_delivery_pct':'percent'}),
}
SCOPE = 'delivered_orders_by_purchase_month'

def month_date(value):
    if not isinstance(value,str): raise ValueError('Months must be strings.')
    try: parsed=date.fromisoformat(value+'-01')
    except ValueError: raise ValueError('Use YYYY-MM purchase months.') from None
    if parsed.strftime('%Y-%m')!=value or not date(2017,1,1)<=parsed<=date(2018,8,1):
        raise ValueError('Supported purchase months are 2017-01 through 2018-08.')
    return parsed

def validate_range(start_month,end_month):
    first,last=month_date(start_month),month_date(end_month)
    if first>last: raise ValueError('start_month must be at or before end_month.')
    return first,last

def months_in_range(start_month,end_month):
    first,last=validate_range(start_month,end_month)
    out=[]
    while first<=last:
        out.append(first.strftime('%Y-%m'))
        first=date(first.year+1,1,1) if first.month==12 else date(first.year,first.month+1,1)
    return out

def number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)): raise ValueError('Invalid numeric type.')
    from re import fullmatch
    if isinstance(value,str) and not fullmatch(r'[+-]?\d+(?:\.\d+)?',value): raise ValueError('Invalid decimal representation.')
    out=Decimal(value)
    if not out.is_finite(): raise ValueError('Nonfinite value.')
    return out

def count(value):
    out=number(value)
    if out<0 or out!=out.to_integral_value(): raise ValueError('Invalid nonnegative count.')
    return out

def near(actual,expected):
    return abs(number(actual)-number(expected))<=Decimal('0.00000001')

def validate_result(tool,data,arguments):
    """Check group identities, period, denominators, ranking and reconciliation.

    Reference totals originate from the existing monthly view, not a model.
    Arithmetic checks cannot establish that underlying warehouse data is correct.
    """
    if tool not in TOOLS or not isinstance(data,dict) or 'error' in data: raise ValueError('Invalid depth evidence.')
    if set(arguments)!={'start_month','end_month'}: raise ValueError('Invalid range arguments.')
    months=months_in_range(**arguments)
    if any(data.get(k)!=v for k,v in arguments.items()): raise ValueError('Evidence period mismatch.')
    if data.get('currency')!='BRL' or data.get('scope')!=SCOPE: raise ValueError('Evidence scope/currency mismatch.')
    key,metrics=TOOLS[tool]; rows=data.get('rows')
    if not isinstance(rows,list) or not rows: raise ValueError('No usable rows for this range.')
    labels=[r[key] for r in rows]
    if any(not isinstance(label,str) or not label for label in labels) or len(set(labels))!=len(labels): raise ValueError('Duplicate or invalid group identifiers.')
    reference=data['reference']; total_orders=count(reference['delivered_orders'])
    total_value=number(reference['delivered_merchandise_value'])
    eligible=count(reference['assessable_delivery_orders']);late=count(reference['late_orders'])
    if total_value<0 or late>eligible or eligible>total_orders: raise ValueError('Invalid reporting reference.')
    for row in rows:
        for metric in metrics:
            if metric not in row: raise ValueError('Missing metric.')
            if metrics[metric] in ('orders','items'): count(row[metric])
            elif row[metric] is not None and number(row[metric])<0: raise ValueError('Negative level metric.')
        if tool in ('get_monthly_trend','get_state_delivery'):
            n,e,l=(count(row[k]) for k in ('delivered_orders','assessable_delivery_orders','late_orders'))
            if not l<=e<=n: raise ValueError('Invalid delivery denominator.')
            if e==0:
                if row['late_delivery_pct'] is not None: raise ValueError('Rate must be null without coverage.')
            elif not near(row['late_delivery_pct'],l/e*100): raise ValueError('Wrong late rate.')
            if tool=='get_monthly_trend':
                v=number(row['delivered_merchandise_value'])
                if n==0:
                    if row['average_merchandise_value_per_order'] is not None: raise ValueError('Undefined average.')
                elif not near(row['average_merchandise_value_per_order'],v/n): raise ValueError('Wrong average order value.')
        else:
            n=count(row['items_sold']); v=number(row['merchandise_value'])
            orders=count(row['orders_containing_category' if tool=='get_category_performance' else 'orders_containing_seller'])
            if n<=0 or orders<=0 or orders>n or orders>total_orders: raise ValueError('Invalid item/group counts.')
            if not near(row['average_item_value'],v/n): raise ValueError('Wrong average item value.')
    if tool in ('get_monthly_trend','get_state_delivery'):
        for metric in ('delivered_orders','assessable_delivery_orders','late_orders'):
            if sum((number(r[metric]) for r in rows),Decimal(0))!=number(reference[metric]): raise ValueError('Group counts do not reconcile.')
        if tool=='get_monthly_trend':
            if labels!=months: raise ValueError('Trend must include every month in chronological order.')
            if sum((number(r['delivered_merchandise_value']) for r in rows),Decimal(0))!=total_value: raise ValueError('Trend money does not reconcile.')
    else:
        if data.get('ranking_limit')!=10 or len(rows)>10: raise ValueError('Unexpected ranking limit.')
        if rows!=sorted(rows,key=lambda r:(-number(r['merchandise_value']),r[key])): raise ValueError('Incorrect merchandise ranking.')
        other=number(data['other_merchandise_value']); other_items=count(data['other_items_sold'])
        if other<0 or sum((number(r['merchandise_value']) for r in rows),Decimal(0))+other!=total_value: raise ValueError('Ranking money does not reconcile.')
        if sum((count(r['items_sold']) for r in rows),Decimal(0))+other_items!=count(data['all_items_sold']): raise ValueError('Item totals do not reconcile.')
        groups=count(data['total_groups'])
        if len(rows)!=min(10,groups) or (groups<=10 and (other!=0 or other_items!=0)): raise ValueError('Incomplete ranking partition.')
    return data
