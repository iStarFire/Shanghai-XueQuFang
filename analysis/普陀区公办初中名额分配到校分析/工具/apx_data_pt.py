"""附录 A.1 / A.2 的数据计算模块（供生成器与核对复用）。"""
import csv
import statistics as st
from pathlib import Path

D = Path('.')


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


W = {r['junior_high_school']: r for r in load(D / '宽表-初中水平-普陀区-2022-2026.csv')}
RANKED = sorted((r for r in W.values() if r['row_type'] == 'ranked'),
                key=lambda r: int(r['rank_P_wq_comb']))


def sh(n):
    return n.replace('上海市', '').replace('上海', '')


def sp(a, b):
    def rk(v):
        s = sorted(v)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in v]
    ra, rb = rk(a), rk(b)
    ma, mb = st.fmean(ra), st.fmean(rb)
    d = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / d if d else None


def a1_rows():
    base = [int(r['rank_P_wq_comb']) for r in RANKED]
    out = []
    for lab, col in (('线性 1:2:3:4:5', 'rank_P_lin'), ('指数 1:2:4:8:16', 'rank_P_exp'),
                     ('近 3 年 0:0:1:1:1', 'rank_P_recent3'),
                     ('近 2 年 0:0:0:1:1', 'rank_P_recent2')):
        d = {r['junior_high_school']: int(r[col]) for r in W.values()
             if r.get(col) not in ('', None)}
        rho = sp(base, [d[n] for n in d])
        mv = sorted(((n, d[n] - int(r['rank_P_wq_comb']))
                     for n, r in ((x['junior_high_school'], x) for x in RANKED) if n in d),
                    key=lambda t: -abs(t[1]))
        out.append({'label': lab, 'pool': len(d), 'rho': rho, 'mv': mv})
    return out


def a2_vals():
    base = [int(r['rank_P_wq_comb']) for r in RANKED]
    return {
        'eq': sp(base, [int(r['rank_P_eq_comb']) for r in RANKED]),
        'z': sp(base, [int(r['rank_Z_wq_comb']) for r in RANKED]),
        'zr': sp(base, [int(r['rank_ZR_wq_comb']) for r in RANKED]),
        'eq_all': sp([int(r['rank_P_wq_all']) for r in RANKED],
                     [int(r['rank_P_eq_all']) for r in RANKED]),
    }


if __name__ == '__main__':
    for r in a1_rows():
        n3 = sum(1 for _, v in r['mv'] if abs(v) >= 3)
        print(f"  {r['label']:<18} 池 {r['pool']:>2}  rho={r['rho']:+.4f}  "
              f"ge3 {n3:>2} ({n3 / r['pool'] * 100:.0f}%)  max {sh(r['mv'][0][0])} {r['mv'][0][1]:+d}")
    v = a2_vals()
    print(f"  A.2 wq-vs-eq comb {v['eq']:.4f} / all {v['eq_all']:.4f}; "
          f"P-vs-Z {v['z']:.4f}; P-vs-ZR {v['zr']:.4f}")
