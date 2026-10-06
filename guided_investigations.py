"""Discoverable investigation templates; no database or model calls here."""
from analytics_tools import validate_month

GUIDES = {
    'change': {
        'title': 'Investigate a sales change',
        'description': 'Compare two months and see which categories contributed to the change.',
        'outcome': 'Month comparison · Category contributions · Checked evidence',
        'dates': 'comparison', 'start': '2017-11', 'end': '2017-12',
        'example': 'comparison', 'example_label': 'View November → December example',
    },
    'trend': {
        'title': 'Explore sales trends',
        'description': 'See how delivered merchandise value and order counts changed over time.',
        'outcome': 'Monthly trend chart · Delivered orders · Period totals',
        'dates': 'range', 'start': '2017-01', 'end': '2018-08',
        'example': 'comparison', 'example_label': 'View a recorded month comparison',
    },
    'leaders': {
        'title': 'Find categories and sellers',
        'description': 'Rank categories or anonymized sellers by delivered merchandise value.',
        'outcome': 'Top-10 ranking chart · Merchandise values · Period totals',
        'dates': 'range', 'start': '2017-11', 'end': '2017-12',
        'example': 'categories', 'example_label': 'View recorded category ranking',
    },
    'delivery': {
        'title': 'Compare delivery performance',
        'description': 'Compare late-delivery rates across customer destination states.',
        'outcome': 'State comparison chart · Late rates · Sample sizes',
        'dates': 'range', 'start': '2017-01', 'end': '2018-08',
        'example': 'definition', 'example_label': 'View the recorded metric definition',
    },
}


def guided_question(plan):
    if not isinstance(plan, dict):
        raise ValueError('Choose a valid investigation.')
    kind = plan.get('kind')
    if not isinstance(kind, str) or kind not in GUIDES:
        raise ValueError('Choose a supported investigation.')
    permitted = {'kind', 'start_month', 'end_month'}
    if kind == 'leaders':
        permitted.add('group')
    if set(plan) != permitted:
        raise ValueError('Unexpected or missing investigation options.')
    start, end = plan['start_month'], plan['end_month']
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError('Choose months in YYYY-MM format.')
    a, b = validate_month(start), validate_month(end)
    if kind != 'change' and a > b:
        raise ValueError('The end month must be at or after the start month.')
    if kind == 'change' and a == b:
        raise ValueError('Choose two different months to compare.')
    if kind == 'change':
        return (f'Compare {start} (baseline) with {end} (comparison). Report delivered '
                'merchandise value change, delivered order count change, late-delivery '
                'rate difference, and the three largest negative category contributions. '
                'Explain category contributions as arithmetic, not proven causes.')
    if kind == 'trend':
        return (f'Create a monthly delivered merchandise value trend chart from {start} '
                f'through {end}. Report the period total delivered orders and merchandise '
                'value. Describe observed changes, without forecasting or causal claims.')
    if kind == 'leaders':
        group = plan['group']
        if group not in ('categories', 'sellers'):
            raise ValueError('Choose categories or sellers.')
        chart = 'category' if group == 'categories' else 'seller'
        return (f'Create a {chart} ranking chart for {start} through {end} by delivered '
                f'merchandise value. Report the three leading {group} and their merchandise '
                'values. Merchandise value is not profit.')
    return (f'Create a customer-state late-delivery rate chart for {start} through {end}. '
            'Report late rates and assessable-order counts. Explain the minimum sample '
            'size and do not infer proven causes or seller-state performance.')
