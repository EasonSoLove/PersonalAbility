# 数据源约定

## 主信源：天天基金

所有基金基础信息、费率、历史净值和基金页面链接优先使用天天基金，并记录精确查询日期。

- 基金主页：`https://fund.eastmoney.com/{基金代码}.html`
- 基金基本概况：`https://fundf10.eastmoney.com/jbgk_{基金代码}.html`
- 历史净值：`https://api.fund.eastmoney.com/f10/lsjz?fundCode={基金代码}&pageIndex=1&pageSize=200&startDate={开始日期}&endDate={结束日期}`
- 基金搜索：`https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?m=1&key={关键词}`
- ETF前复权日K：`https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={SecID}&klt=101&fqt=1&lmt=240&end={YYYYMMDD}&fields1=f1,f2,f3,f4,f5,f6,f7,f8&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61`

## 取数规则

1. 基金代码和ETF代码始终保存为六位字符串，不能丢失前导零。
2. 新基金先查询天天基金主页和基本概况，再同步到“基金信息”Sheet。
3. 场外联接基金的价格趋势可看净值K线；放量必须看关联场内ETF的成交额。
4. ETF拆分或份额折算时使用前复权日K，避免出现伪缺口。
5. 若天天基金未显示关联场内ETF代码，先通过基金名称、跟踪指数和基金搜索结果匹配；仍无法唯一确定时留空并报告，不猜测。
6. 每次同步填写“天天基金页面”和“信息同步日期”。缓存 `fund-map.json` 只用于加速，不替代重新核对。
7. 当日场外净值未确认时，持仓盈亏仍使用最近确认净值；当日ETF收盘只用于技术面。

## 网络受限时

使用现有 `fund-map.json` 和离线行情JSON运行，但在报告中标记“缓存数据”，不得声称已完成当日联网更新。