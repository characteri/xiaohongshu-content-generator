import os

import streamlit as st

from database import (
    delete_record,
    get_record,
    list_records,
    record_to_xiaohongshu,
    save_record,
    update_record,
)
from export_utils import markdown_filename, to_markdown
from load_env import load_env_file
from style_prompts import STYLE_OPTIONS
from utils import generate_xiaohongshu, refine_xiaohongshu

load_env_file()

st.set_page_config(page_title="爆款小红书AI写作助手", layout="wide")

api_key = os.environ.get("DEEPSEEK_API_KEY", "")

if "xhs_result" not in st.session_state:
    st.session_state.xhs_result = None
if "xhs_round" not in st.session_state:
    st.session_state.xhs_round = 0
if "xhs_history_id" not in st.session_state:
    st.session_state.xhs_history_id = None


def _check_api_key() -> bool:
    if api_key:
        return True
    st.error(
        "未检测到 DeepSeek API Key。请在项目根目录创建 `.env` 文件，"
        "参考 `.env.example` 填写 `DEEPSEEK_API_KEY`。"
    )
    return False


def _load_history_record(record_id: int) -> None:
    record = get_record(record_id)
    if record is None:
        st.sidebar.warning("记录不存在或已删除")
        return
    st.session_state.xhs_result = record_to_xiaohongshu(record)
    st.session_state.xhs_theme = record["theme"]
    st.session_state.xhs_style = record["style"]
    st.session_state.xhs_user_notes = record["user_notes"]
    st.session_state.xhs_round = record["round_num"]
    st.session_state.xhs_history_id = record["id"]


def _persist_result(result, round_num: int) -> None:
    """首次生成 INSERT；同一会话的优化 UPDATE 同一条记录。"""
    theme = st.session_state.get("xhs_theme", "")
    style = st.session_state.get("xhs_style", "干货")
    notes = st.session_state.get("xhs_user_notes", "")

    if st.session_state.xhs_history_id is None:
        record_id = save_record(theme, style, notes, result, round_num)
        st.session_state.xhs_history_id = record_id
    else:
        update_record(st.session_state.xhs_history_id, result, round_num)


# ---------- 侧边栏：历史记录 ----------
with st.sidebar:
    st.subheader("📚 历史记录")
    st.caption("自动保存每次「开始写作」；优化会更新同一条，不刷屏")

    records = list_records()
    if not records:
        st.write("暂无历史，生成一篇后会出现在这里。")
    else:
        for rec in records:
            label = (
                f"**{rec['theme'][:18]}**"
                f"{'…' if len(rec['theme']) > 18 else ''}\n\n"
                f"{rec['style']} · 第{rec['round_num']}轮 · {rec['updated_at']}"
            )
            col_load, col_del = st.columns([3, 1])
            with col_load:
                if st.button(label, key=f"load_{rec['id']}", use_container_width=True):
                    _load_history_record(rec["id"])
                    st.rerun()
            with col_del:
                if st.button("删", key=f"del_{rec['id']}"):
                    delete_record(rec["id"])
                    if st.session_state.xhs_history_id == rec["id"]:
                        st.session_state.xhs_history_id = None
                    st.rerun()

# ---------- 主界面 ----------
st.header("爆款小红书AI写作助手 ✏️")
st.caption("风格选择 · 灵感碎片 · 多轮优化 · 历史记录 · Markdown 导出")

col_input, col_hint = st.columns([2, 1])

with col_input:
    default_style = st.session_state.get("xhs_style", STYLE_OPTIONS[0])
    style_index = STYLE_OPTIONS.index(default_style) if default_style in STYLE_OPTIONS else 0
    style = st.selectbox(
        "写作风格",
        STYLE_OPTIONS,
        index=style_index,
        help="干货偏攻略收藏，幽默偏口语梗，种草偏体验安利",
    )
    theme = st.text_input(
        "写作主题",
        value=st.session_state.get("xhs_theme", ""),
        placeholder="例如：杭州西湖一日游",
    )
    user_notes = st.text_area(
        "你的灵感 / 独门体验（选填）",
        value=st.session_state.get("xhs_user_notes", ""),
        placeholder=(
            "写下你想分享的真实片段，不必有条理，例如：\n"
            "初夏晚上10点，和朋友从曲院风荷骑车绕湖，风很凉，特别治愈……"
        ),
        height=120,
        help="AI 会理解你的意图，自然写进正文，而不是生硬粘贴",
    )

