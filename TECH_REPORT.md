# 爆款小红书 AI 写作助手 — 技术实现报告

> 本文档描述当前代码库的架构、数据流与核心模块实现，便于面试准备与二次开发。  
> 版本对应：2025 年精简版（检索参考 + DeepSeek 写作，无维基/热梗/批量爬虫）。

---

## 1. 项目概述

### 1.1 要解决什么问题

新手写小红书笔记时，常见痛点是：

- 不知道同类「爆款」长什么样（标题结构、话题标签、内容角度）
- 从零写稿耗时长

本项目的思路是：**先按主题检索平台上高互动笔记作为参考，再让大模型生成自己的稿**，而不是让模型凭空编造。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 爆款参考检索 | 按写作主题搜索笔记，取 Top3，展示标题/互动/标签/概要/链接 |
| AI 文案生成 | LangChain + DeepSeek，输出 5 标题 + 1 正文 |
| 多轮优化 | 根据用户修改意见在上一版基础上改写 |
| 历史记录 | SQLite 本地保存创作会话 |
| Markdown 导出 | 下载生成结果 |

### 1.3 技术栈

| 层级 | 技术 |
|------|------|
| 前端/交互 | Streamlit |
| 大模型 | DeepSeek API（OpenAI 兼容接口） |
| LLM 框架 | LangChain（PromptTemplate + LCEL Chain + PydanticOutputParser） |
| 数据校验 | Pydantic（`Xiaohongshu` 模型） |
| 小红书数据 | Spider_XHS 衍生的 `apis/xhs_pc_apis.py` + Node 签名 JS |
| 持久化 | SQLite（`data/xiaohongshu_history.db`） |
| 配置 | `.env` + `load_env.py` |

---

## 2. 系统架构

### 2.1 总体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit  UI (main.py)                      │
│  主题 / 风格 / 灵感 │ 预览参考 │ 开始写作 │ 优化 │ 历史 │ 导出   │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
             ▼                               ▼
┌────────────────────────┐      ┌───────────────────────────────┐
│  xhs_reference.py      │      │  utils.py                     │
│  fetch_note_references │      │  generate_xiaohongshu         │
│  references_to_prompt  │      │  refine_xiaohongshu            │
└────────────┬───────────┘      └───────────────┬───────────────┘
             │                                  │
             ▼                                  ▼
