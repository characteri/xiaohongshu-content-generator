"""把生成结果导出为 Markdown 文本，供下载或复制到小红书编辑器。"""

from xiaohongshu_model import Xiaohongshu


def to_markdown(
    theme: str,
    style: str,
    result: Xiaohongshu,
    user_notes: str = "",
    round_num: int = 1,
) -> str:
    lines = [
        f"# 小红书文案：{theme}",
        "",
        f"- **风格**：{style}",
        f"- **优化轮次**：第 {round_num} 轮",
    ]
    if user_notes.strip():
        lines.extend(["", "## 灵感素材", "", user_notes.strip()])

    lines.extend(["", "## 标题候选", ""])
    for i, title in enumerate(result.titles, 1):
        lines.append(f"{i}. {title}")

    lines.extend(["", "## 正文", "", result.content, ""])
    return "\n".join(lines)


def markdown_filename(theme: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in theme[:30])
    return f"xiaohongshu_{safe or 'draft'}.md"
