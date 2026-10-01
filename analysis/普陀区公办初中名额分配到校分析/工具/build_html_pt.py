"""把分析报告生成为可发布的静态站点（GitHub Pages）。

设计要点：
- **单一事实来源**：narrative 只存在于 `分析报告.md`，本脚本负责转换，
  避免 HTML 里的数字与报告脱节。改报告 → 重跑本脚本 → 页面同步。
- **零外部依赖**：CSS 内联，不引任何 CDN；离线可用，GitHub Pages 无需构建。
- **移动端优先**：viewport 元标签、流式字号、表格横向滚动容器、深色模式。

产物：
  analysis/普陀区公办初中名额分配到校分析/index.html   （报告页）
  index.html                                    （站点入口页，扫描全部课题）
"""
import html
import os
import re
import sys

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
TOPIC = f"{ROOT}/analysis/普陀区公办初中名额分配到校分析"
REPORT = f"{TOPIC}/分析报告.md"
OUT_PAGE = f"{TOPIC}/index.html"
OUT_HOME = f"{ROOT}/index.html"
SITE_NAME = "上海学区房数据分析"
REPO_URL = "https://github.com/iStarFire/Shanghai-XueQuFang"

# ---------------------------------------------------------------- inline 标记

CJK = re.compile(r'[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]')


def esc(s):
    return html.escape(s, quote=False)


def markup(s):
    """对**已转义**的字符串施加行内标记。

    必须在多行合并**之后**调用——报告里存在跨行的 `**粗体**`
    （`**整体明显强于头部：…、\\n  上师大三附（+3.00）**`），
    逐行处理会匹配不到，在页面上留出裸 `**`。
    """
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s, flags=re.S)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s


def inline(s):
    return markup(esc(s))


def inline_multi(parts, sep='<br>'):
    return markup(sep.join(esc(p) for p in parts))


def glue(parts):
    """按中文排版习惯合并续行：两侧都是中日韩字符时不插空格。"""
    out = ''
    for p in parts:
        if out and not (CJK.search(out[-1]) and CJK.search(p[:1])):
            out += ' '
        out += p
    return out


_ctr = [0]


def slug(text):
    """给标题生成**稳定**的锚点 id。

    用递增计数器而不是 `hash()` 兜底——后者受 PYTHONHASHSEED 影响，
    会导致每次重新生成时锚点变化、旧链接失效。
    """
    s = re.sub(r'[^0-9a-zA-Z]+', '-', text).strip('-').lower()[:40]
    if s:
        return 'sec-' + s
    _ctr[0] += 1
    return f'sec-x{_ctr[0]}'


# ---------------------------------------------------------------- markdown

