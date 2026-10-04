import collections, datetime as dt, statistics
from partB import *
res = replay(None)   # all real versions evaluated for flags
st = res['state']
an = res['anomalies']
# recompute median at flag time is not stored; show price, and the final-state valid points in the 30d before for context
print('flagged lines (all real versions):', len(an))
rows_out = []
for a in sorted(an, key=lambda a: (a['t'], a['material'])):
    chain = a['chain']; d = a['d']
    ref = [p for _, p in st.valid_points(chain, d - dt.timedelta(days=30), d)]
    med = statistics.median(ref) if ref else None
    ratio = float(a['price'] / med) if med else None
    rows_out.append((a['t'].astimezone(VN).strftime('%d/%m %H:%M'), a['material'][:22], str(a['chain'][1])[:7], str(d), str(a['price']), str(med), None if ratio is None else round(ratio, 3), 'trig' if a['trigger'] else '', len(ref)))
for r in rows_out: print(r)
