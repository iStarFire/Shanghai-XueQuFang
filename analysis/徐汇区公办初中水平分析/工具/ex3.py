import re, zlib, sys, os
sys.path.insert(0, '/tmp/ex')
from pdftext import load_objs, get_stream, parse_tounicode, mul
from extract import NUM, NAME, OP

def cmap_of_font(objs, fnum):
    """返回 (bytes)->str 的解码器；无法解码则 None。"""
    body = objs.get(fnum, b'')
    m = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', body)
    if m:
        s = get_stream(objs, int(m.group(1)))
        if s:
            cm = parse_tounicode(s)
            return lambda b, cm=cm: ''.join(
                cm.get(int.from_bytes(b[j:j+2], 'big'), '')
                for j in range(0, len(b) - 1, 2))
    m = re.search(rb'/Encoding\s*/([A-Za-z0-9\-]+)', body)
    enc = m.group(1).decode('latin1') if m else ''
    if 'UCS2' in enc or 'UTF16' in enc:
        return lambda b: b.decode('utf-16-be', 'replace')
    if 'GBK' in enc or 'GB2312' in enc:
        return lambda b: b.decode('gbk', 'replace')
    if enc in ('WinAnsiEncoding', 'MacRomanEncoding'):
        return lambda b: b.decode('cp1252', 'replace')
    if b'/Subtype/Type0' in body or b'/Subtype/CIDFontType' in body:
        return None
    return lambda b: b.decode('cp1252', 'replace')

def resolve_ref(objs, num):
    return objs.get(num, b'')

def get_resources(objs, body):
    m = re.search(rb'/Resources\s*(\d+)\s+0\s+R', body)
    if m:
        return resolve_ref(objs, int(m.group(1)))
    m = re.search(rb'/Resources\s*<<', body)
    if not m:
        return b''
    start = m.end() - 2
    depth = 0; i = start
    while i < len(body):
        if body[i:i+2] == b'<<': depth += 1; i += 2; continue
        if body[i:i+2] == b'>>':
            depth -= 1; i += 2
            if depth == 0: return body[start:i]
            continue
        i += 1
    return b''

def subdict(res, key):
    m = re.search(key + rb'\s*<<', res)
    if not m: return {}
    start = m.end() - 2; depth = 0; i = start
    while i < len(res):
        if res[i:i+2] == b'<<': depth += 1; i += 2; continue
        if res[i:i+2] == b'>>':
            depth -= 1; i += 2
            if depth == 0: return {k.decode('latin1'): int(v)
                                   for k, v in re.findall(rb'/([^\s/]+)\s+(\d+)\s+0\s+R', res[start:i])}
            continue
        i += 1
    return {}

def build_fontmap(objs, res):
    return {k: cmap_of_font(objs, v) for k, v in subdict(res, rb'/Font').items()}

