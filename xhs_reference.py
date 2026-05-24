"""
按关键词从小红书搜索高互动笔记，返回最多 3 条「参考卡片」（概要、标签、时间、链接），不展示原文。
依赖 Spider_XHS 的 apis/xhs_pc_apis（需配置 XHS_COOKIES、Node 签名环境）。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.data_util import timestamp_to_str

# 按收藏排序搜索，多取一些再按点赞+收藏重排
_SEARCH_POOL_SIZE = 15
_MAX_REFERENCES = 3
_SORT_BY_COLLECT = 4  # 0 综合, 4 最多收藏


@dataclass
class NoteReference:
    """单条爆款参考（供 UI 展示，不含原文正文）。"""

    title: str
    summary: str
    tags: List[str] = field(default_factory=list)
    published_at: str = "未知"
    url: str = ""
    liked_count: str = "0"
    collected_count: str = "0"
    comment_count: str = "0"
    engagement_score: int = 0


def get_xhs_cookies() -> str:
    return (os.environ.get("XHS_COOKIES") or os.environ.get("COOKIES") or "").strip()


def _parse_count(value) -> int:
    """解析互动数字，支持 1.2万、1.2w 等格式。"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower().replace(",", "")
    if not text:
        return 0
    try:
        if text.endswith("万") or text.endswith("w"):
            return int(float(text[:-1]) * 10000)
        return int(float(text))
    except ValueError:
        return 0


def _extract_tags(desc: str, tag_list) -> List[str]:
    tags: List[str] = []
    if tag_list:
        for tag in tag_list:
            if isinstance(tag, dict) and tag.get("name"):
                tags.append(tag["name"].lstrip("#"))
            elif isinstance(tag, str):
                tags.append(tag.lstrip("#"))
    if desc:
        for match in re.findall(r"#([^\s#]{1,30})", desc):
            if match not in tags:
                tags.append(match)
    return tags[:12]


def _publish_time(note_card: dict) -> str:
    for corner in note_card.get("corner_tag_info") or []:
        if corner.get("type") == "publish_time" and corner.get("text"):
            return str(corner["text"])
    ts = note_card.get("time")
    if ts:
        try:
            return timestamp_to_str(int(ts))
        except (TypeError, ValueError):
            pass
    return "未知"


def _note_url(note_id: str, xsec_token: str) -> str:
    token_part = f"?xsec_token={xsec_token}" if xsec_token else ""
    return f"https://www.xiaohongshu.com/explore/{note_id}{token_part}"


def _parse_search_item(item: dict) -> Optional[NoteReference]:
    if item.get("model_type") != "note":
        return None
    note_id = item.get("id")
    if not note_id:
        return None

    card = item.get("note_card") or {}
    title = (card.get("display_title") or card.get("title") or "无标题").strip()
    desc = (card.get("desc") or "").strip()
    interact = card.get("interact_info") or {}
    liked = str(interact.get("liked_count", "0"))
    collected = str(interact.get("collected_count", "0"))
    commented = str(interact.get("comment_count", "0"))
    score = _parse_count(liked) + _parse_count(collected)

    return NoteReference(
        title=title,
        summary="",  # 稍后填充
        tags=_extract_tags(desc, card.get("tag_list")),
        published_at=_publish_time(card),
        url=_note_url(note_id, item.get("xsec_token") or ""),
        liked_count=liked,
        collected_count=collected,
        comment_count=commented,
        engagement_score=score,
    )


def references_to_prompt(refs: List[NoteReference]) -> str:
    """将参考笔记格式化为写作 Prompt 块。"""
    if not refs:
        return "（本次未附带小红书爆款参考。）"
    lines = [
        "【小红书爆款参考 · 仅供结构与选题，禁止照搬原文】",
        "",
    ]
    for i, ref in enumerate(refs, 1):
        tag_str = " ".join(f"#{t}" for t in ref.tags[:8]) if ref.tags else "无"
        lines.extend([
            f"{i}. 《{ref.title}》",
            f"   互动：赞{ref.liked_count} 藏{ref.collected_count} 评{ref.comment_count} · {ref.published_at}",
            f"   标签：{tag_str}",
            f"   概要：{ref.summary}",
            f"   链接：{ref.url}",
            "",
        ])
    return "\n".join(lines).strip()


