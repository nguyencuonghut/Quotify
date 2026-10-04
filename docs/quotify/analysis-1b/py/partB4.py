import collections, datetime as dt, statistics
import partB
from partB import *
res = replay(3)
an = res['anomalies']
pts_by_day = collections.defaultdict(set)
for a in an: pts_by_day[a['t'].astimezone(VN).date()].add((a['chain'], a['d']))
n_msgs = sum(1 if len(v) >= 3 else len(v) for v in pts_by_day.values())
print('D12 anomaly messages if cluster>=3/day merged into one:', n_msgs, 'over', round(WEEKS, 2), 'weeks =', round(n_msgs / WEEKS, 2), '/wk (per recipient manager)')
print('flagged points (distinct chain-date) from trigger lines under lag<=3:', len({(a['chain'], a['d']) for a in an if a['trigger']}))
# ablation: guard off
orig = State.is_anomalous
State.is_anomalous = lambda self, chain, d, price: False
r0 = replay(3); summarize('D6 lag<=3, anomaly guard OFF', r0)
State.is_anomalous = orig
r1 = replay(3); summarize('D6 lag<=3, anomaly guard ON ', r1)
# sensitivity: window 7 calendar days instead? skip
# sensitivity: anti-repeat off
# Weekly distribution stats for the doc comparison: mean of last weeks
