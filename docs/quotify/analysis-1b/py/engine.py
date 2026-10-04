"""Read-only replay engine for D2-D6/D12 (new implementation written by the verification agent; the old backtest3/4/5.py do not exist)."""
import csv, collections, datetime as dt, statistics, bisect
from decimal import Decimal
from zoneinfo import ZoneInfo

VN = ZoneInfo('Asia/Ho_Chi_Minh')
UTC = dt.timezone.utc
D = Decimal
LIGHT, MEDIUM, LARGE = 1, 2, 3
LV = {0: 'none', 1: 'Nhẹ', 2: 'Trung bình', 3: 'Lớn'}

def level(x):  # x = |%| Decimal
    if x < D('2.5'): return 0
    if x < D('5'): return LIGHT
    if x <= D('10'): return MEDIUM
    return LARGE

def wstart(d):
    cnt = 0; x = d
    while True:
        x -= dt.timedelta(days=1)
        if x.weekday() < 5: cnt += 1
        if cnt == 7: return x

_ws = {}
def window_start(d):
    r = _ws.get(d)
    if r is None: r = _ws[d] = wstart(d)
    return r

def wd_lag(rd, cd):
    """weekdays in (rd, cd]"""
    n = 0; x = rd
    while x < cd:
        x += dt.timedelta(days=1)
        if x.weekday() < 5: n += 1
    return n

def load(path='lines.csv'):
    rows = []
    for r in csv.DictReader(open(path, encoding='utf-8')):
        r['rd'] = dt.date.fromisoformat(r['rd']); r['dm'] = dt.date.fromisoformat(r['dm'])
        r['conf'] = dt.datetime.fromisoformat(r['conf_utc']).replace(tzinfo=UTC)
        r['sup'] = dt.datetime.fromisoformat(r['sup_utc']).replace(tzinfo=UTC) if r['sup_utc'] else None
        r['conf_vn_date'] = r['conf'].astimezone(VN).date()
        r['pc'] = D(r['pc']); r['po'] = D(r['po'])
        r['is_seed'] = int(r['is_seed']); r['is_bf'] = int(r['is_bf'])
        r['chain'] = (r['mid'], r['dm'])
        rows.append(r)
    return rows

def evaluate(newp, prev):
    """newp Decimal; prev = list of (date, price) of valid prior points in the window sorted by date.
    returns (dir, level, primary_rule, pct_primary) or None"""
    if not prev: return None
    last = prev[-1][1]
    if last == 0: return None
    p1 = (newp - last) / last * 100
    if p1 == 0: return None
    direction = 1 if p1 > 0 else -1
    best = (abs(p1), 'R1', p1)
    l1 = level(abs(p1))
    if direction > 0:
        mn = min(p for _, p in prev)
        p2 = (newp - mn) / mn * 100
        if abs(p2) > best[0]: best = (abs(p2), 'R2', p2)
    else:
        mx = max(p for _, p in prev)
        p3 = (newp - mx) / mx * 100
        if abs(p3) > best[0]: best = (abs(p3), 'R3', p3)
    return (direction, level(best[0]), best[1], best[2])
