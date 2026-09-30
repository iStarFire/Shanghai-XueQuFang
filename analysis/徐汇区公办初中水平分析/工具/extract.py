import re, zlib, sys
sys.path.insert(0, '/tmp/ex')
from pdftext import load_objs, get_stream, parse_tounicode, mul

NUM = re.compile(rb'[-+]?(?:\d+\.?\d*|\.\d+)')
NAME = re.compile(rb'/([^\s/<>\[\](){}]*)')
OP = re.compile(rb"[A-Za-z'\"*][A-Za-z0-9'\"*]*")

def run(content, cid2uni):
    out = []
    i, n = 0, len(content)
    operands = []
    ctm = (1, 0, 0, 1, 0, 0); cstack = []
    tm = tlm = (1, 0, 0, 1, 0, 0)
    leading = 0.0
    font = None
    def nums(op_list, k):
        vals = [x[1] for x in op_list if x[0] == 'num']
        return vals[-k:] if len(vals) >= k else None
    def show_str(bytes_, tmv):
        if not bytes_ or font != 'FT9':
            return
        cids = [int.from_bytes(bytes_[j:j+2], 'big') for j in range(0, len(bytes_) - 1, 2)]
        txt = ''.join(cid2uni.get(c, '') for c in cids)
        if not txt.strip():
            return
        d = mul(tmv, ctm)
        out.append((round(d[5], 2), round(d[4], 2), txt))
    while i < n:
        c = content[i:i+1]
        if c.isspace() or c == b'':
            i += 1; continue
        if c == b'%':
            j = content.find(b'\n', i); i = n if j < 0 else j + 1; continue
        if c == b'(':
            j = i + 1; depth = 1
            while j < n:
                if content[j:j+1] == b'\\': j += 2; continue
                if content[j:j+1] == b'(': depth += 1
                elif content[j:j+1] == b')':
                    depth -= 1
                    if depth == 0: break
                j += 1
            operands.append(('str', content[i+1:j])); i = j + 1; continue
        if c == b'<' and content[i+1:i+2] == b'<':
            j = content.find(b'>>', i) + 2
            operands.append(('dict', None)); i = j; continue
        if c == b'<':
            j = content.find(b'>', i)
            operands.append(('hex', content[i+1:j])); i = j + 1; continue
        if c == b'[':
            operands.append(('arrstart', None)); i += 1; continue
        if c == b']':
            arr = []
            while operands and operands[-1][0] != 'arrstart':
                arr.append(operands.pop())
            if operands: operands.pop()
            arr.reverse()
            operands.append(('arr', arr)); i += 1; continue
        if c == b'/':
            m = NAME.match(content, i); operands.append(('name', m.group(1).decode('latin1'))); i = m.end(); continue
        m = NUM.match(content, i)
        if m and m.group(0):
            operands.append(('num', float(m.group(0)))); i = m.end(); continue
        m = OP.match(content, i)
        if not m:
            i += 1; continue
        op = m.group(0).decode('latin1'); i = m.end()
        if op == 'q':
            cstack.append(ctm)
        elif op == 'Q':
            if cstack: ctm = cstack.pop()
        elif op == 'cm':
            v = nums(operands, 6)
            if v: ctm = mul(tuple(v), ctm)
        elif op == 'BT':
            tm = tlm = (1, 0, 0, 1, 0, 0)
        elif op == 'Tf':
            names = [x[1] for x in operands if x[0] == 'name']
            if names: font = names[-1]
        elif op == 'Tm':
            v = nums(operands, 6)
            if v: tm = tlm = tuple(v)
        elif op in ('Td', 'TD'):
            v = nums(operands, 2)
            if v:
                if op == 'TD': leading = -v[1]
                tlm = mul((1, 0, 0, 1, v[0], v[1]), tlm); tm = tlm
        elif op == 'TL':
            v = nums(operands, 1)
            if v: leading = v[0]
        elif op == 'T*':
            tlm = mul((1, 0, 0, 1, 0, -leading), tlm); tm = tlm
        elif op in ('Tj', "'", '"'):
            if op in ("'", '"'):
                tlm = mul((1, 0, 0, 1, 0, -leading), tlm); tm = tlm
            for kind, val in reversed(operands):
                if kind == 'hex':
                    show_str(bytes.fromhex(re.sub(rb'\s', b'', val).decode()), tm); break
                if kind == 'str':
                    show_str(val, tm); break
        elif op == 'TJ':
            arr = [x for x in operands if x[0] == 'arr']
            if arr:
                for kind, val in arr[-1][1]:
                    if kind == 'hex':
                        show_str(bytes.fromhex(re.sub(rb'\s', b'', val).decode()), tm)
                    elif kind == 'str':
                        show_str(val, tm)
        operands = []
    return out

def page_texts(path):
    objs = load_objs(path)
    cid2uni = parse_tounicode(get_stream(objs, 10))
    pages = sorted(n for n, b in objs.items()
                   if b'/Type/Page' in b.replace(b' ', b'') and b'/Contents' in b)
    res = []
    for pn in pages:
        cn = int(re.search(rb'/Contents\s+(\d+)\s+0\s+R', objs[pn]).group(1))
        res.append(run(get_stream(objs, cn), cid2uni))
    return res

if __name__ == '__main__':
    pages = page_texts(sys.argv[1])
    for pi, items in enumerate(pages, 1):
        print(f'===== PAGE {pi}: {len(items)} 个文本片段 =====')
        for y, x, t in items[:60]:
            print(f'  y={y:8.2f} x={x:8.2f}  {t}')
