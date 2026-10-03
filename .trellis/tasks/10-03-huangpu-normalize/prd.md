# 黄浦计划表高中名归一 + 双源 join 校验

## Goal

计划表 28 个去重招生学校名实际只约 15 所：2024 整年用简称（格致奉贤/卢高/华二附中/向明浦江等 12 个）、2024 把「上海市上海中学」写成「上海中学」。导致 2024 看似招生学校 14→25 实为同一批、且计划↔分数线大面积 join 失败。需建立高中名归一表、修正 CSV、加入 join 完整率门禁。依赖 huangpu-reextract。

## Requirements

- TBD

## Acceptance Criteria

- [ ] TBD

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
