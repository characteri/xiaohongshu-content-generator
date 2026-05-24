---
name: xhs-writer-agent
description: 维护小红书 AI 写作助手：爆款参考搜索 + Streamlit + DeepSeek 写作。
---

# 核心架构

- `xhs_reference.py`：按主题搜 Top3 高互动笔记（Spider_XHS API）
- `reference_ui.py`：参考卡片展示
- `main.py`：Streamlit 入口
- `utils.py`：DeepSeek 写作，注入 `references_to_prompt()`

环境变量：`DEEPSEEK_API_KEY`、`XHS_COOKIES`

批量离线爬虫 `spider.py` 与在线写作无关，勿接入 main。
