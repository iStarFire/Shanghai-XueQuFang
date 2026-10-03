# -*- coding: utf-8 -*-
"""2.1 嘉定区初中名录：同校改名归并 + 办学性质核实 + 派生列重算。

背景（任务 10-03-jiading-new-schools-recent3）：
  2026-10-03 查实三组「同一所学校、不同年份写法」，若不归并会被当成两所学校：

  | 旧名（早年写法）        | 规范名（最新写法）              | 依据                                   |
  |-------------------------|---------------------------------|----------------------------------------|
  | 上海市嘉定区德富路中学   | 交大附中附属嘉定德富中学        | 2022-02-21 更名；教育局官网确认公办     |
  | 上海市嘉定区杨柳初级中学 | 上海市嘉定区嘉二实验学校        | 教育局官网创建日期 2022.02、一贯制公办  |
  | 上海嘉定区世界外国语学校 | 上海嘉定区世外学校              | 学校官网「原名」；**民办**九年一贯制    |

依据 `.trellis/spec/quality/data-validation.md` 陷阱 7：
  显示名取**最新年份**写法，历年其他写法**单独记一列** `junior_high_school_former_names`
  （列名沿用徐汇区 `build_wide.py` 的既有做法，保持跨区一致）。

依据陷阱 8 的配套要求：
  陷阱 8 要求「按编号核对同一性」，但 `junior_high_school_code` 在宽表 43 行与
  分数线 466 行中**整列为空**（编号从未采集），故改用三重证据链，见 design.md 2.3。

办学性质：世外学校此前被「名称初判」误标为公办，本次按核实结果改为民办；
  `ownership_basis` 由原先全表同一句废话改为逐校实际依据。

注意：民办校多为**老校首次获得名额到校资格**，而非新办校
  （如华旭双语创建于 2015.9、怀少前身为 1941 年的怀少教育院），
  故 `ownership_basis` 与报告表述均不得把「2024 年首现」写成「新办」。

输出：就地覆写 `data/嘉定区/学校/初中名录-公办民办-嘉定区-2026.csv`
"""
import csv
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D_S = f'{ROOT}/data/嘉定区/学校'
ROSTER = f'{D_S}/初中名录-公办民办-嘉定区-2026.csv'
PLAN = [f'{D_S}/名额到校计划-嘉定区-2022-图片转录.csv',
        f'{D_S}/名额到校计划-嘉定区-2023-2026.csv']
SCORE = f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv'
YEARS = ['2022', '2023', '2024', '2025', '2026']

# 规范名 -> 旧名（同一实体）
ALIAS = {
    '交大附中附属嘉定德富中学': '上海市嘉定区德富路中学',
    '上海市嘉定区嘉二实验学校': '上海市嘉定区杨柳初级中学',
    '上海嘉定区世外学校': '上海嘉定区世界外国语学校',
}
OLD_OF = {v: k for k, v in ALIAS.items()}

# 办学性质核实结果（官网 / 官网之外的一手来源）
OWNERSHIP_VERIFIED = {
    '上海嘉定区世外学校': (
        '民办',
        '学校官网 shwfl.edu.cn「原为上海嘉定区世界外国语学校，是一所民办九年一贯制学校」；'
        '百度百科同表述。原判因名称不含「民办」二字而误标公办，本次修正'),
    '上海华旭双语学校': (
        '民办',
        '嘉定区教育局官网「学校查询·一贯制」页：办学性质=民办学校，创建日期 2015.9。'
        '原判依据为名称含「双语」，本次由官方名录页确认；注意其为 2015 年老校，'
        '2024 年系首次获得名额到校资格，非新办'),
    '上海嘉定区民办华盛怀少学校': (
        '民办',
        '名称含「民办」；前身为 1941 年创办的怀少教育院，亦系老校首次获得名额资格'),
    '上海市嘉定区嘉一实验初级中学': (
        '公办', '嘉定区教育局官网 + 2026 招生简章：四年制公办初级中学，2022-08 创办'),
    '上海师范大学附属第五嘉定实验学校': (
        '公办', '上海师大基建处官网 jjc.shnu.edu.cn：公办九年一贯制，2021-09 开学'),
    '交大附中附属嘉定洪德中学': (
        '公办', '嘉定区教育局官网「学校查询·初中」页：办学性质=公办，2021-09 建成启用'),
    '同济大学附属嘉定实验中学': (
        '公办', '嘉定区教育局官网「学校查询·初中」页：办学性质=公办，2021-07 创办'),
    '交大附中附属嘉定德富中学': (
        '公办', '嘉定区教育局官网「学校查询·初中」页：办学性质=公办；'
        '前身为 2015 年成立的德富路中学，2022-02-21 更名'),
    '上海市嘉定区嘉二实验学校': (
        '公办', '嘉定区教育局官网「学校查询·一贯制」页：办学性质=公办，创建日期 2022.02；'
        '前身为 1959 年创建的杨柳初级中学'),
}
DEFAULT_BASIS = '嘉定区教育局官网「学校查询」页核实业办性质'

