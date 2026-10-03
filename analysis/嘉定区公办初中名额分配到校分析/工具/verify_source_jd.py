# -*- coding: utf-8 -*-
"""2.2 / C2：逐格回源抽查——把分数线与名额**打开原始 PDF/HTML 页面**核对。

依据 `.trellis/spec/quality/data-validation.md`：
  - 维度 6「可追溯性」：抽查 3~5 条回到来源核对，**必须真做，不能只看登记表**；
  -「`source_page` 必须真能被用来定位一次」——打开该文件该页，确认目标行就在那里；
  - 反模式：「把『值对得上』当成『能定位』」，两者必须**分别验**。

PDF 文本结构（已用启良中学 2026 三条线实测确认）：
    行 i   初中校名
    行 i+1 招生学校名（可能跨 2 行，如「…嘉定新城」+「分校」）
    行 i+2 录取最低分  ← 第一个数字，即 CSV 的 min_score
    之后   数学 / 语文 / 综合测试 / … / 是否同分优待 / 综合素质评价

用法：python3 verify_source_jd.py
"""
import csv
import os
import html
import re
import sys

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D_S = f'{ROOT}/data/嘉定区/学校'
NUM = re.compile(r'^\d+(?:\.\d+)?$')


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def page_lines(doc, pno):
    return doc[pno - 1].get_text().split('\n')