┌────────────────────────┐      ┌───────────────────────────────┐
│  apis/xhs_pc_apis.py   │      │  DeepSeek API                 │
│  + xhs_utils/xhs_util  │      │  + prompt_template.py         │
│  + static/*.js 签名    │      │  + xiaohongshu_model.py       │
└────────────────────────┘      └───────────────────────────────┘
             │                                  │
             ▼                                  ▼
      小红书 PC 搜索 API                   结构化文案 JSON
                                                  │
                                                  ▼
                                        ┌─────────────────┐
                                        │  database.py    │
                                        │  SQLite 历史    │
                                        └─────────────────┘
```

### 2.2 两条主链路

**链路 A：预览/获取参考（可不写作）**

```
用户填主题 → 点「预览参考」
  → fetch_note_references(theme)
  → reference_ui 三列卡片展示
  → 结果存入 st.session_state.xhs_references
```

**链路 B：写作（可带参考）**

```
用户点「开始写作」
  → （可选）fetch_note_references
  → references_to_prompt(refs) 拼入 Prompt
  → generate_xiaohongshu(...)
  → Pydantic 解析为 Xiaohongshu
  → save_record 写入 SQLite
  → 页面展示 + 可 refine_xiaohongshu 多轮优化
```

---

## 3. 目录与模块职责

```
项目根目录/
├── main.py                 # Streamlit 入口，会话状态，按钮事件
├── xhs_reference.py        # ★ 爆款参考：搜索、解析、概要、Prompt 块
├── reference_ui.py         # 参考笔记三列 HTML 卡片 UI
├── utils.py                # LangChain 写作/优化链
├── prompt_template.py        # System/User Prompt 模板
├── style_prompts.py          # 干货/幽默/种草 风格说明
├── xiaohongshu_model.py      # 输出结构 Pydantic 模型
├── database.py               # SQLite CRUD
├── export_utils.py           # Markdown 导出
├── load_env.py               # 读取 .env
├── apis/
│   └── xhs_pc_apis.py        # 小红书 PC 端 HTTP API（搜索、笔记详情等）
├── xhs_utils/
│   ├── xhs_util.py           # 请求签名（调用 static/*.js）
│   ├── cookie_util.py        # Cookie 字符串解析
│   ├── data_util.py          # 时间戳等工具（Spider_XHS 遗留）
│   └── http_util.py          # 请求超时等
├── static/
│   ├── xhs_main_260411.js    # 签名核心
│   └── xhs_rap.js            # x-rap-param 等
├── data/                     # SQLite 文件目录（.gitignore）
├── .env                      # 密钥与 Cookie（勿提交 Git）
└── requirements.txt
```

**不接入主流程的文件（可忽略）：**

- `.cursor/skills/`：Cursor 编辑器用说明，程序不读
- `node_modules/`：`npm install` 生成，给 execjs 调 JS 签名用

---

## 4. 核心实现：爆款参考如何工作

> 这是面试最常问的部分，下面按「输入 → 请求 → 解析 → 排序 → 概要 → 展示 → 注入 Prompt」展开。

### 4.1 入口函数

文件：`xhs_reference.py`  
函数：`fetch_note_references(keyword, cookies=None, limit=3, api_key=None)`

**输入：**

- `keyword`：用户填的「写作主题」，原样作为搜索词
- `cookies`：默认从环境变量 `XHS_COOKIES` 读取
- `limit`：默认 3 条
- `api_key`：DeepSeek Key，用于生成改写概要

**输出：**

- `(success: bool, message: str, refs: List[NoteReference])`

### 4.2 搜索参数（常量）

```python
_SEARCH_POOL_SIZE = 15      # 先搜 15 条，再筛 Top3
_MAX_REFERENCES = 3
_SORT_BY_COLLECT = 4        # 4 = 按「最多收藏」排序搜索
```

设计原因：

1. 搜索 API 的排序与「综合互动最高」不完全一致  
2. 先按收藏搜一批，再用 `点赞 + 收藏` 本地重排，更贴近「爆款」

### 4.3 调用小红书搜索 API

```python
api = XHS_Apis()
success, msg, notes = api.search_some_note(
    keyword,
    _SEARCH_POOL_SIZE,   # require_num = 15
    cookies,
    _SORT_BY_COLLECT,  # sort_type_choice = 4
    0,                 # note_type = 不限
)
```

底层路径：

1. `apis/xhs_pc_apis.py` → `search_some_note()` 分页拉取直到够 15 条  
2. 每页调用 `search_note()` → POST `https://www.xiaohongshu.com/api/sns/web/v1/search/notes`  
3. 请求前通过 `xhs_utils/xhs_util.py` 的 `generate_request_params()` 计算签名头（`x-s`、`x-t`、`x-s-common` 等）  
4. 签名逻辑在 `static/xhs_main_260411.js` 中，Python 用 **PyExecJS** 调用

**依赖：**

- 有效登录 Cookie（`.env` 中 `XHS_COOKIES`）
- 本机已 `npm install`（Node 环境供 execjs 使用）

### 4.4 单条搜索结果的数据结构（API 返回）

每条 item 大致结构（简化）：

```json
{
  "id": "笔记ID",
  "model_type": "note",
  "xsec_token": "访问令牌",
  "note_card": {
    "display_title": "标题",
    "desc": "正文摘录（搜索列表里通常较短）",
    "interact_info": {
      "liked_count": "69807",
      "collected_count": "13817",
      "comment_count": "2810"
    },
    "corner_tag_info": [
      { "type": "publish_time", "text": "5天前" }
    ],
    "tag_list": [ ... ]   // 有时为空
  }
}
```

### 4.5 解析为 `NoteReference`

函数：`_parse_search_item(item)`

| 字段 | 来源 |
|------|------|
| `title` | `note_card.display_title` 或 `title` |
| `liked_count` / `collected_count` / `comment_count` | `interact_info` |
| `published_at` | `corner_tag_info` 中 `publish_time`，或 `time` 时间戳转字符串 |
| `tags` | `tag_list` + 从 `desc` 正则提取 `#话题` |
| `url` | `https://www.xiaohongshu.com/explore/{id}?xsec_token=...` |
| `engagement_score` | `_parse_count(赞) + _parse_count(藏)`，支持「1.2万」格式 |

过滤：只保留 `model_type == "note"` 的条目。

### 4.6 排序与截断

```python
parsed_with_desc.sort(key=lambda pair: pair[0].engagement_score, reverse=True)
pairs = parsed_with_desc[:limit]  # Top 3
```

### 4.7 概要（summary）如何生成

搜索列表里的 `desc` 往往只有标题或短句，**不是完整正文**。项目不展示原文，而是生成「改写概要」：

**方式 A — 有 DeepSeek API Key（默认）：**

函数 `_summarize_with_llm(pairs, api_key)`

- 把每条参考的标题、desc 前 400 字、已有标签发给 DeepSeek  
- 要求：1～2 句中性概括，**禁止照搬**  
- 用正则 `[1]`、`[2]`、`[3]` 解析回写到 `ref.summary`

**方式 B — 无 Key 或 LLM 失败：**

函数 `_heuristic_summary(title, desc)`

- 去掉 `#标签`，截断到约 100 字  
- 前缀 `【内容概要，非原文】`（UI 展示时会去掉该前缀）

### 4.8 注入写作 Prompt

函数：`references_to_prompt(refs: List[NoteReference]) -> str`

生成类似如下文本块，作为 Prompt 变量 `{research_context}`：

```
【小红书爆款参考 · 仅供结构与选题，禁止照搬原文】

1. 《标题》
   互动：赞xxx 藏xxx 评xxx · 发布时间
   标签：#tag1 #tag2
   概要：...
   链接：https://...

2. ...
```

在 `utils.generate_xiaohongshu()` 中传入 chain。

### 4.9 UI 展示

文件：`reference_ui.py`

- 使用 Streamlit `st.columns(3)` 三列并排  
- 每列用自定义 HTML + CSS 渲染卡片（兼容 Streamlit 1.28，不用 `border=True`）  
- 展示：标题、时间、赞藏评、#标签 pill、概要、原笔记链接

### 4.10 参考链路时序图

```
用户          main.py           xhs_reference        xhs_pc_apis         DeepSeek
  │              │                    │                   │                  │
  │─填主题───────►│                    │                   │                  │
  │─预览参考─────►│                    │                   │                  │
  │              │─fetch_note_refs───►│                   │                  │
  │              │                    │─search_some_note─►│                  │
  │              │                    │◄──JSON notes──────│                  │
  │              │                    │─parse/sort/top3──│                  │
  │              │                    │─summarize_with_llm──────────────────►│
  │              │                    │◄──概要文本──────────────────────────│
  │              │◄──List[NoteReference]                 │                  │
  │              │─render_reference_summary─► 三列卡片   │                  │
  │◄─看到参考────│                    │                   │                  │
  │              │                    │                   │                  │
  │─开始写作─────►│                    │                   │                  │
  │              │─references_to_prompt                   │                  │
  │              │─generate_xiaohongshu──────────────────────────────────────►│
  │◄─5标题+正文──│                    │                   │                  │
```

---

## 5. AI 文案生成实现

### 5.1 输出结构

文件：`xiaohongshu_model.py`

```python
class Xiaohongshu(BaseModel):
    titles: List[str]  # 恰好 5 个
    content: str       # 正文
```

LangChain 的 `PydanticOutputParser` 会把模型输出强制解析成该结构；格式不对会报错。

### 5.2 Prompt 组成

文件：`prompt_template.py` + `style_prompts.py`

**System Prompt 包含：**

- 角色：小红书爆款写作专家  
- `{style_instructions}`：干货 / 幽默 / 种草 之一  
- 标题技巧（二极管标题法、爆款词等）  
- 正文技巧（结构、emoji、文末 tag）  
- 规则：参考只学结构，禁止照搬；灵感要自然融入  
- `{parser_instructions}`：Pydantic 格式说明  

**User Prompt 包含：**

- `{theme}`：写作主题  
- `{research_context}`：参考笔记块（`references_to_prompt` 输出）  
- `{user_notes}`：用户灵感  

### 5.3 LangChain 调用链

文件：`utils.py`

```python
chain = prompt | ChatOpenAI(model="deepseek-chat", base_url=DeepSeek) | output_parser
result = chain.invoke({...})
```

- `generate_xiaohongshu()`：首次生成  
- `refine_xiaohongshu()`：带上 `{previous_draft}` + `{feedback}` 做优化  

### 5.4 多轮优化

- 用户输入修改意见  
- 调用 `refine_xiaohongshu(previous, feedback, ...)`  
- `st.session_state.xhs_round` 递增  
- `database.update_record()` 更新同一条历史（不新增一行）

---

## 6. 前端与状态管理（Streamlit）

### 6.1 Session State 键

| 键 | 含义 |
|----|------|
| `xhs_result` | 当前生成的 `Xiaohongshu` 对象 |
| `xhs_references` | 当前参考列表 `List[NoteReference]` |
| `xhs_theme` / `xhs_style` / `xhs_user_notes` | 表单缓存 |
| `xhs_round` | 优化轮次 |
| `xhs_history_id` | 当前会话对应 SQLite 行 id |
| `use_xhs_ref` | 是否写作时带参考 |

### 6.2 按钮逻辑摘要

| 按钮 | 行为 |
|------|------|
| 预览参考 | 仅 `fetch_note_references`，不写作 |
| 开始写作 | 可选先拉参考 → `generate_xiaohongshu` → `save_record` |
| 优化 | `refine_xiaohongshu` → `update_record` |
| 清空 | 重置 session state |

---

## 7. 数据持久化

### 7.1 表结构 `posts`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| theme | TEXT | 主题 |
| style | TEXT | 风格 |
| user_notes | TEXT | 灵感 |
| titles_json | TEXT | 5 标题 JSON 数组 |
| content | TEXT | 正文 |
| round_num | INTEGER | 优化轮次 |
| created_at / updated_at | TEXT | 时间 |

文件路径：`data/xiaohongshu_history.db`（已在 `.gitignore`）

### 7.2 设计选择

- **首次写作** `INSERT`  
- **同会话优化** `UPDATE` 同 id，避免历史列表被优化刷屏  

---

## 8. 配置与环境

### 8.1 `.env` 变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 写作必填 | DeepSeek API |
| `XHS_COOKIES` | 参考必填 | 浏览器登录小红书后复制 |

### 8.2 启动命令

```bash
cp .env.example .env
pip install -r requirements.txt
npm install
streamlit run main.py
```

---

## 9. 异常与降级

| 场景 | 行为 |
|------|------|
| 未配置 `XHS_COOKIES` | 预览/参考失败，提示配置；写作可不带参考继续 |
| Cookie 过期 | 搜索 API 失败，返回错误信息 |
| 关键词无结果 | 提示换词或检查 Cookie |
| DeepSeek 概要失败 | 降级为 `_heuristic_summary` |
| DeepSeek 生成解析失败 | Chain 抛错，页面 spinner 结束 |

---

## 10. 已知限制

1. **Cookie 会过期**，需手动更新，无自动登录  
2. **搜索列表无完整正文**，参考深度有限  
3. **非官方 API**，接口变更可能导致失效（依赖 Spider_XHS 社区维护）  
4. **个人工具**，无多用户、无权限、无线上 AB  
5. **未做相似度检测**，依赖 Prompt 约束防抄袭  

---

## 11. 面试常见问题 ↔ 文档章节

| 问题 | 看哪一节 |
|------|----------|
| 参考文章怎么实现的？ | **第 4 节** |
| 为什么 Top3？为什么搜 15 条？ | 4.2、4.6 |
| 概要是不是原文？ | 4.7 |
| 和 RAG 什么关系？ | 4.8（检索增强生成） |
| LangChain 干什么用？ | 第 5 节 |
| Cookie/签名怎么回事？ | 4.3 |
| 怎么存历史？ | 第 7 节 |
| 失败了怎么办？ | 第 9 节 |

---

## 12. 一句话总结

本项目 = **小红书搜索检索（Spider_XHS API + Cookie/签名）** + **结构化参考卡片** + **LangChain/DeepSeek 检索增强写作** + **Streamlit 交互与 SQLite 历史**。

核心文件只需记住三个：`xhs_reference.py`（参考）、`utils.py`（写作）、`main.py`（界面）。

---

*文档生成自当前代码库，如有改动请以源码为准。*
