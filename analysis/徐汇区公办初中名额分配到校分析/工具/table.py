import sys
sys.path.insert(0, '/tmp/ex')
from extract import page_texts

def group_rows(items, ytol=1.2, xgap=16.0):
    items = sorted(items, key=lambda t: (t[0], t[1]))
    rows = []
    for y, x, t in items:
        if rows and abs(rows[-1][0] - y) <= ytol:
            rows[-1][1].append((x, t))
        else:
            rows.append((y, [(x, t)]))
    out = []
    for y, cells in rows:
        cells.sort()
        merged = []
        for x, t in cells:
            if merged and x - merged[-1][1] <= xgap:
                merged[-1][0] += t; merged[-1][1] = x
            else:
                merged.append([t, x, x])
        out.append((y, [(c[2], c[0]) for c in merged]))
    return out

if __name__ == '__main__':
    path = sys.argv[1]
    pageno = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    items = page_texts(path)[pageno - 1]
    for y, cells in group_rows(items):
        if y > 470:   # 跳过标题与说明
            continue
        print(f'y={y:7.2f} | ' + ' | '.join(f'[{c[0]:.0f}]{c[1]}' for c in cells))
