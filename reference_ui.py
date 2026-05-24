"""小红书爆款参考：三列卡片展示。"""

from __future__ import annotations

import html
from typing import List

import streamlit as st

from xhs_reference import NoteReference

_CARD_CSS = """
<style>
.ref-row { margin-top: 0.25rem; }
.ref-card {
    background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
    border: 1px solid #ececec;
    border-radius: 14px;
    padding: 1rem 1rem 0.85rem;
    min-height: 240px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.ref-card h4 {
    margin: 0 0 0.55rem 0;
    font-size: 0.92rem;
    font-weight: 600;
    line-height: 1.4;
    color: #1a1a1a;
}
.ref-meta {
    color: #888;
    font-size: 0.78rem;
    margin-bottom: 0.45rem;
}
.ref-stats {
    color: #555;
    font-size: 0.78rem;
    margin-bottom: 0.5rem;
}
.ref-tags { margin-bottom: 0.55rem; min-height: 1.4rem; }
.ref-tag {
    display: inline-block;
    background: #fff1f3;
    color: #ff2442;
    border: 1px solid #ffd6de;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 0.72rem;
    margin: 0 5px 5px 0;
}
.ref-summary {
    font-size: 0.82rem;
    color: #444;
    line-height: 1.55;
    margin: 0 0 0.6rem 0;
}
.ref-link a {
    font-size: 0.78rem;
    color: #ff2442;
    text-decoration: none;
}
.ref-link a:hover { text-decoration: underline; }
</style>
"""


def _clean_summary(text: str) -> str:
    return (text or "").replace("【内容概要，非原文】", "").strip()


def _card_html(ref: NoteReference) -> str:
    title = html.escape(ref.title)
    time_str = html.escape(ref.published_at or "未知")
    stats = (
        f"赞 {html.escape(ref.liked_count)} · "
        f"藏 {html.escape(ref.collected_count)} · "
        f"评 {html.escape(ref.comment_count)}"
    )
    if ref.tags:
        tags = "".join(
            f'<span class="ref-tag">#{html.escape(t)}</span>' for t in ref.tags[:10]
        )
    else:
        tags = '<span class="ref-meta">—</span>'
    summary = html.escape(_clean_summary(ref.summary))
    link = ""
    if ref.url:
        safe_url = html.escape(ref.url, quote=True)
        link = f'<div class="ref-link"><a href="{safe_url}" target="_blank">原笔记 →</a></div>'

    return f"""
    <div class="ref-card">
        <h4>{title}</h4>
        <div class="ref-meta">🕐 {time_str}</div>
        <div class="ref-stats">{stats}</div>
        <div class="ref-tags">{tags}</div>
        <p class="ref-summary">{summary}</p>
        {link}
    </div>
    """


def render_reference_summary(
    refs: List[NoteReference],
    title: str = "当前参考摘要",
) -> None:
    if not refs:
        return
    st.markdown(f"#### {title}")
    st.markdown(_CARD_CSS, unsafe_allow_html=True)

    cols = st.columns(3)
    for i in range(3):
        with cols[i]:
            if i < len(refs):
                st.markdown(
                    _card_html(refs[i]),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="ref-card"></div>', unsafe_allow_html=True)
