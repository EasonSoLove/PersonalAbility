# finance-markdown 项目规则

1. 本目录是YAML/CSV/Markdown方案；不要修改相邻的旧版 `finance` 目录。
2. 先读取 `data/schema.json`、`data/funds.yaml` 和 `docs/model-entry-protocol.md`。
3. 正式交易唯一来源是 `data/transactions.csv`。持仓、成本、盈亏和现金流都是派生结果，不得手工写回。
4. 用户要求录入时，先生成批次并预检；含糊字段留空或询问，不猜测。
5. 使用 `scripts/import_transactions.py` 原子导入，不得绕过重复检查直接拼接CSV。
6. 导入后必须运行数据校验和报告生成。
7. 待确认交易不改变确认持仓；已作废交易不参与计算。
8. 新增基金时以天天基金为主来源；关联ETF不能唯一确认时留空。
9. 所有文本文件使用UTF-8；基金和ETF代码保持六位字符串。
10. 修改Schema时同步更新模板、脚本、文档和测试。