---
name: cn-index-fund-analysis
description: Analyze and maintain Chinese index-fund and ETF-link portfolio workbooks using 天天基金 as the primary source. Use in this finance project to add or refresh funds in the 基金信息 sheet, map OTC funds to target ETFs, decide between technical-only and portfolio-plus-technical analysis, reconcile transaction ledgers, calculate cost/P&L/break-even with fixed scripts, or analyze K-lines, turnover expansion, MA5/10/20/60, RSI, support, resistance, and staged trade conditions for any supported fund—not only the initial five funds.
---

# 中国指数基金流水与技术面分析

以工作簿、天天基金数据和可复算脚本生成带日期的分析。投资结论属于不确定决策，不承诺回本或收益。

## 标准流程

1. **锁定时间边界。** 写明当前日期、市场是否收盘、场外基金当日净值是否已确认。持仓盈亏只用最近确认净值；未确认当日仅用关联ETF收盘分析技术面。
2. **读取Schema。** 先读 `references/workbook-schema.json` 和 `references/workbook-schema.md`，再读取工作簿。字段按表头名称定位，不依赖固定列号。
3. **收集基金代码。** 合并“基金信息”和“交易流水”中的代码，保留六位格式。
4. **先补基金信息。** 对基金信息缺失、过期或关联ETF为空的代码，按 `references/sources.md` 查询天天基金，运行 `scripts/tiantian_fund_info.py` 标准化结果，并同步到“基金信息”Sheet。无法唯一匹配ETF时留空并说明，不猜测。
5. **验证模板。** 运行 `scripts/validate_workbook.py`。如Schema变化，必须同时更新JSON、工作簿模板、脚本和测试。
6. **判断分析分支。** 运行 `scripts/portfolio_analysis.py`：
   - 无交易记录或确认持仓为零：仅分析技术面；
   - 有确认持仓：结合成本、盈亏、交易行为和技术面；
   - 有待确认交易：单列，不从确认持仓中扣除。
7. **计算技术指标。** 运行 `scripts/technical_analysis.py`。趋势使用前复权ETF日K；量能使用ETF成交额。普通场外指数基金若无关联ETF，只分析净值趋势，不分析放量。
8. **综合判断。** 不因低于成本而自动加仓。按技术信号质量、组合重合、持仓比例、现金预算和失效条件排序。

## 快速命令

```powershell
python scripts/validate_workbook.py "基金交易记录与仓位分析.xlsx"
python scripts/tiantian_fund_info.py 021934 023652 --cache references/fund-map.json
python scripts/portfolio_analysis.py "基金交易记录与仓位分析.xlsx" --nav-json latest-nav.json
python scripts/technical_analysis.py --mapping references/fund-map.json --end YYYY-MM-DD
python scripts/technical_analysis.py 000001 --mapping mapping.json --nav-bars-json nav-bars.json --end YYYY-MM-DD
python scripts/run_analysis.py "基金交易记录与仓位分析.xlsx" --mapping references/fund-map.json --nav-json latest-nav.json --end YYYY-MM-DD
python tests/smoke_test.py --workbook "基金交易记录与仓位分析.xlsx"
```

使用Codex捆绑Python时替换命令中的 `python`。联网受限时可传入离线JSON，但必须标记缓存日期。

## 固定计算规则

- 买入、定投、转换转入：增加确认份额，成本为成交金额加手续费。
- 卖出、转换转出：按移动加权平均成本减少份额；实际到账优先，其次成交金额，最后才用份额×净值−费用估算。
- 待确认交易不改变已确认持仓。
- 现金分红计入已实现现金流。
- 分开报告表内成本、外部净现金投入和整个账户历史本金，不混用。
- 回本所需涨幅=`max(累计未弥补亏损,0)/当前市值`。
- 固定报警：转换记录不成对、卖出缺金额、公式错误、止盈标签与实际盈亏矛盾、短期快速建仓、无条件越跌越买、只有买入的“再平衡”。

## 技术面规则

- 计算MA5/10/20/60、5/10/20日收益、RSI14、距MA20/MA60、MA20五日斜率、20/60日高低点和当日成交额/前5日平均成交额。
- 成交额倍数：`<1.0`缩量；`1.0–1.2`轻微放量；`1.2–1.5`中等放量；`>=1.5`明显放量。
- 站上MA20不等于反转。MA20仍向下且价格未站稳MA60时，通常只定义为反弹或反转尝试。
- 买入至少要求两个独立条件，例如缩量回踩MA20企稳，或放量突破压力/MA60并次日确认。
- 先写失效条件，再写买入条件。常用失效：连续两日收于MA20下、MA5下穿MA10、放量突破失败或组合回撤触发上限。
- 对ETF拆分使用前复权数据；不要把场外基金页面的人气或估值当作成交量。

## 数据源

天天基金是本项目保留的主信源。读取 `references/sources.md`。每次新增基金都保存基金页面、同步日期、关联ETF代码和行情SecID。`references/fund-map.json` 是缓存，不是永久真相。

## 输出顺序

1. 结论和精确截止日期
2. 数据来源、净值确认状态和待确认交易
3. 分支说明：仅技术面或持仓+技术面
4. 有持仓时：成本、市值、盈亏、回本要求和流水问题
5. 基金—指数—ETF映射
6. 技术面仪表盘和逐只K线判断
7. 分批条件、金额、支撑压力和失效条件
8. 风险、假设和置信度

把事实、固定计算、技术推断和未来预测分开表达。