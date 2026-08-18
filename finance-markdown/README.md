# 基金交易账本（YAML + CSV + Markdown）

这是从旧版 Excel 工作簿迁移出来的文件化方案。旧目录 `D:\05-Personal Project\PersonalAbility\finance\` 不参与本项目运行，也不会被自动同步或修改。

## 当前状态

- 基金档案：6 只
- 交易记录：34 笔
- 已确认：32 笔
- 待确认：2 笔
- 迁移基准日期：2026-08-17
- 最近确认净值日期：2026-08-14

## 目录分工

|位置|用途|维护方式|
|---|---|---|
|`data/funds.yaml`|基金名称、指数、关联 ETF、费率和来源|按基金资料维护|
|`data/transactions.csv`|正式交易账本，唯一交易事实来源|只能由原子导入程序写入|
|`data/nav/latest-nav.json`|最近确认净值缓存|按净值更新|
|`.agents/skills/cn-index-fund-analysis-files/scripts/`|校验、图片导入、持仓、技术面和报告脚本|代码维护|
|`.agents/skills/cn-index-fund-analysis-files/docs/`|数据结构、图片录入和技术面口径|规则维护|
|`.agents/skills/cn-index-fund-analysis-files/imports/`|图片示例、识别 JSON、中间批次和归档|图片流程维护|
|`reports/`|持仓、流水检查和技术面报告|脚本生成，不手工改|

## 交易录入：只使用图片识别

交易图片示例位于：`.agents/skills/cn-index-fund-analysis-files/imports/samples/交易记录样例.jpeg`。

1. 模型/视觉能力读取交易图片，生成识别结果 JSON；未看清的字段留空并标记 `uncertain_fields`。
2. 先预检：

```powershell
python .agents/skills/cn-index-fund-analysis-files/scripts/image_import.py `
  .agents/skills/cn-index-fund-analysis-files/imports/samples/交易记录样例.jpeg `
  --recognition-json .agents/skills/cn-index-fund-analysis-files/imports/pending/识别结果.json
```

3. 用户明确确认录入、更新或作废，且预检无错误后，才加 `--commit`：

```powershell
python .agents/skills/cn-index-fund-analysis-files/scripts/image_import.py `
  .agents/skills/cn-index-fund-analysis-files/imports/samples/交易记录样例.jpeg `
  --recognition-json .agents/skills/cn-index-fund-analysis-files/imports/pending/识别结果.json `
  --commit
```

脚本会将图片识别结果转换为内部批次，执行字段校验、重复检查和原子导入；成功提交的批次进入 `imports/archive/`，未提交批次留在 `imports/pending/`。用户不直接填写 CSV。

完整流程见 `.agents/skills/cn-index-fund-analysis-files/docs/model-entry-protocol.md`。

## 数据校验和报告

```powershell
python .agents/skills/cn-index-fund-analysis-files/scripts/validate_data.py
python .agents/skills/cn-index-fund-analysis-files/scripts/generate_reports.py --nav-json data/nav/latest-nav.json
python .agents/skills/cn-index-fund-analysis-files/scripts/generate_reports.py --nav-json data/nav/latest-nav.json --technical --end YYYY-MM-DD
python tests/run_tests.py
```

## 技术面

技术面脚本默认使用关联 ETF 前复权日 K，完整分析至少 60 根日 K，计算 MA、RSI、KDJ、MACD、W&R、DMI、BIAS、OBV、CCI、ROC、CR、BOLL、收益率、成交额倍数和 20/60 日区间位置。完整公式、参数、分析顺序和场外净值限制见 `.agents/skills/cn-index-fund-analysis-files/docs/methodology.md`。

正式账本只保存原始事实。当前份额、成本、市值、盈亏、回本要求、风险提醒和技术面都是派生结果。