def _heuristic_summary(title: str, desc: str) -> str:
    """无 LLM 时的兜底：压缩表述，并标明非原文。"""
    raw = f"{title}。{desc}" if desc and desc != title else title
    raw = re.sub(r"#\S+", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if len(raw) > 100:
        raw = raw[:100].rstrip() + "…"
    return f"【内容概要，非原文】{raw}"


def _summarize_with_llm(
    items: List[Tuple[NoteReference, str]],
    api_key: str,
) -> None:
    """用 DeepSeek 为每条参考生成改写概要（就地写入 item.summary）。"""
    from langchain_openai import ChatOpenAI

    blocks = []
    for idx, (ref, desc) in enumerate(items, 1):
        tag_hint = "、".join(ref.tags[:6]) if ref.tags else "无"
        blocks.append(
            f"[{idx}] 标题：{ref.title}\n"
            f"    摘录（仅供理解，请勿照抄）：{desc[:400] or '（无正文摘录）'}\n"
            f"    已有标签：{tag_hint}"
        )
    prompt = (
        "你是小红书运营分析助手。根据下列笔记的标题和简短摘录，"
        "为每条写 1～2 句【中性内容概要】，要求：\n"
        "1. 用自己的话概括，禁止照搬原文句子\n"
        "2. 不要输出完整正文或长段落\n"
        "3. 按 [1][2][3] 编号逐条输出，每条单独一行，格式：[n] 概要内容\n\n"
        + "\n\n".join(blocks)
    )
    model = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
    )
    text = model.invoke(prompt).content.strip()
    for idx, (ref, desc) in enumerate(items, 1):
        pattern = rf"\[{idx}\]\s*(.+?)(?=\n\[|\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            ref.summary = match.group(1).strip()
        else:
            ref.summary = _heuristic_summary(ref.title, desc)


def fetch_note_references(
    keyword: str,
    cookies: Optional[str] = None,
    *,
    limit: int = _MAX_REFERENCES,
    api_key: Optional[str] = None,
) -> Tuple[bool, str, List[NoteReference]]:
    """
    搜索关键词下高收藏笔记，返回互动最高的 limit 条参考。

    Returns:
        (success, message, references)
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return False, "请先填写写作主题作为搜索关键词", []

    cookies = (cookies or get_xhs_cookies()).strip()
    if not cookies:
        return (
            False,
            "未配置小红书 Cookie。请在 .env 中设置 XHS_COOKIES（登录小红书 PC 网页后从浏览器复制）。",
            [],
        )

    api = XHS_Apis()
    success, msg, notes = api.search_some_note(
        keyword,
        _SEARCH_POOL_SIZE,
        cookies,
        _SORT_BY_COLLECT,
        0,
    )
    if not success:
        return False, f"搜索失败：{msg}", []

    parsed_with_desc: List[Tuple[NoteReference, str]] = []
    for item in notes:
        ref = _parse_search_item(item)
        if ref is None:
            continue
        card = item.get("note_card") or {}
        parsed_with_desc.append((ref, (card.get("desc") or "").strip()))

    if not parsed_with_desc:
        return False, "未找到相关笔记，请换关键词或检查 Cookie 是否过期", []

    parsed_with_desc.sort(key=lambda pair: pair[0].engagement_score, reverse=True)
    pairs = parsed_with_desc[:limit]
    top = [ref for ref, _ in pairs]

    if api_key:
        try:
            _summarize_with_llm(pairs, api_key)
        except Exception as exc:
            for ref, desc in pairs:
                ref.summary = _heuristic_summary(ref.title, desc)
            return (
                True,
                f"已获取 {len(top)} 条参考（概要生成失败，已使用简化摘要：{exc}）",
                top,
            )
    else:
        for ref, desc in pairs:
            ref.summary = _heuristic_summary(ref.title, desc)

    return True, f"已找到 {len(top)} 条高互动参考（按收藏搜索，按点赞+收藏排序）", top
