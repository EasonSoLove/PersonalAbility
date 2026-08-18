# 基金交易账本（YAML + CSV + Markdown）

这是从旧版 Excel 工作簿独立迁移出来的新方案。旧目录 `D:\05-Personal Project\PersonalAbility\finance\` 不参与本项目运行，也不会被自动同步或修改。

## 当前状态

- 基金档案：6只
- 交易记录：34笔
- 已确认：32笔
- 待确认：2笔
- 迁移基准日期：2026-08-17
- 最近随项目迁移的确认净值日期：2026-08-14

## 文件分工

|位置|用途|是否手工修改|
|---|---|---|
|`data/funds.yaml`|基金名称、指数、关联ETF、费率和来源|可以|
|`data/transactions.csv`|正式交易账本，唯一交易事实来源|可以，但推荐通过批次导入|
|`data/nav/latest-nav.json`|最近确认净值缓存|可以由模型或脚本更新|
|`inbox/transaction-template.csv`|人工和模型共用的录入模板|复制后填写|
|`inbox/batches/`|尚未导入的交易批次|可以|
|`archive/imported-batches/`|成功导入的原始批次|不要修改|
|`generated/`|持仓、流水检查和技术面报告|不要手工修改|
|`analysis/`|按日期保存的投资分析|可以补充文字|

## 最简单的人工录入

1. 复制 `inbox/transaction-template.csv` 到 `inbox/batches/`。
2. 删除模板中的示例行，填写一笔或多笔交易。
3. 先预检：

```powershell
python scripts/import_transactions.py inbox/batches/你的批次.csv --source 人工
```

4. 确认预检摘要无误后正式导入：

```powershell
python scripts/import_transactions.py inbox/batches/你的批次.csv --source 人工 --commit
```

5. 生成报告：

```powershell
python scripts/generate_reports.py --nav-json data/nav/latest-nav.json
```

## 让模型批量录入

可以直接描述：

> 录入三笔交易：8月17日买入020973共1000元，待确认；8月18日买入021934共500元，待确认；把交易TX-...更新为已确认，确认份额为xxx。

模型应当：

1. 把自然语言转换成 `inbox/batches/YYYY-MM-DD-NNN.csv`；
2. 不猜测未提供的确认日期、份额、净值、手续费或到账金额；
3. 运行预检；
4. 汇报新增、更新、作废、缺失字段和疑似重复；
5. 用户已经明确说“录入/更新/作废”时，验证通过后可以提交；仅说“整理/看看”时不得提交；
6. 导入后重新生成持仓与检查报告。

完整规则见 `docs/model-entry-protocol.md`。

## 批次中的操作

- `新增`：交易ID可空，由系统生成。
- `更新`：必须填写已有交易ID；空字段表示保留原值。
- `作废`：必须填写已有交易ID；不会删除历史行。
- 如需主动清空字段，填写 `__CLEAR__`、`清空` 或 `【清空】`。

## 数据检查

```powershell
python scripts/validate_data.py
```

检查范围包括基金代码、交易ID、日期和数值格式、确认状态、疑似重复、转换配对和关联ETF格式。

## 重新计算

正式账本只保存原始事实。当前份额、成本、盈亏、市值、回本所需涨幅和风险提醒全部由固定脚本计算，不要把派生值重新写回 `transactions.csv`。