# 陷阱 8 高风险对：名称高度相似但确为两所不同学校，禁止合并。
MUST_KEEP_SEPARATE = ('上海外国语大学嘉定外国语学校', '上海嘉定区世外学校')


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def index(paths):
    """{校名: {年份: [记录]}}"""
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        for r in load(p):
            d[r['junior_high_school']][r['year']].append(r)
    return d


def quota(plan, names, years):
    return sum(int(r.get('quota') or 0) for n in names for y in years
               for r in plan.get(n, {}).get(y, []))


def main():
    rows = load(ROSTER)
    plan, score = index(PLAN), index([SCORE])

    merged = collections.OrderedDict()
    for r in rows:
        # 名录里是**旧名行**，需映射到规范名（OLD_OF = 旧名 -> 规范名）
        r['junior_high_school'] = OLD_OF.get(r['junior_high_school'],
                                            r['junior_high_school'])
        merged.setdefault(r['junior_high_school'], []).append(r)

    out = []
    for canon, group in merged.items():
        r = dict(group[0])
        # names = 规范名 + 其旧名（ALIAS 是 规范名 -> 旧名，与 OLD_OF 方向相反）
        names = [canon] + ([ALIAS[canon]] if canon in ALIAS else [])

        py = sorted({y for n in names for y in plan.get(n, {})})
        sy = sorted({y for n in names for y in score.get(n, {})})

        own, basis = OWNERSHIP_VERIFIED.get(
            canon, (r.get('ownership') or '待核实', DEFAULT_BASIS))
        r.update({
            'ownership': own,
            'ownership_basis': basis,
            'plan_years': ';'.join(py),
            'score_years': ';'.join(sy),
            'years_included': str(len(sy)),
            'quota_total_2022': str(quota(plan, names, ['2022'])),
            'quota_total_2023_2026': str(quota(plan, names, YEARS[1:])),
            'junior_high_school_former_names': ALIAS.get(canon, ''),
        })
        out.append(r)

    out.sort(key=lambda r: (-len(r['score_years'].split(';')) if r['score_years'] else 0,
                            r['junior_high_school']))

    # ---------------- 自检（可失败）—— 必须在写文件之前
    names = [r['junior_high_school'] for r in out]
    assert len(names) == len(set(names)), f'归并后仍有重复校名：{len(names)} vs {len(set(names))}'
    for n in MUST_KEEP_SEPARATE:
        assert n in names, f'陷阱 8 高风险校缺失：{n}'
    for old in OLD_OF:
        assert old not in names, f'旧名未归并，仍是独立行：{old}'
    for r in out:
        assert r['ownership'] in ('公办', '民办'), f"ownership 非法：{r['junior_high_school']}"
    assert len(out) == 40, f'归并后应为 40 所，实际 {len(out)}'
    # 归并必须真的把旧名的年份并进来（曾两次因映射方向写反而静默失效）
    for canon, n_expect in (('交大附中附属嘉定德富中学', '5'),
                            ('上海市嘉定区嘉二实验学校', '5'),
                            ('上海嘉定区世外学校', '3')):
        got = next(r['years_included'] for r in out if r['junior_high_school'] == canon)
        assert got == n_expect, f'{canon} 年份数应为 {n_expect}，实际 {got}'
    n_former = sum(1 for r in out if r['junior_high_school_former_names'])
    assert n_former == 3, f'former_names 应有 3 条，实际 {n_former}'

    cols = ['junior_high_school', 'junior_high_school_former_names',
            'junior_high_school_code', 'district', 'ownership', 'ownership_basis',
            'plan_years', 'score_years', 'years_included',
            'quota_total_2022', 'quota_total_2023_2026', 'plan_quarter_lines']
    with open(ROSTER, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(out)
    n5 = sum(1 for r in out if r['years_included'] == '5')
    priv = [r['junior_high_school'] for r in out if r['ownership'] == '民办']
    print(f'名录 {len(out)} 所（原 43，归并 3 组）｜五年全勤 {n5} 所｜民办 {len(priv)} 所')
    print('民办名单：', '、'.join(priv))
    print('former_names 非空：',
          [(r['junior_high_school'], r['junior_high_school_former_names'])
           for r in out if r['junior_high_school_former_names']])
    print(f'写出 -> {ROSTER}')


if __name__ == '__main__':
    main()
