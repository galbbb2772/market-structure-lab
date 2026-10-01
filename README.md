# Market Structure Lab

独立的美股市场结构研究站。当前目标是把市场结构、三大指数涨跌比、行业活跃度、宏观观测和历史条件频率放在同一套可审计页面中。

## 当前模块

- **历史箱体**：20交易日小箱体 / 60交易日大箱体，保留检测时间、上下沿、持续交易日和描述性评分。
- **三大指数涨跌比**：仅统计 S&P 500、Nasdaq Composite、Dow Jones；支持日/月/年与自定义历史区间。
- **涨跌幅分布**：上涨/下跌数量、涨跌比、涨跌占比、上涨/下跌幅中位数、历史百分位、5%/95%分位、2σ极端波动频率和正态参照。
- **市场阶段历史频率**：用 S&P 500 的200日均线位置和均线斜率构造牛市/震荡/熊市代理，统计1/5/20交易日后历史上涨/下跌频率。样本少于60不展示概率。
- **行业活跃度**：行业ETF成交金额和单日振幅相对过去60个交易日的百分位代理。
- **宏观观测**：FRED 最新/修订历史，仅作研究展示，不冒充 point-in-time vintage。

## 原则

1. 不修改 Frozen V4 正式策略规则；新研究先独立验证。
2. 不把事后信息用于当时信号；箱体最快在 `detected_at` 后下一交易日生效。
3. 不把探索性历史频率表述成未来已验证概率。
4. 公共仓库只放指数/ETF和汇总研究，不放私人全美股/退市股原始库或正式候选名单。

## 本地生成数据

```bash
python -m pip install -r requirements.txt
python build_structure_lab.py
python -m unittest discover -s tests -v
```

生成的数据写入 `docs/data/structure_lab.json`。GitHub Actions 在美股工作日自动刷新，也支持手动运行。

网站入口：`docs/structure-lab.html`。如果开启 GitHub Pages，建议将发布源设为 `main / docs`。
