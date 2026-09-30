import re, zlib

def load_objs(path):
    d = open(path, 'rb').read()
    objs = {}
    for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', d, re.S):
        objs[int(m.group(1))] = m.group(2)
    return objs

def get_stream(objs, n):
    b = objs[n]
    m = re.search(rb'stream\r?\n', b)
    if not m:
        return None
    s = m.end(); e = b.find(b'endstream', s)
    raw = b[s:e]
    try:
        return zlib.decompress(raw)
    except Exception:
        return raw

def parse_tounicode(data):
    txt = data.decode('latin1')
    m = {}
    for blk in re.findall(r'beginbfchar(.*?)endbfchar', txt, re.S):
        for a, b in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            m[int(a, 16)] = ''.join(chr(int(b[i:i+4], 16)) for i in range(0, len(b), 4))
    for blk in re.findall(r'beginbfrange(.*?)endbfrange', txt, re.S):
        for a, b, c in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            lo, hi, st = int(a, 16), int(b, 16), int(c, 16)
            for k in range(lo, hi + 1):
                m[k] = chr(st + (k - lo))
    return m

def mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1*a2 + b1*c2, a1*b2 + b1*d2,
            c1*a2 + d1*c2, c1*b2 + d1*d2,
            e1*a2 + f1*c2 + e2, e1*b2 + f1*d2 + f2)

TOKEN = re.compile(rb'<<|>>|\[|\]|/([^\s/<>\[\]()]+)|\((?:[^()\\]|\\.)*\)|<([0-9A-Fa-f\s]*)>|[-+]?[0-9]*\.?[0-9]+|[A-Za-z\'"*]+')

def unescape_lit(s):
    out = bytearray(); i = 0
    while i < len(s):
        ch = s[i]
        if ch == 0x5C and i + 1 < len(s):
            nxt = s[i+1]
            mp = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
            if nxt in mp: out.append(mp[nxt]); i += 2; continue
            if 0x30 <= nxt <= 0x37:
                j = i + 1; oct_s = ''
                while j < len(s) and len(oct_s) < 3 and 0x30 <= s[j] <= 0x37:
                    oct_s += chr(s[j]); j += 1
                out.append(int(oct_s, 8) & 0xFF); i = j; continue
            out.append(nxt); i += 2; continue
        out.append(ch); i += 1
    return bytes(out)

def extract(path, cid2uni):
    objs = load_objs(path)
    pages = [n for n, b in objs.items() if b'/Type/Page' in b.replace(b' ', b'') and b'/Contents' in b]
    pages.sort()
    results = {}
    for pi, pn in enumerate(pages, 1):
        content = get_stream(objs, int(re.search(rb'/Contents\s+(\d+)\s+0\s+R', objs[pn]).group(1)))
        toks = TOKEN.findall(content) if False else None
        # full token walk
        items = []
        pos = 0
        stack = []
        ctm = (1, 0, 0, 1, 0, 0); ctm_stack = []
        tm = tlm = (1, 0, 0, 1, 0, 0)
        leading = 0.0
        font = None
        for m in TOKEN.finditer(content):
            t = m.group(0)
            if t == b'q':
                ctm_stack.append(ctm)
            elif t == b'Q':
                if ctm_stack: ctm = ctm_stack.pop()
            elif t == b'cm':
                if len(stack) >= 6:
                    ctm = mul(tuple(stack[-6:]), ctm); stack = stack[:-6]
            elif t == b'BT':
                tm = tlm = (1, 0, 0, 1, 0, 0)
            elif t == b'Tf':
                if stack:
                    font = stack[-2] if len(stack) >= 2 else None
                    stack = []
            elif t == b'Tm':
                if len(stack) >= 6:
                    tm = tlm = tuple(stack[-6:]); stack = []
            elif t in (b'Td', b'TD'):
                if len(stack) >= 2:
                    tx, ty = stack[-2], stack[-1]
                    if t == b'TD': leading = -ty
                    tlm = mul((1, 0, 0, 1, tx, ty), tlm)
                    tm = tlm; stack = []
            elif t == b'TL':
                if stack: leading = stack[-1]; stack = []
            elif t == b'T*':
                tlm = mul((1, 0, 0, 1, 0, -leading), tlm); tm = tlm
            elif t in (b'Tj', b'TJ', b"'", b'"'):
                pass
            else:
                stack.append(t)
        results[pi] = items
    return results