with col_hint:
    st.info(
        "**怎么用更好？**\n\n"
        "1. 主题定方向（去哪、写什么）\n"
        "2. 灵感框写只有你知道的细节\n"
        "3. 生成后可优化、导出、在左侧加载历史"
    )

btn_col1, btn_col2, _ = st.columns([1, 1, 3])
with btn_col1:
    submit = st.button("开始写作", type="primary", use_container_width=True)
with btn_col2:
    if st.button("清空重新开始", use_container_width=True):
        st.session_state.xhs_result = None
        st.session_state.xhs_round = 0
        st.session_state.xhs_history_id = None
        st.session_state.xhs_theme = ""
        st.session_state.xhs_style = STYLE_OPTIONS[0]
        st.session_state.xhs_user_notes = ""
        st.rerun()


if submit:
    if not _check_api_key():
        st.stop()
    if not theme.strip():
        st.info("请输入写作主题")
        st.stop()
    with st.spinner("AI 正在创作中，请稍等..."):
        result = generate_xiaohongshu(
            theme.strip(),
            api_key,
            style=style,
            user_notes=user_notes,
        )
        st.session_state.xhs_result = result
        st.session_state.xhs_theme = theme.strip()
        st.session_state.xhs_style = style
        st.session_state.xhs_user_notes = user_notes
        st.session_state.xhs_round = 1
        st.session_state.xhs_history_id = None
        _persist_result(result, round_num=1)
    st.rerun()


def _render_result(result):
    st.divider()
    if st.session_state.xhs_round > 1:
        st.success(f"已完成第 {st.session_state.xhs_round} 轮优化")

    export_col, _ = st.columns([1, 3])
    with export_col:
        md_text = to_markdown(
            st.session_state.get("xhs_theme", theme),
            st.session_state.get("xhs_style", style),
            result,
            user_notes=st.session_state.get("xhs_user_notes", user_notes),
            round_num=st.session_state.get("xhs_round", 1),
        )
        st.download_button(
            label="⬇️ 下载 Markdown",
            data=md_text,
            file_name=markdown_filename(st.session_state.get("xhs_theme", "draft")),
            mime="text/markdown",
            use_container_width=True,
        )

    left_column, right_column = st.columns(2)
    with left_column:
        st.markdown("##### 🔥 爆款标题推荐")
        for i, title in enumerate(result.titles, 1):
            st.write(f"{i}. {title}")
    with right_column:
        st.markdown("##### 📝 正文内容")
        st.write(result.content)

    with st.expander("预览 Markdown 导出内容"):
        st.markdown(md_text)


if st.session_state.xhs_result:
    _render_result(st.session_state.xhs_result)

    st.markdown("---")
    st.subheader("多轮优化")
    st.caption("告诉 AI 哪里不满意，它在上一版基础上改；优化结果会同步更新到历史记录")

    feedback = st.text_area(
        "修改意见",
        placeholder="例如：标题太正式；正文太长；多写骑车那段；多加 #西湖 #夜游 标签",
        height=100,
        key="refine_feedback",
    )
    if st.button("根据意见优化", use_container_width=False):
        if not _check_api_key():
            st.stop()
        if not feedback.strip():
            st.warning("请先填写修改意见")
        else:
            with st.spinner("AI 正在优化中..."):
                st.session_state.xhs_result = refine_xiaohongshu(
                    st.session_state.xhs_result,
                    feedback,
                    st.session_state.get("xhs_theme", theme),
                    api_key,
                    style=st.session_state.get("xhs_style", style),
                    user_notes=st.session_state.get("xhs_user_notes", user_notes),
                )
                st.session_state.xhs_round += 1
                _persist_result(
                    st.session_state.xhs_result,
                    round_num=st.session_state.xhs_round,
                )
            st.rerun()
