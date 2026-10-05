"""Fixed, parameterized read-only range analyses. No arbitrary SQL execution."""
from datetime import date
from decimal import Decimal
from depth_contracts import TOOLS, SCOPE, validate_range, validate_result


def _query(cursor,sql,args):
    cursor.execute(sql,args)
    return cursor.fetchall()


def _run(tool,start_month,end_month):
    start,end=validate_range(start_month,end_month)
    from analytics_tools import connect_database
    args={'start_month':start_month,'end_month':end_month}
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            monthly=_query(cursor,'''SELECT purchase_month, delivered_orders, delivered_merchandise_value,
                average_merchandise_value_per_order, assessable_delivery_orders, late_orders, late_delivery_pct
                FROM analytics.monthly_performance WHERE purchase_month BETWEEN %s AND %s
                ORDER BY purchase_month''',(start,end))
            if not monthly: raise ValueError('No monthly data for this range.')
            reference={key:sum((row[key] for row in monthly),Decimal(0) if key=='delivered_merchandise_value' else 0)
                for key in ('delivered_orders','delivered_merchandise_value','assessable_delivery_orders','late_orders')}
            result={**args,'currency':'BRL','scope':SCOPE,'reference':reference}
            if tool=='get_monthly_trend':
                rows=[{**row,'purchase_month':row['purchase_month'].strftime('%Y-%m')} for row in monthly]
                source='analytics.monthly_performance'
                note='Monthly totals, in chronological order. No forecasting or causal attribution.'
            elif tool=='get_state_delivery':
                rows=_query(cursor,'''SELECT customer_state, SUM(delivered_orders) AS delivered_orders,
                    SUM(assessable_delivery_orders) AS assessable_delivery_orders, SUM(late_orders) AS late_orders,
                    100.0*SUM(late_orders)/NULLIF(SUM(assessable_delivery_orders),0) AS late_delivery_pct
                    FROM analytics.state_delivery_monthly WHERE purchase_month BETWEEN %s AND %s
                    GROUP BY customer_state ORDER BY late_delivery_pct DESC NULLS LAST, customer_state''',(start,end))
                source='analytics.state_delivery_monthly + analytics.monthly_performance'
                note='Customer destination state, not seller state. Rates use assessable delivered orders only. Small samples do not establish operational quality or causes. Charts omit states with fewer than 30 assessable orders; all states remain in evidence.'
            else:
                # Table/column strings come solely from this fixed allowlist, never user/model input.
                view,key,order_key=('analytics.category_monthly','category_label','orders_containing_category') if tool=='get_category_performance' else ('analytics.seller_monthly','seller_id','orders_containing_seller')
                rows=_query(cursor,f'''SELECT {key}, SUM(items_sold) AS items_sold,
                    SUM({order_key}) AS {order_key}, SUM(merchandise_value) AS merchandise_value,
                    SUM(merchandise_value)/NULLIF(SUM(items_sold),0) AS average_item_value
                    FROM {view} WHERE purchase_month BETWEEN %s AND %s GROUP BY {key}
                    ORDER BY merchandise_value DESC, {key}''',(start,end))
                result.update(ranking_limit=10,total_groups=len(rows),
                    all_items_sold=sum(r['items_sold'] for r in rows),
                    other_items_sold=sum(r['items_sold'] for r in rows[10:]),
                    other_merchandise_value=sum((r['merchandise_value'] for r in rows[10:]),Decimal(0)))
                rows=rows[:10]
                source=view+' + analytics.monthly_performance'
                note='Top 10 by delivered merchandise value; remaining groups included in reconciliation. Item counts count item rows. Group order counts overlap across categories/sellers and must not be added. Average item value is not average order value. Seller identifiers are anonymized, not business names.'
            result.update(rows=rows,source=source,interpretation=note)
            return validate_result(tool,result,args)


def get_monthly_trend(start_month:str,end_month:str)->dict:
    return _run('get_monthly_trend',start_month,end_month)

def get_category_performance(start_month:str,end_month:str)->dict:
    return _run('get_category_performance',start_month,end_month)

def get_seller_performance(start_month:str,end_month:str)->dict:
    return _run('get_seller_performance',start_month,end_month)

def get_state_delivery(start_month:str,end_month:str)->dict:
    return _run('get_state_delivery',start_month,end_month)

FUNCTIONS={name:globals()[name] for name in TOOLS}
