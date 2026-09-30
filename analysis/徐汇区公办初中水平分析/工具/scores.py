import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ex3 import page_texts

BANDS = {
 2022: [210, 365, 435, 480, 505, 540],
 2023: [130, 290, 375, 425, 455, 490, 525],
 2024: [130, 290, 375, 425, 455, 490, 525],
 2025: [130, 290, 375, 425, 458, 480, 508, 535],
 2026: [130, 290, 375, 425, 458, 480, 508, 535],
}
NAMES = {
 2022: ['junior_high_school','senior_high_school','min_score',
        'last_chinese_math_english','last_math','last_chinese','last_comprehensive_test'],
 2023: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'last_chinese_math_english','last_math','last_chinese','last_comprehensive_test'],
 2024: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'last_chinese_math_english','last_math','last_chinese','last_comprehensive_test'],
 2025: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'comprehensive_eval','last_chinese_math_english','last_math','last_chinese',
        'last_comprehensive_test'],
 2026: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'comprehensive_eval','last_chinese_math_english','last_math','last_chinese',
        'last_comprehensive_test'],
}
NUM = re.compile(r'^-?\d+(?:\.\d+)?$')
ROW_TOL = 1.2
CELL_TOL = 11.0

def band_of(x, bands):
    i = 0
    while i < len(bands) and x >= bands[i]:
        i += 1
    return i

def extract_year(year, path):
    bands = BANDS[year]
    out = []
    for pno, items in page_texts(path):
        items = [it for it in items if it[0] >= 20]
        rows = []
        for y, x, t in sorted(items, key=lambda p: (p[0], p[1])):
            if rows and abs(rows[-1][0] - y) <= ROW_TOL:
                rows[-1][1].append((x, t))
            else:
                rows.append((y, [(x, t)]))
        for y, cells in rows:
            ncol = len(NAMES[year])
            cols = {}
            for x, t in cells:
                i = band_of(x, bands)
                if i >= ncol: continue
                cols[i] = cols.get(i, '') + t
            jh = sorted((x, t) for (yy, x, t) in items
                        if x < bands[0] and abs(yy - y) <= CELL_TOL)
            if jh: cols[0] = ''.join(t for _, t in jh)
            vals = [cols.get(i, '') for i in range(ncol)]
            if not NUM.match(vals[2] or ''): continue
            if not vals[0] or not vals[1]: continue
            out.append((pno, vals))
    return out

if __name__ == '__main__':
    year = int(sys.argv[1]); path = sys.argv[2]
    rows = extract_year(year, path)
    print(f'=== {year}: {len(rows)} 行, {len(set(v[0] for _,v in rows))} 初中, '
          f'{len(set(v[1] for _,v in rows))} 高中 ===')
    print('  可疑校名:', sorted(n for n in set(v[0] for _, v in rows)
                                if len(n) < 6 or len(n) > 25))
    for pno, v in rows[:3]:
        print('  ', ' | '.join(x or '·' for x in v))
