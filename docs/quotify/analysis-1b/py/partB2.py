import collections, datetime as dt, statistics
from partB import *

res = replay(3)
sent, msgs, ev = res['sent'], res['msgs'], res['events']
print('== D6 scenario (not seed, lag<=3 WD): sent events by ISO week of scan date (chain-level / material-level msgs / TB+L msgs)')
byw = collections.defaultdict(lambda: [0, 0, 0, 0])
for e in sent: byw[e['cd'].isocalendar()[:2]][0] += 1
for m in msgs:
    k = m['cd'].isocalendar()[:2]; byw[k][1] += 1
    if m['lv'] >= MEDIUM: byw[k][2] += 1
for e in ev: byw[e['cd'].isocalendar()[:2]][3] += 1
for k in sorted(byw): print(k, 'sent_by_chain', byw[k][0], '| D5b msgs', byw[k][1], '| TB+L msgs', byw[k][2], '| events before anti-repeat', byw[k][3])
print('max week msgs', max(v[1] for v in byw.values()), 'max week TB+L', max(v[2] for v in byw.values()))
print()
print('== per day (VN scan date): msgs, TB+L, chain-level sent')
byd = collections.defaultdict(lambda: [0, 0, 0])
for e in sent: byd[e['cd']][2] += 1
for m in msgs:
    byd[m['cd']][0] += 1
    if m['lv'] >= MEDIUM: byd[m['cd']][1] += 1
top = sorted(byd.items(), key=lambda kv: -kv[1][0])[:6]
for k, v in top: print(k, 'msgs', v[0], 'TB+L', v[1], 'by-chain', v[2])
print('days with >=1 msg', len(byd), 'of', PERIOD_DAYS)
print('max msgs in one scan slot (2 min):')
slotc = collections.Counter(int(m['t'].timestamp() // 120) for m in msgs)
mx = max(slotc.values()); print('  ', mx, '(slot count with that max:', sum(1 for v in slotc.values() if v == mx), ')')
print('max chain-level events in one scan slot:', max(collections.Counter(int(e['t'].timestamp() // 120) for e in sent).values()))
print()
print('== level mix of sent (chain-level)', {LV[k]: v for k, v in sorted(collections.Counter(e['lv'] for e in sent).items())}, 'dir up/down', collections.Counter(e['dir'] for e in sent))
print('rules', collections.Counter(e['rule'] for e in sent))
print('top materials by D5b msgs', collections.Counter(m['material'] for m in msgs).most_common(6))
print('suppressed by anti-repeat', sum(1 for e in ev if not e['sent']), 'of', len(ev))
print()
# ----- anomalies
an = res['anomalies']
print('== D12 line-level flags during real-data replay: flagged lines', len(an), '| distinct (chain,date) points', len({(a['chain'], a['d']) for a in an}),
      '| chains', len({a['chain'] for a in an}), '| materials', len({a['mid'] for a in an}))
print('   of which from trigger versions (lag<=3)', sum(1 for a in an if a['trigger']), 'lines; non-trigger', sum(1 for a in an if not a['trigger']))
byday = collections.Counter(a['t'].astimezone(VN).date() for a in an)
print('   flagged lines per VN day:', sorted(byday.items())[:20])
print('   by material', collections.Counter(a['material'] for a in an).most_common())
# clusters by scan day with >=3 points
pts_by_day = collections.defaultdict(set)
for a in an: pts_by_day[a['t'].astimezone(VN).date()].add((a['chain'], a['d']))
print('   days with >=3 flagged points (D12 cluster rule):', [(str(k), len(v)) for k, v in sorted(pts_by_day.items()) if len(v) >= 3])
print('   per-week flagged distinct points', len({(a['chain'], a['d']) for a in an}) / WEEKS)
# ----- recipients D8
roles = {a: b for a, b in csv.reader(open('roles.csv', encoding='utf-8'))}
managers = {u for u, r in roles.items() if 'manager' in r.split(',')}
stafflines = [l for l in rows if not l['is_seed']]
def recipients(mid, t, cd):
    s = set()
    for l in stafflines:
        if l['mid'] != mid: continue
        if l['conf'] <= t and (l['sup'] is None or l['sup'] > t) and cd - dt.timedelta(days=90) <= l['rd'] <= cd:
            s.add(l['quser'])
    return s
per = collections.defaultdict(lambda: {'imm': 0, 'light': 0, 'light_days': set(), 'all': 0})
nrec = []
for m in msgs:
    rec = recipients(m['mid'], m['t'], m['cd'])
    nrec.append(len(rec))
    for u in rec:
        if m['lv'] >= MEDIUM: per[u]['imm'] += 1
        else:
            per[u]['light'] += 1; per[u]['light_days'].add(m['cd'])
        per[u]['all'] += 1
    for u in managers:
        if m['lv'] >= MEDIUM and u not in rec:
            per[u]['imm'] += 1; per[u]['all'] += 1
print()
print('== D8 staff recipients per message (staff who entered the material within 90 days, not counting managers receive_all): mean', round(statistics.mean(nrec), 2), 'median', statistics.median(nrec), 'max', max(nrec))
print('   per person (anonymised), msgs over', round(WEEKS, 2), 'weeks: immediate(TB+L)/wk, light msgs/wk, digest-days/wk, all-levels msgs/wk, role')
for i, (u, s) in enumerate(sorted(per.items(), key=lambda kv: -kv[1]['all'])):
    print(f"   P{i+1}: imm {s['imm']/WEEKS:5.1f}/wk | light {s['light']/WEEKS:5.1f}/wk | digest-days {len(s['light_days'])/WEEKS:4.1f}/wk | all {s['all']/WEEKS:5.1f}/wk | {roles.get(u,'?')}")