def md_to_html(md):
    """把报告用的 markdown 子集转成 HTML。

    支持：# ~ ###、> 引用、| 表格 |、- 列表、1. 列表、--- 分隔线、
    行内 **粗体** 与 `代码`。报告未使用更复杂的语法，故不引入解析库。
    """
    lines = md.split('\n')
    out, i = [], 0
    toc = []          # (level, text, id)
    used = {}

    def unique_id(base):
        n = used.get(base, 0)
        used[base] = n + 1
        return base if n == 0 else f'{base}-{n}'

    while i < len(lines):
        ln = lines[i]

        # --- 表格 ---
        if ln.startswith('|') and i + 1 < len(lines) and \
                re.match(r'^\|[\s:|-]+\|$', lines[i + 1]):
            head = [c.strip() for c in ln.strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append([c.strip() for c in lines[i].strip('|').split('|')])
                i += 1
            t = ['<div class="tw"><table>', '<thead><tr>']
            t += [f'<th>{inline(c)}</th>' for c in head]
            t.append('</tr></thead><tbody>')
            for r in rows:
                t.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>')
            t.append('</tbody></table></div>')
            out.append(''.join(t))
            continue

        # --- 引用块 ---
        if ln.startswith('>'):
            buf = []
            while i < len(lines) and lines[i].startswith('>'):
                buf.append(lines[i].lstrip('>').strip())
                i += 1
            body = inline_multi([x for x in buf if x])
            out.append(f'<blockquote>{body}</blockquote>')
            continue

        # --- 标题 ---
        m = re.match(r'^(#{1,4})\s+(.*)$', ln)
        if m:
            lv, text = len(m.group(1)), m.group(2).strip()
            sid = unique_id(slug(text))
            toc.append((lv, re.sub(r'\*\*|`', '', text), sid))
            out.append(f'<h{lv} id="{sid}">{inline(text)}</h{lv}>')
            i += 1
            continue

        # --- 分隔线 ---
        if re.match(r'^-{3,}$', ln.strip()):
            out.append('<hr>')
            i += 1
            continue

        # --- 列表 ---
        # 列表项要吸收「缩进续行」——报告里有跨行的粗体与跨行的分句，
        # 若不吸收续行，续行会被当成独立段落，粗体标记随之断裂。
        if re.match(r'^\s*([-*]|\d+\.)\s+', ln):
            ordered = bool(re.match(r'^\s*\d+\.\s+', ln))
            items = []
            while i < len(lines):
                m2 = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)$', lines[i])
                if m2:
                    items.append([m2.group(3)])
                    i += 1
                elif items and lines[i].strip() and lines[i][:1] in (' ', '\t'):
                    items[-1].append(lines[i].strip())
                    i += 1
                else:
                    break
            tag = 'ol' if ordered else 'ul'
            lis = ''.join(f'<li>{markup(esc(glue(x)))}</li>' for x in items)
            out.append(f'<{tag}>{lis}</{tag}>')
            continue

        # --- 空行 ---
        if not ln.strip():
            i += 1
            continue

        # --- 普通段落 ---
        buf = []
        while i < len(lines) and lines[i].strip() and \
                not lines[i].startswith(('|', '>', '#')) and \
                not re.match(r'^\s*([-*]|\d+\.)\s+', lines[i]) and \
                not re.match(r'^-{3,}$', lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        if not buf:
            # 以 | 开头但下一行不是表格分隔行的「孤立行」（如正文中的
            # 「|x|」绝对值记号出现在行首）：上面的段落循环不吸收它，
            # 若不在此推进 i，外层 while 会死循环（A6 曾触发过）。
            # 处置：按普通段落吸收该行。
            buf.append(lines[i].strip())
            i += 1
        out.append('<p>' + inline_multi(buf) + '</p>')

    return '\n'.join(out), toc


# ---------------------------------------------------------------- 样式

CSS = """
:root{
  --bg:#f7f8fa; --card:#fff; --fg:#1a1d21; --muted:#5b6470; --line:#e3e6ea;
  --accent:#1f6feb; --accent-soft:#eaf1fd; --warn:#b26a00; --warn-soft:#fff6e5;
  --ok:#1a7f37; --code-bg:#f0f2f5; --radius:10px;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#12141a; --card:#1a1d24; --fg:#e6e8eb; --muted:#9aa4b2; --line:#2a2f38;
    --accent:#6ea8fe; --accent-soft:#1c2739; --warn:#e2a03f; --warn-soft:#2a2314;
    --ok:#5ec27b; --code-bg:#232830;
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",
       "Microsoft YaHei","Noto Sans CJK SC",sans-serif;
  overflow-wrap:break-word;
}
.wrap{max-width:980px;margin:0 auto;padding:0 16px 64px}
header.top{
  background:var(--card);border-bottom:1px solid var(--line);
  position:sticky;top:0;z-index:20;backdrop-filter:saturate(150%) blur(8px);
}
header.top .wrap{padding-top:12px;padding-bottom:12px}
.crumb{font-size:.82rem;color:var(--muted)}
.crumb a{color:var(--accent);text-decoration:none}
h1{font-size:clamp(1.35rem,4.6vw,1.9rem);line-height:1.35;margin:.5em 0 .3em}
h2{font-size:clamp(1.15rem,3.8vw,1.45rem);margin:2em 0 .6em;
   padding-left:.55em;border-left:4px solid var(--accent);line-height:1.4}
h3{font-size:clamp(1.02rem,3.2vw,1.18rem);margin:1.6em 0 .5em;color:var(--fg)}
h4{font-size:1rem;margin:1.3em 0 .4em;color:var(--muted)}
p{margin:.7em 0}
a{color:var(--accent)}
hr{border:0;border-top:1px solid var(--line);margin:2em 0}
strong{font-weight:650}
code{background:var(--code-bg);padding:.12em .38em;border-radius:5px;
     font-family:var(--mono);font-size:.88em}
blockquote{
  margin:1em 0;padding:.8em 1em;background:var(--accent-soft);
  border-left:4px solid var(--accent);border-radius:0 var(--radius) var(--radius) 0;
  font-size:.95em;color:var(--fg);
}
blockquote strong{color:var(--warn)}
ul,ol{padding-left:1.35em;margin:.7em 0}
li{margin:.3em 0}
/* 表格：移动端横向滚动，首列吸附 */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1.1em 0;
    border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:.9rem;min-width:100%}
th,td{padding:.55em .7em;text-align:left;border-bottom:1px solid var(--line);
      white-space:nowrap}
th{background:var(--code-bg);font-weight:650;position:sticky;top:0;z-index:1}
tbody tr:last-child td{border-bottom:0}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--code-bg) 45%,transparent)}
td:first-child,th:first-child{position:sticky;left:0;background:var(--card);
      box-shadow:1px 0 0 var(--line);z-index:2;white-space:normal;min-width:8.5em}
th:first-child{background:var(--code-bg);z-index:3}
/* 目录 */
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
        padding:.9em 1.1em;margin:1.4em 0}
nav.toc h2{font-size:.95rem;margin:0 0 .5em;padding:0;border:0;color:var(--muted)}
nav.toc ol{margin:0;padding-left:1.3em;font-size:.92rem}
nav.toc li{margin:.22em 0}
nav.toc a{text-decoration:none}
/* 下载区 */
.dl{display:flex;flex-wrap:wrap;gap:.6em;margin:1.2em 0}
.dl a{display:inline-flex;align-items:center;gap:.4em;background:var(--card);
      border:1px solid var(--line);border-radius:999px;padding:.45em .95em;
      font-size:.88rem;text-decoration:none;color:var(--fg)}
.dl a:hover{border-color:var(--accent);color:var(--accent)}
/* 入口页卡片 */
.cards{display:grid;gap:14px;grid-template-columns:1fr;margin-top:1.6em}
@media(min-width:680px){.cards{grid-template-columns:1fr 1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
      padding:1.1em 1.2em;text-decoration:none;color:inherit;transition:.15s}
.card:hover{border-color:var(--accent);transform:translateY(-2px)}
.card h3{margin:0 0 .4em;font-size:1.05rem;color:var(--accent)}
.card p{margin:0;font-size:.9rem;color:var(--muted)}
.tag{display:inline-block;font-size:.75rem;padding:.1em .55em;border-radius:999px;
     background:var(--accent-soft);color:var(--accent);margin-bottom:.5em}
footer{color:var(--muted);font-size:.85rem;margin-top:3em;padding-top:1.2em;
       border-top:1px solid var(--line)}
@media print{
  header.top{position:static}body{background:#fff}
  .tw{overflow:visible}.dl,nav.toc{display:none}
}
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="description" content="{desc}">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<header class="top"><div class="wrap">
  <div class="crumb"><a href="{home}">← {site}</a></div>
  <h1>{h1}</h1>
</div></header>
<main class="wrap">
{toc}
{dl}
{body}
<footer>
  <p>数据与结论均来自官方 PDF，每个数字可回源到具体文件与页码。
     分析口径、方法与局限见页面内「局限声明」一节。</p>
  <p>仓库：<a href="{repo}">{repo}</a></p>
</footer>
</main>
</body>
</html>
"""

HOME = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="description" content="{desc}">
<title>{site}</title>
<style>{css}</style>
</head>
<body>
<header class="top"><div class="wrap">
  <div class="crumb">{site}</div>
  <h1>分析结论</h1>
</div></header>
<main class="wrap">
  <p>{desc}</p>
  <div class="cards">
{cards}
  </div>
  <footer>
    <p>所有原始文件与结论均可回源核验。仓库：
       <a href="{repo}">{repo}</a></p>
  </footer>
</main>
</body>
</html>
"""


def build_toc(toc):
    items = [t for t in toc if t[0] == 2]
    if not items:
        return ''
    lis = ''.join(f'<li><a href="#{sid}">{html.escape(txt)}</a></li>'
                  for _, txt, sid in items)
    return f'<nav class="toc"><h2>本页目录</h2><ol>{lis}</ol></nav>'


def build_dl():
    files = [
        ('宽表-初中水平-徐汇区-2022-2026.csv', '宽表 CSV（28 行 × 117 列）'),
        ('分析报告.md', '分析报告（Markdown）'),
        ('分析方法-名额到校.md', '分析方法'),
        ('剔除清单.md', '剔除清单'),
        ('缺分对清单.csv', '缺分对清单'),
    ]
    links = ''.join(f'<a href="{html.escape(f)}">⬇ {html.escape(t)}</a>'
                    for f, t in files if os.path.exists(f'{TOPIC}/{f}'))
    return f'<div class="dl">{links}</div>'


def topic_meta():
    """从报告里取标题与一句摘要，供入口页使用。"""
    md = open(REPORT, encoding='utf-8').read()
    m = re.search(r'^#\s+(.+)$', md, re.M)
    title = re.sub(r'\*\*|`', '', m.group(1)).strip() if m else '未命名课题'
    return title


def main():
    md = open(REPORT, encoding='utf-8').read()
    h1 = topic_meta()
    # 报告首行的 H1 已由页头承载，正文里再去掉一次，避免标题重复出现
    md_body = re.sub(r'^#\s+.*?\n', '', md, count=1)
    body, toc = md_to_html(md_body)

    page = PAGE.format(
        title=f'{h1} · {SITE_NAME}',
        desc='徐汇区公办初中「名额分配到校」竞争强度的 2022–2026 年分析结论',
        css=CSS,
        site=SITE_NAME,
        home='../',
        h1=html.escape(h1),
        toc=build_toc(toc),
        dl=build_dl(),
        body=body,
        repo=REPO_URL,
    )
    with open(OUT_PAGE, 'w', encoding='utf-8') as f:
        f.write(page)

    # 入口页：扫描 analysis/*/index.html
    cards = []
    adir = f'{ROOT}/analysis'
    for name in sorted(os.listdir(adir)):
        p = f'{adir}/{name}'
        if not os.path.isdir(p) or not os.path.exists(f'{p}/index.html'):
            continue
        t = topic_meta() if name == '徐汇区公办初中名额分配到校分析' else name
        sub = {'徐汇区公办初中名额分配到校分析':
               '2022–2026 年名额分配到校计划数与最低分数线，'
               '整理为 117 列初中宽表，给出「名额到校通道竞争强度」的排名与稳定性结论'}.get(name, '')
        cards.append(
            f'<a class="card" href="analysis/{name}/index.html">'
            f'<span class="tag">徐汇区</span><h3>{html.escape(t)}</h3>'
            f'<p>{html.escape(sub)}</p></a>')
    home = HOME.format(
        title=SITE_NAME, css=CSS, site=SITE_NAME,
        desc='围绕上海学区房的数据采集、整理、校验与分析结论。'
             '所有数字均可回源到官方原始文件与页码。',
        cards='\n'.join(cards) or '<p>暂无课题。</p>',
        repo=REPO_URL,
    )
    with open(OUT_HOME, 'w', encoding='utf-8') as f:
        f.write(home)

    print(f'已生成 {OUT_PAGE}')
    print(f'已生成 {OUT_HOME}')
    print(f'  正文 {len(body)} 字符，目录 {sum(1 for t in toc if t[0]==2)} 项，'
          f'入口卡片 {len(cards)} 个')


if __name__ == '__main__':
    sys.exit(main())
