"""普陀报告生成编排器：按固定顺序执行全部生成器。

顺序依赖（必须遵守）：
  1. build_v3.py               数据层（宽表 5 张 CSV + 派生列）
  2. build_tables_pt.py        第 4 章三张表
  3. build_tables_report_pt.py 第 2 章表 2-1/2-2、3.2 四线表、4.1 离散度
  4. build_ch5_pt.py           第 5 章 5.1-5.3（11 所预注册个案）整块替换第 5 章
  5. build_ch5_topic_pt.py     第 5 章 5.4 梅陇专题，必须在 4 之后

警告：4 会把第 5 章整块重写；若先跑 5，5.4 会被抹掉。
两个脚本各有断言拦截，不会静默丢失内容（已实测）。

用法：python3 工具/build_all_pt.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
STEPS = [
    ('build_v3.py', '数据层：宽表 5 张 CSV + 派生列'),
    ('build_tables_pt.py', '第 4 章三张表'),
    ('build_tables_report_pt.py', '第 2 章表、3.2 四线表、4.1 离散度'),
    ('build_ch5_pt.py', '第 5 章 5.1-5.3：11 所预注册个案'),
    ('build_ch5_topic_pt.py', '第 5 章 5.4：梅陇专题（用户指定）'),
]

fail = []
for script, desc in STEPS:
    print('>> %s - %s' % (script, desc))
    # 子进程必须在**分析目录**（脚本用相对路径读 CSV），而非 工具/
    r = subprocess.run([sys.executable, str(HERE / script)],
                       capture_output=True, text=True, cwd=str(HERE.parent))
    if r.returncode != 0:
        print('  FAILED:')
        for ln in (r.stderr.strip().split('\n') or ['(none)'])[-4:]:
            print('     %s' % ln)
        fail.append(script)
    else:
        for ln in [x for x in r.stdout.strip().split('\n') if x.strip()][-2:]:
            print('  %s' % ln)

print()
if fail:
    print('FAILED %d/%d: %s' % (len(fail), len(STEPS), fail))
    sys.exit(1)
print('OK all %d steps done (order fixed)' % len(STEPS))
