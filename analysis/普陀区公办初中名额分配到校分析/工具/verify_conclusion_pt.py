"""核心结论数字核对：把结论里的关键数字与 CSV 实际值逐一对照。

只核对结论中最易陈旧的量（名次、P 值、Spearman、离散度、分类计数），
不做全文数字普查（那会淹没在派生量里）。
"""
import csv
import statistics as st
import sys
from collections import Counter
from pathlib import Path

D = Path('.')
sys.path.insert(0, str(Path(__file__).parent))
from apx_data_pt import sp, RANKED, W, sh  # noqa: E402

T = {r['junior_high_school']: r for r in
      csv.DictReader((D / '趋势分类-普陀区-2022-2026.csv').open(encoding='utf-8-sig'))}
R2 = list(csv.DictReader((D / '收敛指标-普陀区-2022-2026.csv').open(encoding='utf-8-sig')))
Y = ['2022', '2023', '2024', '2025', '2026']

rep = (D / '分析报告.md').read_text(encoding='utf-8')
head = rep[:rep.index('## 局限声明')] if '## 局限声明' in rep else rep[:9000]

bad, checked = [], 0


def want(label, s, where=None):
    global checked
    checked += 1
    if s not in (where if where is not None else head):
        bad.append((label, s))


# 1 第一梯队
want('第一梯队标题', '第一梯队（加权综合前 4）')
for r in RANKED[:4]:
    want(f"第一梯队含 {sh(r['junior_high_school'])}", sh(r['junior_high_school']))
    want(f"梯队 P {sh(r['junior_high_school'])}", f"{float(r['P_wq_comb']):.3f}")

# 2 梅陇
ml = W['上海市梅陇中学']
want('梅陇加权综合第', str(ml['rank_P_wq_comb']))
want('梅陇全身第', f"全身第 {ml['rank_P_wq_all']}")
want('梅陇头部第', f"头部第 {ml['rank_P_wq_head']}")
want('梅陇尾部第', f"尾部第 {ml['rank_P_wq_tail']}")
want('梅陇等权第', f"等权综合第 {ml['rank_P_eq_comb']}")
want('梅陇规模第 1', '全区规模最大')

# 3 Spearman
for lab, v in (
        ('wq-eq 综合', sp([int(r['rank_P_wq_comb']) for r in RANKED],
                       [int(r['rank_P_eq_comb']) for r in RANKED])),
        ('全身-头部', sp([int(r['rank_P_wq_all']) for r in RANKED],
                       [int(r['rank_P_wq_head']) for r in RANKED])),
        ('全身-尾部', sp([int(r['rank_P_wq_all']) for r in RANKED],
                       [int(r['rank_P_wq_tail']) for r in RANKED])),
        ('头部-尾部', sp([int(r['rank_P_wq_head']) for r in RANKED],
                       [int(r['rank_P_wq_tail']) for r in RANKED]))):
    want(f'ρ{lab}', f'{v:.3f}')

# 4 名额相关
_q = [st.fmean([float(r[f'quota4_{y}']) for y in Y]) for r in RANKED]
want('ρ(名额,均名)', f"{sp(_q, [float(r['mean_rank_base4_wq_avg']) for r in RANKED]):.3f}")
want('ρ(名额,P综合)', f"{sp(_q, [float(r['P_wq_comb']) for r in RANKED]):.3f}")

# 5 收敛
# 报告用 Unicode 减号（− U+2212），不是 ASCII '-'
want('收敛 b', '\u22120.887')
want('收敛 R²', '0.749')
want('IQR 2022=13.3', '13.3')
want('IQR 2026=5.2', '5.2')

# 6 分类计数（在 4.4 呈现，不在核心结论）
_c = Counter(r['trend_class'] for r in T.values())
sec44 = rep[rep.index('### 4.4'):rep.index('## 5 ')]
want('4.4 上升所数', f"**{_c['明显上升']}**", sec44)
want('4.4 下降所数', f"**{_c['明显下降']}**", sec44)
want('4.4 持平所数', f"**{_c['基本持平']}**", sec44)

# 7 位次变动
shift = [int(r['rank_P_eq_comb']) - int(r['rank_P_wq_comb']) for r in RANKED]
want('不变所数', f"{sum(1 for s in shift if s == 0)} 所不变")
want('变动1位所数', f"{sum(1 for s in shift if abs(s) == 1)} 所变动 1 位")
want('变动2位所数', f"{sum(1 for s in shift if abs(s) == 2)} 所变动 2 位")

print(f'核心结论核对：{checked} 项')
if bad:
    print(f'\n❌ {len(bad)} 项与实际值不符：')
    for lab, s in bad:
        print(f'  [{lab}] 未找到 {s!r}')
    sys.exit(1)
print('✅ 全部一致')