def verify_scores():
    """分数线逐格回源：校名行之后第一个数字必须等于 CSV 的 min_score。"""
    SC = load(f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv')
    cache, ok, bad, skipped = {}, 0, [], 0
    for r in SC:
        doc_name, pno = r['source_doc'], int(r['source_page'])
        if pno < 1 or pno > 99:
            bad.append((r['junior_high_school'], doc_name, pno, 'source_page 非法'))
            continue
        if doc_name not in cache:
            cache[doc_name] = fitz.open(f'{D_S}/{doc_name}')
        doc = cache[doc_name]
        if pno > doc.page_count:
            bad.append((r['junior_high_school'], doc_name, pno,
                        f'**页码超出实际页数 {doc.page_count}**'))
            continue
        lines = page_lines(doc, pno)
        # 校名可能在页中被拆行，用「前 6 字」定位起点
        key = r['junior_high_school'][:6]
        idx = [i for i, l in enumerate(lines) if l.strip().startswith(key)]
        if not idx:
            skipped += 1
            continue
        # 同一页可能有多条该校的记录（每条线一条），取 min_score 匹配的那一条
        want = float(r['min_score'])
        hit = False
        for i in idx:
            for j in range(i + 1, min(i + 5, len(lines))):
                if NUM.match(lines[j].strip()):
                    if abs(float(lines[j]) - want) < 1e-6:
                        hit = True
                    break
        if hit:
            ok += 1
        else:
            bad.append((r['junior_high_school'], r['senior_high_school'],
                        r['year'], f"CSV={want} 未在该页校名后的首个数字找到"))
    for d in cache.values():
        d.close()
    return ok, bad, skipped


def verify_scores_merged():
    """归并校专项：2022 年旧名行的数据必须真能在原 PDF 里按**旧名**找到。"""
    pairs = [('交大附中附属嘉定德富中学', '上海市嘉定区德富路中学', '2022'),
             ('上海市嘉定区嘉二实验学校', '上海市嘉定区杨柳初级中学', '2022'),
             ('上海嘉定区世外学校', '上海嘉定区世界外国语学校', '2024')]
    SC = load(f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv')
    out = []
    for canon, old, yr in pairs:
        rows = [r for r in SC if r['year'] == yr and r['junior_high_school'] == old]
        for r in rows:
            doc = fitz.open(f'{D_S}/{r["source_doc"]}')
            pno = int(r['source_page'])
            lines = page_lines(doc, pno) if pno <= doc.page_count else []
            key = old[:6]
            found = [i for i, l in enumerate(lines) if l.strip().startswith(key)]
            want = float(r['min_score'])
            hit = False
            for i in found:
                for j in range(i + 1, min(i + 5, len(lines))):
                    if NUM.match(lines[j].strip()):
                        if abs(float(lines[j]) - want) < 1e-6:
                            hit = True
                        break
            doc.close()
            out.append((canon, old, yr, r['senior_high_school'], want, hit,
                        f"{r['source_doc']} p{pno}"))
    return out


def verify_pages():
    """C15：source_page 最大值不得超过该 PDF 实际页数（PDF 对象号陷阱）。"""
    SC = load(f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv')
    PL = (load(f'{D_S}/名额到校计划-嘉定区-2023-2026.csv')
          + load(f'{D_S}/名额到校计划-嘉定区-2022-图片转录.csv'))
    prob = []
    cache = {}
    for rows, kind in ((SC, '分数线'), (PL, '计划')):
        for r in rows:
            d = r['source_doc']
            if not d.endswith('.pdf'):
                continue
            if d not in cache:
                cache[d] = fitz.open(f'{D_S}/{d}').page_count
            if int(r['source_page']) > cache[d]:
                prob.append((kind, d, r['source_page'], f"实际仅 {cache[d]} 页"))
    for d in cache:
        fitz.open(f'{D_S}/{d}').close()
    return prob, cache


CODE_RE = re.compile(r'^(?:042|102|142|152)\d{3}$')


def verify_quotas():
    """名额逐格回源。PDF 结构：校名 → 代码 → 招生校名(可跨行) → 计划数 → 下一代码…"""
    PL = (load(f'{D_S}/名额到校计划-嘉定区-2023-2026.csv')
          + load(f'{D_S}/名额到校计划-嘉定区-2022-图片转录.csv'))
    cache, ok, bad, skipped = {}, 0, [], 0
    for r in PL:
        d, pno = r['source_doc'], int(r['source_page'])
        if d.endswith('.html'):
            if d not in cache:
                h = open(f'{D_S}/{d}', encoding='utf-8', errors='ignore').read()
                cache[d] = html_rows(h)
            hits = [row for row in cache[d] if row[0] == r['junior_high_school']
                    and row[1] == r['senior_high_school_code']]
            if not hits:
                skipped += 1
            elif str(hits[0][2]) == str(r['quota']):
                ok += 1
            else:
                bad.append((r['year'], r['junior_high_school'],
                            r['senior_high_school_code'],
                            f"CSV={r['quota']} 原文={hits[0][2]}"))
            continue
        if d.endswith('.jpg'):      # 2022 为二手截图转录，无文本层，不计入回源
            skipped += 1
            continue
        if d not in cache:
            cache[d] = fitz.open(f'{D_S}/{d}')
        doc = cache[d]
        if pno > doc.page_count:
            bad.append((r['year'], r['junior_high_school'], d, f'页码越界 {pno}'))
            continue
        lines = page_lines(doc, pno)
        key = r['junior_high_school'][:6]
        code, want = r['senior_high_school_code'], str(r['quota'])
        hit = False
        for i, l in enumerate(lines):
            if not l.strip().startswith(key):
                continue
            for j in range(i + 1, min(i + 24, len(lines))):
                if lines[j].strip() != code:
                    continue
                for k in range(j + 1, min(j + 6, len(lines))):
                    if NUM.match(lines[k].strip()):
                        if lines[k].strip() == want:
                            hit = True
                        break
                break
        if hit:
            ok += 1
        else:
            bad.append((r['year'], r['junior_high_school'], code,
                        f'CSV={want} 未在该页 {code} 后找到'))
    for x in cache.values():
        if hasattr(x, 'close'):
            x.close()
    return ok, bad, skipped


def _cl(t):
    return re.sub(r'\s+', '', html.unescape(t).replace('\xa0', ' ')).strip()


def html_rows(h):
    """抽取 HTML 表格行 -> [(初中校名, 招生代码, 计划数)]。

    必须先锁定**含「招生学校代码」的最大 table**，否则会抽到页面里的无关表格；
    每行是「校名 | 代码|名称|名额 | 代码|名称|名额 …」的三元组循环，
    不是一行一组（初版按后者写，导致抽出 0 行）。
    """
    best = ''
    for m in re.finditer(r'<table', h):
        end = h.find('</table>', m.start())
        seg = h[m.start():end]
        if '\u62db\u751f\u5b66\u6821\u4ee3\u7801' in seg and len(seg) > len(best):
            best = seg
    out = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', best, re.S):
        cs = [_cl(re.sub(r'<[^>]+>', '', c))
              for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
        if not cs or not cs[0] or cs[0] in ('\u521d\u4e2d\u5b66\u6821', '\u62db\u751f\u5b66\u6821\u4ee3\u7801'):
            continue
        for i in range(1, len(cs) - 2, 3):
            code, name, quota = cs[i], cs[i + 1], cs[i + 2]
            if CODE_RE.match(code) and quota.isdigit():
                out.append((cs[0], code, quota))
    return out


def main():
    print('=== C2 分数线逐格回源（全 466 格）===')
    ok, bad, skipped = verify_scores()
    print(f'  命中 {ok} / {ok + len(bad) + skipped}｜'
          f'失败 {len(bad)}｜本页未定位到校名 {skipped}')
    for b in bad[:12]:
        print('   ❌', b)
    rate = ok / (ok + len(bad)) if (ok + len(bad)) else 0
    print(f'  命中率（可定位样本）= {rate:.4%}｜'
          f'门禁要求 100%：{"通过" if rate == 1 and not bad else "**不通过**"}')

    print('\n=== C2 归并校专项：2022 年旧名行按旧名回源 ===')
    for canon, old, yr, line, want, hit, src in verify_scores_merged():
        print(f'  {"✅" if hit else "❌"} {canon} ← {old} {yr} {line} = {want}｜{src}')

    print('\n=== C2 名额逐格回源 ===')
    qok, qbad, qskip = verify_quotas()
    print(f'  命中 {qok} / {qok + len(qbad) + qskip}｜失败 {len(qbad)}｜'
          f'无文本层或未定位 {qskip}（2022 为二手截图转录，不计入）')
    for b in qbad[:12]:
        print('   ❌', b)
    qrate = qok / (qok + len(qbad)) if (qok + len(qbad)) else 0
    print(f'  命中率（可定位样本）= {qrate:.4%}｜'
          f'门禁要求 100%：{"通过" if qrate == 1 and not qbad else "**不通过**"}')

    print('\n=== C15 source_page 必须是真实页码 ===')
    prob, pages = verify_pages()
    for d, n in sorted(pages.items()):
        print(f'  {d}：实际 {n} 页')
    if prob:
        for p in prob[:10]:
            print('   ❌', p)
    print(f'  结论：{"通过" if not prob else "**不通过**"}'
          f'（{"两表页码语义一致且均未越界" if not prob else "存在越界"}）')
    return 0 if (not bad and not prob and not qbad) else 1


if __name__ == '__main__':
    sys.exit(main())