def run(objs, content, fontmap, xobjs, depth=0):
    out = []
    i, n = 0, len(content)
    operands = []
    ctm = (1, 0, 0, 1, 0, 0); cstack = []
    tm = tlm = (1, 0, 0, 1, 0, 0)
    leading = 0.0; font = None
    def nums(k):
        vals = [x[1] for x in operands if x[0] == 'num']
        return vals[-k:] if len(vals) >= k else None
    def show(b, tmv):
        dec = fontmap.get(font)
        if not b or not dec: return
        try: txt = dec(b)
        except Exception: txt = ''
        if not txt.strip():
            if os.environ.get('XQDEBUG'):
                d = mul(tmv, ctm)
                out.append((round(d[5], 2), round(d[4], 2), '□' * max(1, len(b) // 2)))
            return
        d = mul(tmv, ctm)
        out.append((round(d[5], 2), round(d[4], 2), txt))
    while i < n:
        c = content[i:i+1]
        if c.isspace() or c == b'': i += 1; continue
        if c == b'%':
            j = content.find(b'\n', i); i = n if j < 0 else j + 1; continue
        if c == b'(':
            j = i + 1; depth_p = 1
            while j < n:
                if content[j:j+1] == b'\\': j += 2; continue
                if content[j:j+1] == b'(': depth_p += 1
                elif content[j:j+1] == b')':
                    depth_p -= 1
                    if depth_p == 0: break
                j += 1
            operands.append(('str', content[i+1:j])); i = j + 1; continue
        if c == b'<' and content[i+1:i+2] == b'<':
            j = content.find(b'>>', i); operands.append(('dict', None)); i = (j + 2) if j >= 0 else n; continue
        if c == b'<':
            j = content.find(b'>', i); operands.append(('hex', content[i+1:j])); i = j + 1; continue
        if c == b'[':
            operands.append(('arrstart', None)); i += 1; continue
        if c == b']':
            arr = []
            while operands and operands[-1][0] != 'arrstart': arr.append(operands.pop())
            if operands: operands.pop()
            arr.reverse(); operands.append(('arr', arr)); i += 1; continue
        if c == b'/':
            m = NAME.match(content, i); operands.append(('name', m.group(1).decode('latin1'))); i = m.end(); continue
        m = NUM.match(content, i)
        if m and m.group(0):
            operands.append(('num', float(m.group(0)))); i = m.end(); continue
        m = OP.match(content, i)
        if not m: i += 1; continue
        op = m.group(0).decode('latin1'); i = m.end()
        if op == 'q':
            cstack.append(ctm)
        elif op == 'Q':
            if cstack: ctm = cstack.pop()
        elif op == 'cm':
            v = nums(6)
            if v: ctm = mul(tuple(v), ctm)
        elif op == 'BT':
            tm = tlm = (1, 0, 0, 1, 0, 0)
        elif op == 'Tf':
            names = [x[1] for x in operands if x[0] == 'name']
            if names: font = names[-1]
        elif op == 'Tm':
            v = nums(6)
            if v: tm = tlm = tuple(v)
        elif op in ('Td', 'TD'):
            v = nums(2)
            if v:
                if op == 'TD': leading = -v[1]
                tlm = mul((1, 0, 0, 1, v[0], v[1]), tlm); tm = tlm
        elif op == 'TL':
            v = nums(1)
            if v: leading = v[0]
        elif op == 'T*':
            tlm = mul((1, 0, 0, 1, 0, -leading), tlm); tm = tlm
        elif op in ('Tj', "'", '"'):
            if op in ("'", '"'):
                tlm = mul((1, 0, 0, 1, 0, -leading), tlm); tm = tlm
            for kind, val in reversed(operands):
                if kind == 'hex':
                    try: show(bytes.fromhex(re.sub(rb'\s', b'', val).decode('latin1')), tm)
                    except Exception: pass
                    break
                if kind == 'str': show(val, tm); break
        elif op == 'TJ':
            arr = [x for x in operands if x[0] == 'arr']
            if arr:
                for kind, val in arr[-1][1]:
                    if kind == 'hex':
                        try: show(bytes.fromhex(re.sub(rb'\s', b'', val).decode('latin1')), tm)
                        except Exception: pass
                    elif kind == 'str': show(val, tm)
        elif op == 'Do' and depth < 4:
            names = [x[1] for x in operands if x[0] == 'name']
            if names and names[-1] in xobjs:
                fo = objs.get(xobjs[names[-1]], b'')
                if b'/OC ' in fo or b'/OC<' in fo:   # 可选内容层 = 水印，跳过
                    operands = []; continue
                fm = re.search(rb'/Matrix\s*\[([^\]]*)\]', fo)
                mtx = tuple(float(t) for t in fm.group(1).split()) if fm else (1, 0, 0, 1, 0, 0)
                sub = get_stream(objs, xobjs[names[-1]]) if False else None
                sm = re.search(rb'stream\r?\n', fo)
                if sm:
                    s = sm.end(); e = fo.find(b'endstream', s)
                    raw = fo[s:e]
                    try: body = zlib.decompress(raw)
                    except Exception: body = raw
                    fres = get_resources(objs, fo)
                    fmap = build_fontmap(objs, fres)
                    fxobjs = subdict(fres, rb'/XObject')
                    saved = ctm
                    ctm = mul(mtx, ctm)
                    out.extend(run(objs, body, fmap or fontmap, fxobjs, depth + 1))
                    ctm = saved
        operands = []
    return out

def page_texts(path):
    objs = load_objs(path)
    pages = sorted(n for n, b in objs.items()
                   if b'/Type/Page' in b.replace(b' ', b'') and b'/Contents' in b)
    res = []
    for pn in pages:
        pb = objs[pn]
        res_d = get_resources(objs, pb)
        fm = build_fontmap(objs, res_d)
        xo = subdict(res_d, rb'/XObject')
        cn = int(re.search(rb'/Contents\s+(\d+)\s+0\s+R', pb).group(1))
        items = run(objs, get_stream(objs, cn), fm, xo)
        rot = re.search(rb'/Rotate\s+(-?\d+)', pb)
        rot = int(rot.group(1)) % 360 if rot else 0
        if rot in (90, 270):
            # 页面被旋转：内容空间里表格是转置的，交换 x/y 还原为行列表结构
            items = [(x, y, t) for (y, x, t) in items]
        res.append((pn, items))
    return res

if __name__ == '__main__':
    for pn, items in page_texts(sys.argv[1]):
        print(f'=== page obj {pn}: {len(items)} 片段 ===')
