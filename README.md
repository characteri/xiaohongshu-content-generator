# 爆款小红书 AI 写作助手

按主题搜索小红书高互动笔记 → 提炼参考 → DeepSeek 生成文案。

## 怎么跑

```bash
cp .env.example .env   # 填 DEEPSEEK_API_KEY、XHS_COOKIES
pip install -r requirements.txt
npm install            # 小红书签名需要
streamlit run main.py
```

## 目录说明

| 文件/目录 | 作用 |
|-----------|------|
| `main.py` | 网页界面入口 |
| `xhs_reference.py` | 按关键词搜 Top3 笔记，生成概要 |
| `reference_ui.py` | 三列参考卡片 UI |
| `utils.py` | 调用 DeepSeek 生成/优化文案 |
| `prompt_template.py` | 写作提示词 |
| `style_prompts.py` | 干货/幽默/种草风格说明 |
| `xiaohongshu_model.py` | 输出格式（5 标题 + 正文） |
| `database.py` | 本地历史记录 SQLite |
| `export_utils.py` | 导出 Markdown |
| `load_env.py` | 读取 `.env` |
| `apis/` | 小红书 PC 接口（来自 Spider_XHS） |
| `xhs_utils/` | Cookie、签名 JS 调用 |
| `static/` | 签名用 JS 文件 |
| `data/` | SQLite 数据库文件目录 |

## 不必关心的目录

| 目录 | 说明 |
|------|------|
| `.cursor/skills/` | 给 **Cursor 编辑器** 看的 AI 维护说明，程序运行不依赖 |
| `node_modules/` | `npm install` 生成的签名依赖，已在 `.gitignore` |
| `.venv/` | Python 虚拟环境，不要上传 |

根目录曾有的空文件夹 `skills/`、`workflow/`、`research/`、`tools/` 为早期规划残留，已清理。
