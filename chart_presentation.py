"""Pure chart display helpers: round axes, consistent units, readable labels."""
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_UP


def nice_ticks(minimum, maximum, target=4):
    lo=min(Decimal(0),Decimal(str(minimum)));hi=max(Decimal(0),Decimal(str(maximum)))
    if not lo.is_finite() or not hi.is_finite():raise ValueError('Invalid chart extent.')
    if lo==hi:hi=lo+1
    raw=(hi-lo)/target;base=Decimal(10)**raw.adjusted()
    step=next(n for n in (Decimal(1),Decimal(2),Decimal('2.5'),Decimal(5),Decimal(10)) if n>=raw/base)*base
    low=((lo*Decimal('1.08') if lo<0 else lo)/step).to_integral_value(rounding=ROUND_FLOOR)*step
    high=((hi*Decimal('1.08') if hi>0 else hi)/step).to_integral_value(rounding=ROUND_CEILING)*step
    return low,high,[low+i*step for i in range(int((high-low)/step)+1)]


def compact(value, places=2):
    n=Decimal(str(value));size=abs(n)
    scale,suffix=(Decimal(1000000),'M') if size>=1000000 else (Decimal(1000),'k') if size>=1000 else (Decimal(1),'')
    rounded=(n/scale).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
    text=format(rounded,'f')
    if '.' in text:text=text.rstrip('0').rstrip('.')
    return text+suffix


def category_label(label):
    names={'bed_bath_table':'Bed, bath & table','watches_gifts':'Watches & gifts',
           'health_beauty':'Health & beauty','computers_accessories':'Computer accessories','pc_gamer':'PC gamer'}
    return names.get(label,str(label).replace('_',' ').capitalize())


def month_label(month):
    from datetime import date
    try:return date.fromisoformat(str(month)[:7]+'-01').strftime('%b %Y')
    except ValueError:return str(month)
