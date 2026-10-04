# Part B: as-of replay by confirmed_at with D6 trigger source, D2 rules, D12 line-level anomaly guard, D5 anti-repeat + message grouping.
import sys, collections, datetime as dt, statistics, csv
from decimal import Decimal as D
from engine import *

rows = load()
roles = {}
for a, b in csv.reader(open('roles.csv', encoding='utf-8')): roles[a] = b

vers = {}
for r in rows:
    v = vers.setdefault(r['vid'], {'vid': r['vid'], 'conf': r['conf'], 'is_seed': r['is_seed'], 'is_bf': r['is_bf'], 'rd': r['rd'], 'status': r['status'],
                                   'sup_by': r['sup_by_vid'] or None, 'qid': r['qid'], 'quser': r['quser'], 'lines': []})
    v['lines'].append(r)
pred = {}
for v in vers.values():
    if v['sup_by']: pred[v['sup_by']] = v['vid']
seed_vs = [v for v in vers.values() if v['is_seed']]
real_vs = sorted([v for v in vers.values() if not v['is_seed']], key=lambda v: (v['conf'], v['vid']))
assert all(v['status'] == 'confirmed' for v in seed_vs)

class State:
    def __init__(self):
        self.pts = collections.defaultdict(lambda: collections.defaultdict(list))  # chain -> date -> [entry]
        self.flag_log = []
    def point(self, chain, d):
        es = [e for e in self.pts[chain].get(d, []) if not e['flag']]
        return min(e['pc'] for e in es) if es else None
    def valid_points(self, chain, lo, hi):   # dates in [lo, hi)
        out = []
        for x in sorted(self.pts[chain]):
            if lo <= x < hi:
                p = self.point(chain, x)
                if p is not None: out.append((x, p))
        return out
    def is_anomalous(self, chain, d, price):
        ref = [p for _, p in self.valid_points(chain, d - dt.timedelta(days=30), d)]
        if not ref: return False
        med = statistics.median(ref)
        return abs(price - med) / med * 100 >= 30
    def add(self, line, flag=None):
        chain = line['chain']; d = line['rd']
        if flag is None: flag = self.is_anomalous(chain, d, line['pc'])
        e = {'lid': line['lid'], 'pc': line['pc'], 'flag': flag, 'vid': line['vid'], 'line': line}
        self.pts[chain][d].append(e)
        return e
    def remove_version(self, vid):
        gone = []
        for chain, byd in self.pts.items():
            for d, es in byd.items():
                keep = [e for e in es if e['vid'] != vid]
                if len(keep) != len(es):
                    gone += [e for e in es if e['vid'] == vid]
                    byd[d] = keep
        return gone

def build_baseline():
    st = State()
    ls = sorted([l for v in seed_vs for l in v['lines']], key=lambda l: (l['rd'], l['lo']))
    for l in ls: st.add(l)
    return st

def key_m(l): return (l['mid'], l['dm'], l['po'], l['pc'])

