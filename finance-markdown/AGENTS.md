# finance-markdown 项目规则

1. 本目录是 YAML/CSV/Markdown 方案；只修改当前项目目录内的文件。
2. 先读取 `data/schema.json`、`data/funds.yaml` 和 `.agents/skills/cn-index-fund-analysis-files/docs/model-entry-protocol.md`。
3. 正式交易唯一来源是 `data/transactions.csv`；持仓、成本、盈亏和现金流都是派生结果，不得手工写回。
4. 交易录入只接受交易图片识别流程：使用 `.agents/skills/cn-index-fund-analysis-files/scripts/image_import.py` 预检和原子导入，不保留人工 CSV 录入入口。
5. 导入后必须运行 `validate_data.py` 和 `generate_reports.py`。
6. 待确认交易不改变确认持仓；已作废交易不参与计算。
7. 新增基金以天天基金为主来源；关联 ETF 不能唯一确认时留空。
8. 所有文本文件使用 UTF-8；基金和 ETF 代码保持六位字符串。
9. 技术面指标和解释以 `.agents/skills/cn-index-fund-analysis-files/docs/methodology.md` 为准；修改口径时同步更新脚本、测试和报告说明。