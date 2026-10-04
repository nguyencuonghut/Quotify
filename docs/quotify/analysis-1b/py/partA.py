# Part A: static day-end replay, reproduces B.7 configuration (12 months, all lines trigger, 7 working days, direction-consistent, 30% anomaly guard, 14-day anti-repeat)
import sys, collections, datetime as dt, statistics
from decimal import Decimal as D
from engine import *

rows = [r for r in load() if r['status'] == 'confirmed']
START = dt.date(2025, 10, 2)    # evaluate points with rd > START (doc 12-month window)
END = dt.date(2026, 10, 2)

def run(anomaly):
    pts = collections.defaultdict(dict)    # chain -> date -> list of (price, line)
    for r in rows:
        pts[r['chain']].setdefault(r['rd'], []).append(r)
    stats = collections.Counter()
    events = []      # (chain, date, dir, level, rule)
    anomalies = []
    for chain, byd in pts.items():
        valid = []   # list of (date, price) valid points so far
        dates = sorted(byd)
        for d in dates:
            lines = byd[d]
            ws = window_start(d)
            prev_win = [(x, p) for (x, p) in valid if ws <= x < d]
            if anomaly == 'line30d':      # D12 final: line level vs median of valid points in 30 calendar days
                ref30 = [p for (x, p) in valid if d - dt.timedelta(days=30) <= x < d]
                if ref30:
                    med = statistics.median(ref30)
                    keep = []
                    for ln in lines:
                        if abs(ln['pc'] - med) / med * 100 >= 30:
                            if d > START: anomalies.append((chain, d, ln['pc'], med, 'line'))
                        else: keep.append(ln)
                    lines = keep
                if not lines: continue
                newp = min(l['pc'] for l in lines)
            else:
                newp = min(l['pc'] for l in lines)
                if anomaly == 'point7wd' and prev_win:
                    med = statistics.median([p for _, p in prev_win])
                    if abs(newp - med) / med * 100 >= 30:
                        if d > START: anomalies.append((chain, d, newp, med, 'point'))
                        continue
            ev = evaluate(newp, prev_win)
            if d > START:
                stats['points'] += 1
                if ev is None:
                    stats['no_prev' if not prev_win else 'no_change_or_zero'] += 1
                else:
                    stats['N'] += 1
                    if ev[1] > 0:
                        stats['reported'] += 1; stats['rule_' + ev[2]] += 1
                        events.append((chain, d, ev[0], ev[1], ev[2]))
            valid.append((d, newp))
    return stats, events, anomalies

def antirepeat(events):
    sent = []; last = {}
    for (chain, d, dr, lv, rule) in sorted(events, key=lambda e: (e[1], e[0])):
        l = last.get(chain)
        if l and (d - l[0]).days <= 14 and (l[1], l[2]) == (dr, lv):
            continue
        last[chain] = (d, dr, lv); sent.append((chain, d, dr, lv, rule))
    return sent

for mode in ('point7wd', 'line30d', 'none'):
    stats, events, anomalies = run(mode)
    sent = antirepeat(events)
    wk = 52
    bychain = len(sent)
    mat_day = {(c[0], d) for (c, d, dr, lv, rule) in sent}
    mat_day_tbl = {(c[0], d) for (c, d, dr, lv, rule) in sent if lv >= MEDIUM}
    print(f"--- anomaly mode = {mode}")
    print('points', stats['points'], '| N (has prev & changed)', stats['N'], '| no prev', stats['no_prev'], '| reported (>=2.5%)', stats['reported'],
          '| R1/R2/R3 primary', stats['rule_R1'], stats['rule_R2'], stats['rule_R3'])
    print('anomalies', len(anomalies), 'chains', len({a[0] for a in anomalies}), 'materials', len({a[0][0] for a in anomalies}))
    print('after anti-repeat: by chain', bychain, f'({bychain/wk:.1f}/wk)', '| by material-day', len(mat_day), f'({len(mat_day)/wk:.1f}/wk)', '| TB+L material-day', len(mat_day_tbl), f'({len(mat_day_tbl)/wk:.1f}/wk)')
    lvc = collections.Counter(lv for (_,_,_,lv,_) in sent)
    print('levels sent', {LV[k]: v for k, v in sorted(lvc.items())})
