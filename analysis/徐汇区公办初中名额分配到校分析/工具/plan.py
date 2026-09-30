import sys, re
sys.path.insert(0, '/tmp/ex')
from ex3 import page_texts

CODE = re.compile(r'^\d{6}$')
ROW_TOL = 1.2
CELL_TOL = 11.0

def rows_of(items):
    items = [i for i in items if i[0] >= 20]
    rows = []
    for y, x, t in sorted(items, key=lambda p: (p[0], p[1])):
        if rows and abs(rows[-1][0] - y) <= ROW_TOL:
            rows[-1][1].append((x, t))
        else:
            rows.append((y, [(x, t)]))
    return rows

def merge_cells(chars, gap=15.0):
    out = []
    for x, t in sorted(chars):
        if out and x - out[-1][1] <= gap:
            out[-1][0] += t; out[-1][1] = x
        else:
            out.append([t, x, x])
    return [(c[1], c[0]) for c in out]      # (start_x, text)

def find_centers(pages_items):
    """在所有页里找「高中编号行」：一行内出现 >=3 个 6 位数字码。"""
    best = None
    for page_items in pages_items:
        for y, chars in rows_of(page_items):
            codes = [c for c in merge_cells(chars) if CODE.match(c[1])]
            if len(codes) >= 3 and (best is None or len(codes) > len(best[1])):
                best = (y, codes)
    if not best:
        return []
    return sorted(best[1])          # [(末字x, 6位码), ...] 按 x 排序

def extract_plan(path):
    pages = page_texts(path)
    pages_items = [its for _, its in pages]
    centers = find_centers(pages_items)
    if not centers:
        raise SystemExit('未找到高中编号行')
    left = min(x for x, _ in centers) - 25.0
    out = []
    for pno, items in pages:
        items = [i for i in items if i[0] >= 20]
        for y, chars in rows_of(items):
            # 初中列偶尔换行：吸收 ±11 内的同名首列片段
            lc = [(x, t) for (yy, x, t) in items if x < left and abs(yy - y) <= CELL_TOL]
            leftcells = merge_cells(lc)
            if len(leftcells) < 3:
                continue
            seq, code, name = leftcells[0][1], leftcells[1][1], leftcells[2][1]
            name = ''.join(c[1] for c in leftcells[2:])   # 名称若被拆开则拼接
            if not re.match(r'^\d+$', seq) or not CODE.match(code):
                continue
            if not name or not name.startswith(('上海', '华东', '复旦', '徐汇')):
                continue
            right = [(x, t) for x, t in chars if x >= left]
            xs = [c[0] for c in centers]
            vals = [''] * len(centers)
            for x, t in right:
                j = min(range(len(xs)), key=lambda k: abs(xs[k] - x))
                vals[j] += t
            out.append((pno, seq, code, name, vals))
    return centers, out

if __name__ == '__main__':
    for y in (2022, 2023, 2024):
        centers, rows = extract_plan(f'/tmp/plan/{y}.pdf')
        print(f'=== {y}: {len(rows)} 行, {len(centers)} 个高中列, 中心={[round(c,1) for c in centers]} ===')
        for r in rows[:3]:
            print('   ', r[1], r[2], r[3], '|', ' '.join(v or '·' for v in r[4]))
