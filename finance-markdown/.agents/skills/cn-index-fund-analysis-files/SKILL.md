---
name: cn-index-fund-analysis-files
description: Maintain and analyze the YAML/CSV/Markdown Chinese index-fund project in finance-markdown. Use for manual or model batch transaction entry, pending-trade updates, duplicate checks, fund metadata sync, portfolio cost/P&L calculation, Markdown reports, and ETF technical analysis without Excel.
---

# 中国指数基金文件化账本与技术分析

本技能只操作当前 `finance-markdown` 项目，不修改相邻旧版 `finance` 文件夹。

## 数据源

- `data/funds.yaml`：基金档案和基金—指数—ETF映射。
- `data/transactions.csv`：正式交易账本，唯一交易事实来源。
- `data/nav/latest-nav.json`：最近确认净值缓存。
- `inbox/batches/*.csv`：人工或模型生成的待导入批次。
- `generated/*.md`：脚本生成的派生报告，不手工维护。

## 标准流程

1. 锁定绝对日期、净值确认日期和待确认状态。
2. 读取 `data/schema.json`、`data/funds.yaml`、`docs/model-entry-protocol.md`。
3. 运行 `scripts/validate_data.py`；数据错误未解决前不计算投资结论。
4. 新增基金时以天天基金为主来源。先运行 `tiantian_fund_info.py` 输出查询JSON，再用 `merge_fund_info.py` 合并；ETF无法唯一确认时留空。
5. 用户要求录入交易时，把输入转换为标准批次CSV；未提供字段留空，不猜测。
6. 先运行 `import_transactions.py` 预检。疑似重复、多个待确认候选或无效字段必须停止。
7. 用户意图已经明确为录入/更新/作废且预检通过时，使用 `--commit` 原子写入。
8. 导入后再次校验，并运行 `generate_reports.py`。
9. 有确认持仓时输出成本、市值、盈亏和技术面；无持仓时仅输出技术面。
10. 把事实、固定计算、技术推断和未来预测分开表达。

## 交易录入原则

- 空值表示未知，`0` 表示已经确认是零。
- 待确认交易不改变确认持仓。
- 更新优先使用交易ID；无ID时只有唯一匹配才可更新。
- 作废交易保留历史行，不直接删除。
- 转换转入/转出使用相同关联交易ID。
- 正式账本不得直接拼接；必须经过批次预检和原子导入。
- 失败批次不得改变正式账本。

## 固定计算

- 买入、定投、转换转入增加份额，成本为成交金额加手续费。
- 卖出、转换转出按移动加权平均成本减少份额。
- 卖出到账优先，其次成交金额，最后才估算并报警。
- 现金分红计入已实现现金流。
- 回本所需涨幅为未弥补亏损除以当前市值。

## 快速命令

```powershell
python scripts/validate_data.py
python scripts/import_transactions.py inbox/batches/批次.csv --source 人工
python scripts/import_transactions.py inbox/batches/批次.csv --source 人工 --commit
python scripts/generate_reports.py --nav-json data/nav/latest-nav.json
python scripts/generate_reports.py --nav-json data/nav/latest-nav.json --technical --end YYYY-MM-DD
python tests/run_tests.py
```

## 输出顺序

1. 结论和精确截止日期；
2. 数据来源、净值确认状态和待确认交易；
3. 分析分支；
4. 成本、市值、盈亏、回本要求和流水问题；
5. 基金—指数—ETF映射；
6. 技术面；
7. 分批条件和失效条件；
8. 风险、假设和置信度。