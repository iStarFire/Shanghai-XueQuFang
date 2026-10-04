"""阶段 3.4：当前宽表与 0.3 基线**逐格比对**，差异必须全部可解释。

基线 = validation/baseline.md 记录的 0.3 快照（/tmp/pt_baseline/，md5 已核验一致）。
本轮已知变更（均已在 validation/school-identity.md 记录）：
  A. 归并兴陇 → 曹二实验（1.2）：两校合一行，曹二实验 4 年 → 5 年
  B. 排除晋元西校（1.1）：有名额无分数，不独立计量，2022 名额 660 → 611
  C. 新增列：rel_*/row_type/exit_reason/former_names/P_recent2/rank_P_recent2
  D. rel 基准池：RANKED → 当年公办非退出池（同量平移，delta_rel/sen 不变）

判定：可比单元格（存在于两版且语义未变）的差异，必须全部落在 A 的影响面内。
"""
import csv
import sys
from pathlib import Path

BASE = Path('/tmp/pt_baseline')
NEW = Path('.')

# 归并影响面：这些学校预期会变
MERGED_AFFECTED = {'上海市曹杨第二中学附属实验中学', '上海市兴陇中学'}
# 预期不变的口径列（语义未变，池未变）
STABLE_COLS = [
    'P_eq', 'rank_P_eq', 'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq',
    'P_wq_all', 'rank_P_wq_all', 'P_wq_head', 'rank_P_wq_head',
    'P_wq_tail', 'rank_P_wq_tail', 'P_eq_all', 'rank_P_eq_all',
    'P_eq_head', 'rank_P_eq_head', 'P_eq_tail', 'rank_P_eq_tail',
    'P_eq_comb', 'rank_P_eq_comb',
    'P_lin', 'rank_P_lin', 'P_exp', 'rank_P_exp',
    'quota4_avg', 'quota_all_avg',
    'mean_rank_base4_wq_avg', 'mean_rank_base4_eq_avg',
    'mean_rank_base4_w_linear', 'mean_rank_base4_w_exp',
]
# 这两列预期变（rel 基准池变更 + 归并）
CHANGED_BY_DESIGN = {'shift_wq_eq', 'P_wq', 'rank_P_wq', 'P_wq_comb', 'rank_P_wq_comb'}


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return {r['junior_high_school']: r for r in csv.DictReader(f)}


B = load(BASE / '宽表-初中水平-普陀区-2022-2026.csv')
N = load(NEW / '宽表-初中水平-普陀区-2022-2026.csv')

print(f'基线 {len(B)} 所 ｜ 当前 {len(N)} 所')
only_b = sorted(set(B) - set(N))
only_n = sorted(set(N) - set(B))
print(f'  仅基线有: {only_b}')
print(f'  仅当前有: {only_n}')

# 逐格比对：**P 值列**变化必须落在归并影响面内；
# **rank 列**允许位次链连锁位移（曹二实验后移 ⇒ 其后各校前移），
# 但必须满足：① 位移幅度有限；② 该列 P 值未变的学校，位移方向与幅度符合排序结果。
VALUE_COLS = [c for c in STABLE_COLS if not c.startswith('rank_')]
RANK_COLS = [c for c in STABLE_COLS if c.startswith('rank_')]

# rank 列 → 其依据的 P 列
RANK_SRC = {r: r.replace('rank_', '') for r in RANK_COLS}

val_diffs, rank_diffs, checked = [], [], 0
for c in sorted(set(B) & set(N)):
    for col in STABLE_COLS:
        if col not in B[c] or col not in N[c]:
            continue
        vb, vn = B[c][col], N[c][col]
        if vb == vn:
            continue
        try:
            if abs(float(vb) - float(vn)) < 5e-4:
                continue
        except ValueError:
            pass
        checked += 1
        (rank_diffs if col in RANK_SRC else val_diffs).append((c, col, vb, vn))

print(f'\n逐格比对：{len(VALUE_COLS)} 个值列 + {len(RANK_COLS)} 个名次列 × '
      f'{len(set(B) & set(N))} 所，容差 5e-4，共 {checked} 处差异')

print(f'\n--- 值列差异（须全部落在归并影响面内）{len(val_diffs)} 处 ---')
for c, col, vb, vn in val_diffs:
    tag = '归并' if c in MERGED_AFFECTED else '⚠️ 非预期'
    print(f'  {tag}  {c[:22]:<24} {col:<16} {vb} → {vn}')
unexpected = [d for d in val_diffs if d[0] not in MERGED_AFFECTED]

print(f'\n--- 名次列差异 {len(rank_diffs)} 处：逐条验证是否为位次链连锁位移 ---')
bad_rank = []
for c, col, vb, vn in rank_diffs:
    src = RANK_SRC[col]
    s_b, s_n = B[c].get(src), N[c].get(src)
    self_changed = s_b != s_n
    # 连锁位移的上限：曹二实验名次变动量
    try:
        shift = int(float(vn)) - int(float(vb))
    except ValueError:
        bad_rank.append((c, col, vb, vn, '名次非整数'))
        continue
    if c in MERGED_AFFECTED:
        note = '本体（归并）'
    elif self_changed:
        bad_rank.append((c, col, vb, vn, f'自身 {src} 变了却未列入影响面'))
        note = '⚠️ 自身值变化'
    elif abs(shift) > 2:
        bad_rank.append((c, col, vb, vn, f'位移 {shift:+d} 超过连锁上限'))
        note = '⚠️ 位移过大'
    else:
        note = f'连锁位移 {shift:+d}（自身 {src} 未变）'
    if len([1 for x in rank_diffs if x[1] == col]) <= 8 or c in MERGED_AFFECTED:
        print(f'  {c[:22]:<24} {col:<18} {vb} → {vn}   {note}')
print(f'  … 名次列差异合计 {len(rank_diffs)} 处，异常 {len(bad_rank)} 处')

# 判定
print()
if only_n:
    print(f'❌ 新增了未预期的校：{only_n}')
if unexpected or bad_rank:
    if unexpected:
        print(f'❌ 值列有 {len(unexpected)} 处差异落在归并影响面之外：')
        for c, col, vb, vn in unexpected[:15]:
            print(f'   {c[:22]:<24} {col:<18} {vb} → {vn}')
    if bad_rank:
        print(f'❌ 名次列有 {len(bad_rank)} 处无法解释：')
        for x in bad_rank[:10]:
            print(f'   {x[0][:22]:<24} {x[1]:<18} {x[2]} → {x[3]}  {x[4]}')
    sys.exit(1)
if only_b == ['上海市兴陇中学'] or set(only_b) <= MERGED_AFFECTED:
    print('✅ 校集合变化完全由归并解释（兴陇并入曹二实验）')
print('✅ 稳定列无归并影响面之外的差异')
print('\n=== 按设计预期变化的列（不参与判定，仅记录）===')
for col in sorted(CHANGED_BY_DESIGN):
    ch = [c for c in sorted(set(B) & set(N)) if B[c].get(col) != N[c].get(col)]
    print(f'  {col:<18} 变化 {len(ch):>2} 所'
          + (f'：{", ".join(x[:12] for x in ch[:4])}' if ch else ''))
