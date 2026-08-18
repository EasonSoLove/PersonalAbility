---
name: cn-index-fund-analysis-files
description: 维护 finance-markdown 的 YAML/CSV/Markdown 基金账本、图片识别交易导入、持仓报告和完整 ETF 技术面分析。
---

# 中国指数基金文件化账本

本技能只操作当前 `finance-markdown` 项目，不修改相邻旧版 `finance` 目录。

## 目录边界

- `data/`：事实数据。`data/transactions.csv` 是正式交易唯一来源；持仓、成本、盈亏和现金流全部派生。
- `.agents/skills/cn-index-fund-analysis-files/scripts/`：项目脚本。
- `.agents/skills/cn-index-fund-analysis-files/docs/`：数据结构、录入协议、计算和技术面口径。
- `.agents/skills/cn-index-fund-analysis-files/imports/`：交易图片、图片识别 JSON、中间批次和提交归档。
- `reports/`：脚本生成的持仓、流水检查和技术面报告，不手工维护。

## 工作规则

1. 开始前读取 `data/schema.json`、`data/funds.yaml` 和 `docs/model-entry-protocol.md`。
2. 交易录入唯一用户入口是图片识别：根据交易图片生成识别 JSON，运行 `scripts/image_import.py` 先预检；不得提供人工填写 CSV 或绕过重复检查直接拼接账本。
3. 未从图片明确看到的字段留空，不猜日期、基金代码、份额、净值、手续费或到账金额；代码保持六位字符串。
4. 只有用户明确要求录入/写入/更新/确认/作废且预检通过时才使用 `--commit`。
5. 导入后必须运行 `scripts/validate_data.py` 和 `scripts/generate_reports.py`；失败批次不得改变正式账本。
6. 待确认交易不改变确认持仓，已作废交易保留历史行且不参与计算。
7. 新增基金以天天基金为主来源；关联 ETF 无法唯一确认时留空，不猜测。
8. 输出严格区分事实、固定计算、技术推断、分批条件、失效条件、风险和未来预测。

## 技术面口径

完整规则在 `docs/methodology.md`，脚本实现必须与该文档同步。默认使用关联 ETF 前复权日 K；完整分析至少 60 根日 K。无唯一 ETF 时可以用基金净值分析价格指标，但成交额倍数、放量/缩量和 OBV 不适用。

计算并报告：

- 趋势：MA5/10/20/60、价格相对均线距离、MA20 五日斜率、20/60 日高低点；
- 动量/趋势强度：5/10/20 日收益、MACD(12,26,9)、DMI14/+DI/-DI/ADX、ROC12、CR26；
- 摆动/偏离：RSI14、KDJ(9,3,3)、W&R14、CCI20、BIAS6/12/24；
- 波动：BOLL20(2σ)、中轨/上下轨/带宽/通道位置；
- 量价：ETF 成交额倍数和 OBV 当前值/5 日变化。

分析顺序为“趋势 → 动量 → 摆动 → 量价”，相关指标不简单多数表决。ADX 只表示趋势强度，超买/超卖不等于立即反转，BOLL 收缩不等于方向确定。

## 常用命令

```powershell
python .agents/skills/cn-index-fund-analysis-files/scripts/validate_data.py
python .agents/skills/cn-index-fund-analysis-files/scripts/image_import.py `
  .agents/skills/cn-index-fund-analysis-files/imports/samples/交易记录样例.jpeg `
  --recognition-json .agents/skills/cn-index-fund-analysis-files/imports/pending/识别结果.json
python .agents/skills/cn-index-fund-analysis-files/scripts/image_import.py `
  .agents/skills/cn-index-fund-analysis-files/imports/samples/交易记录样例.jpeg `
  --recognition-json .agents/skills/cn-index-fund-analysis-files/imports/pending/识别结果.json `
  --commit
python .agents/skills/cn-index-fund-analysis-files/scripts/generate_reports.py `
  --nav-json data/nav/latest-nav.json --technical --end YYYY-MM-DD
python tests/run_tests.py
```

## 输出顺序

1. 结论和精确截止日期；
2. 数据来源、净值确认状态和待确认交易；
3. 持仓计算或仅技术面分支；
4. 基金—指数—ETF 映射；
5. 技术指标分组和相互冲突的信号；
6. 分批条件、失效条件、风险和置信度。