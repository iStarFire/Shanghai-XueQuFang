# 修复三区网页版下载区：改为自动扫描目录

## Goal

普陀 build_html_pt.py 的 build_dl() 文件清单整段复制自徐汇，os.path.exists 把 4 个不存在的文件全过滤掉，导致 6 个 CSV 的下载入口全部消失（只剩分析报告）；嘉定只列了 2 个 CSV，缺 4 个；徐汇漏列趋势分析与两个 rank 表。根因是硬编码清单。改为按标签表自动扫描课题目录，三处一起改，并新增门禁断言：下载项数 == 目录内交付物数、无交付物缺入口、链接全部指向真实文件、不含他区文件

## Requirements

- TBD

## Acceptance Criteria

- [ ] TBD

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
