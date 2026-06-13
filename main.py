import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import streamlit as st

from load_env import ensure_npm_deps, load_env_file, load_streamlit_secrets

load_streamlit_secrets()
load_env_file()
ensure_npm_deps()

from database import (
    delete_record,
    get_record,
    list_records,
    record_to_xiaohongshu,
    save_record,
    update_record,
)
from export_utils import markdown_filename, to_markdown
from reference_ui import render_reference_summary
from style_prompts import STYLE_OPTIONS
from utils import generate_xiaohongshu, refine_xiaohongshu
from xhs_reference import fetch_note_references, get_xhs_cookies

st.set_page_config(
    page_title="爆款小红书AI写作助手",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1100px; }
    div[data-testid="stSidebar"] { background-color: #f8f8f8; }
    </style>
    """,
    unsafe_allow_html=True,
)

api_key = os.environ.get("DEEPSEEK_API_KEY", "")

if "xhs_result" not in st.session_state:
    st.session_state.xhs_result = None
if "xhs_round" not in st.session_state:
    st.session_state.xhs_round = 0
if "xhs_history_id" not in st.session_state:
    st.session_state.xhs_history_id = None
if "xhs_references" not in st.session_state:
    st.session_state.xhs_references = None
if "xhs_ref_message" not in st.session_state:
    st.session_state.xhs_ref_message = ""
if "use_xhs_ref" not in st.session_state:
    st.session_state.use_xhs_ref = True


def _check_api_key() -> bool:
    if api_key:
        return True
    st.error("请在 `.env` 中配置 `DEEPSEEK_API_KEY`")
    return False


def _load_history_record(record_id: int) -> None:
    record = get_record(record_id)
    if record is None:
        return
    st.session_state.xhs_result = record_to_xiaohongshu(record)
    st.session_state.xhs_theme = record["theme"]
    st.session_state.xhs_style = record["style"]
    st.session_state.xhs_user_notes = record["user_notes"]
    st.session_state.xhs_round = record["round_num"]
    st.session_state.xhs_history_id = record["id"]


def _persist_result(result, round_num: int) -> None:
    if st.session_state.xhs_history_id is None:
        st.session_state.xhs_history_id = save_record(
            st.session_state.get("xhs_theme", ""),
            st.session_state.get("xhs_style", "干货"),
            st.session_state.get("xhs_user_notes", ""),
            result,
            round_num,
        )
    else:
        update_record(st.session_state.xhs_history_id, result, round_num)


def _clear_session() -> None:
    st.session_state.xhs_result = None
    st.session_state.xhs_round = 0
    st.session_state.xhs_history_id = None
    st.session_state.xhs_theme = ""
    st.session_state.xhs_style = STYLE_OPTIONS[0]
    st.session_state.xhs_user_notes = ""
    st.session_state.xhs_references = None
    st.session_state.xhs_ref_message = ""


def _fetch_references(theme: str) -> None:
    if not theme.strip():
        st.info("请先填写写作主题")
        return
    if not get_xhs_cookies():
        st.error("请配置 `XHS_COOKIES`")
        return
    with st.spinner("搜索中…"):
        ok, message, refs = fetch_note_references(
            theme.strip(),
            api_key=api_key or None,
        )
    st.session_state.xhs_ref_message = message if ok else ""
    st.session_state.xhs_references = refs if ok else None
    if not ok:
        st.error(message)


with st.sidebar:
    st.markdown("### 历史")
    for rec in list_records():
        if st.button(
            f"{rec['theme'][:16]} · {rec['style']}",
            key=f"load_{rec['id']}",
            use_container_width=True,
        ):
            _load_history_record(rec["id"])
            st.rerun()

st.title("爆款小红书 AI 写作")

row1_a, row1_b = st.columns([3, 2])

with row1_a:
    style = st.selectbox(
        "风格",
        STYLE_OPTIONS,
        index=STYLE_OPTIONS.index(st.session_state.get("xhs_style", STYLE_OPTIONS[0]))
        if st.session_state.get("xhs_style") in STYLE_OPTIONS
        else 0,
    )
    theme = st.text_input(
        "主题",
        value=st.session_state.get("xhs_theme", ""),
        placeholder="优绩主义",
    )
    user_notes = st.text_area(
        "灵感（选填）",
        value=st.session_state.get("xhs_user_notes", ""),
        height=88,
    )

with row1_b:
    st.markdown("**参考热门笔记** · 最多 3 条")
    use_xhs_ref = st.checkbox("写作时参考高赞笔记", value=st.session_state.use_xhs_ref)
    st.session_state.use_xhs_ref = use_xhs_ref
    if st.button("预览参考", use_container_width=True):
        _fetch_references(theme)
        st.rerun()

if st.session_state.xhs_references:
    render_reference_summary(st.session_state.xhs_references)

st.divider()

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    submit = st.button("开始写作", type="primary", use_container_width=True)
with c2:
    if st.button("清空", use_container_width=True):
        _clear_session()
        st.rerun()

if submit:
    if not _check_api_key():
        st.stop()
    if not theme.strip():
        st.info("请填写主题")
        st.stop()

    refs = None
    if use_xhs_ref and get_xhs_cookies():
        if not st.session_state.xhs_references:
            with st.spinner("获取参考笔记…"):
                ok, _, refs = fetch_note_references(
                    theme.strip(), api_key=api_key or None
                )
                if ok:
                    st.session_state.xhs_references = refs
        refs = st.session_state.xhs_references

    with st.spinner("生成中…"):
        result = generate_xiaohongshu(
            theme.strip(),
            api_key,
            style=style,
            user_notes=user_notes,
            references=refs,
        )
        st.session_state.xhs_result = result
        st.session_state.xhs_theme = theme.strip()
        st.session_state.xhs_style = style
        st.session_state.xhs_user_notes = user_notes
        st.session_state.xhs_round = 1
        st.session_state.xhs_history_id = None
        _persist_result(result, 1)
    st.rerun()


if st.session_state.xhs_result:
    r = st.session_state.xhs_result
    st.markdown("### 生成结果")
    st.download_button(
        "下载 Markdown",
        data=to_markdown(
            st.session_state.get("xhs_theme", ""),
            st.session_state.get("xhs_style", ""),
            r,
            st.session_state.get("xhs_user_notes", ""),
            st.session_state.get("xhs_round", 1),
        ),
        file_name=markdown_filename(st.session_state.get("xhs_theme", "draft")),
        mime="text/markdown",
    )
    left, right = st.columns(2)
    with left:
        st.markdown("**标题**")
        for i, t in enumerate(r.titles, 1):
            st.write(f"{i}. {t}")
    with right:
        st.markdown("**正文**")
        st.write(r.content)

    st.markdown("---")
    feedback = st.text_input("修改意见")
    if st.button("优化"):
        if feedback.strip() and _check_api_key():
            with st.spinner("优化中…"):
                st.session_state.xhs_result = refine_xiaohongshu(
                    r,
                    feedback,
                    st.session_state.get("xhs_theme", ""),
                    api_key,
                    style=st.session_state.get("xhs_style", ""),
                    user_notes=st.session_state.get("xhs_user_notes", ""),
                    references=st.session_state.xhs_references,
                )
                st.session_state.xhs_round += 1
                _persist_result(st.session_state.xhs_result, st.session_state.xhs_round)
            st.rerun()
