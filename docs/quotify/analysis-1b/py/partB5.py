import collections
from partB import *
for name, L in (('D6 lag<=3', 3), ('any lag', None)):
    res = replay(L)
    c = collections.Counter(); cs = collections.Counter(); ctb = collections.Counter()
    for m in res['msgs']: c[(m['cd'].year, m['cd'].month)] += 1; ctb[(m['cd'].year, m['cd'].month)] += (m['lv'] >= MEDIUM)
    for e in res['sent']: cs[(e['cd'].year, e['cd'].month)] += 1
    print(name, 'D5b msgs per month', dict(c), '| TB+L', dict(ctb), '| chain-level', dict(cs))
    # material-day per month
    md = collections.Counter((cd.year, cd.month) for (_, cd) in res['mat_day']); print('   material-day per month', dict(md))