def replay(L, only_notbf=False, label=''):
    """L: max working-day lag for trigger (None = any lag). Returns dict of results."""
    st = build_baseline()
    events = []; anomalies = []; trig_versions = 0
    for v in real_vs:
        t = v['conf']; cd = t.astimezone(VN).date()
        lag = wd_lag(v['rd'], cd)
        is_trigger = (L is None or lag <= L) and (not only_notbf or not v['is_bf'])
        # candidate lines + carry flags
        p = pred.get(v['vid'])
        carry = {}   # line key -> flag list
        cand = []
        if p:
            pool = collections.defaultdict(list)
            for e in [e for chain in st.pts for d_, es in st.pts[chain].items() for e in es if e['vid'] == p]:
                pool[key_m(e['line'])].append(e['flag'])
        for l in sorted(v['lines'], key=lambda l: int(l['lo'])):
            if p and pool[key_m(l)]:
                carry[l['lid']] = pool[key_m(l)].pop(0)
            else:
                cand.append(l)
        # old points for impacted (chain,date) before changes
        impacted = {(l['chain'], l['rd']) for l in v['lines']}
        if p: impacted |= {(l['chain'], l['rd']) for l in vers[p]['lines']}
        old_pt = {k: st.point(*k) for k in impacted}
        if p: st.remove_version(p)
        # insert: carried first (flag preserved), then candidates evaluated (in line order, using state incl. earlier lines of same version)
        entries = {}
        for l in sorted(v['lines'], key=lambda l: int(l['lo'])):
            if l['lid'] in carry: entries[l['lid']] = st.add(l, flag=carry[l['lid']])
        for l in cand:
            entries[l['lid']] = st.add(l)
        for l in cand:
            if entries[l['lid']]['flag']:
                anomalies.append({'t': t, 'chain': l['chain'], 'd': l['rd'], 'price': l['pc'], 'trigger': is_trigger, 'mid': l['mid'], 'material': l['material'], 'vid': v['vid']})
        if not is_trigger or not cand: continue
        trig_versions += 1
        done = set()
        for l in cand:
            if entries[l['lid']]['flag']: continue
            k = (l['chain'], l['rd'])
            if k in done: continue
            done.add(k)
            newp = st.point(*k)
            if newp is None or newp == old_pt.get(k): continue
            d = l['rd']; ws = window_start(d)
            prev = st.valid_points(l['chain'], ws, d)
            ev = evaluate(newp, prev)
            if ev and ev[1] > 0:
                events.append({'t': t, 'cd': cd, 'chain': l['chain'], 'mid': l['mid'], 'material': l['material'], 'd': d, 'dir': ev[0], 'lv': ev[1], 'rule': ev[2], 'pct': ev[3],
                               'lag': lag, 'quser': v['quser'], 'vid': v['vid']})
    # D5(a) anti-repeat by chain, 14 calendar days on scan local date
    events.sort(key=lambda e: (e['t'], e['chain']))
    last = {}; sent = []
    for e in events:
        l = last.get(e['chain'])
        if l and (e['cd'] - l[0]).days <= 14 and (l[1], l[2]) == (e['dir'], e['lv']):
            e['sent'] = False; continue
        last[e['chain']] = (e['cd'], e['dir'], e['lv']); e['sent'] = True; sent.append(e)
    # D5(b) messages: per (material, scan slot); same local day later scan only if escalation
    slot = lambda e: int(e['t'].timestamp() // SCAN_SLOT_SECONDS)
    groups = collections.defaultdict(list)
    for e in sent: groups[(e['mid'], e['cd'], slot(e))].append(e)
    msgs = []; day_state = {}
    for (mid, cd, sl), es in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        top = max(e['lv'] for e in es); topdir = [e['dir'] for e in es if e['lv'] == top][0]
        s = day_state.get((mid, cd))
        if s is None or top > s[0] or topdir != s[1]:
            msgs.append({'mid': mid, 'cd': cd, 'lv': top, 'dir': topdir, 'n_events': len(es), 'material': es[0]['material'], 'events': es, 't': es[0]['t']})
            day_state[(mid, cd)] = (max(top, s[0] if s else 0), topdir)
    mat_day = {(e['mid'], e['cd']) for e in sent}
    return {'events': events, 'sent': sent, 'msgs': msgs, 'mat_day': mat_day, 'anomalies': anomalies, 'trig_versions': trig_versions, 'state': st}

SCAN_SLOT_SECONDS = 30  # scan interval decided in L27 (the first analysis used 120)
PERIOD_DAYS = 44; WEEKS = PERIOD_DAYS / 7
def summarize(name, res):
    ev, sent, msgs = res['events'], res['sent'], res['msgs']
    md = res['mat_day']; md_tb = {(e['mid'], e['cd']) for e in sent if e['lv'] >= MEDIUM}
    m_tb = [m for m in msgs if m['lv'] >= MEDIUM]
    print(f"{name:34s} trigVers={res['trig_versions']:3d} events={len(ev):4d} sent(by chain)={len(sent):4d} ({len(sent)/WEEKS:5.1f}/wk) | material-day={len(md):3d} ({len(md)/WEEKS:5.1f}/wk) TB+L={len(md_tb):3d} ({len(md_tb)/WEEKS:4.1f}/wk) | D5b msgs={len(msgs):3d} ({len(msgs)/WEEKS:5.1f}/wk) TB+L={len(m_tb):3d} ({len(m_tb)/WEEKS:4.1f}/wk)")

if __name__ == '__main__':
    print('versions: seed', len(seed_vs), 'real', len(real_vs), '| period days', PERIOD_DAYS, 'weeks', round(WEEKS, 2))
    scen = [('D6 lag<=0 WD', 0), ('D6 lag<=1 WD', 1), ('D6 lag<=2 WD', 2), ('D6 lag<=3 WD (D6 NEW)', 3), ('lag<=5 WD', 5), ('lag<=7 WD', 7), ('any lag (real users)', None)]
    results = {}
    for name, L in scen:
        results[name] = replay(L)
        summarize(name, results[name])
    r = replay(None, only_notbf=True); summarize('S2: only is_backfilled=false', r)
    import pickle
    pickle.dump({k: {kk: vv for kk, vv in v.items() if kk != 'state'} for k, v in results.items()}, open('partB_results.pkl', 'wb'))
