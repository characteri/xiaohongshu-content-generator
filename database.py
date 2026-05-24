"""
SQLite 历史记录模块

SQLite 是什么？
- 一个「文件型」数据库：整个库就是一个 .db 文件，无需安装 MySQL 等服务
- 适合本地小工具：历史不多、单用户使用、零配置

本项目的 data/xiaohongshu_history.db 里有一张表 posts，每行 = 一次创作会话。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from xiaohongshu_model import Xiaohongshu

# 数据库文件路径（放在 data/ 目录，和代码分开）
DB_PATH = Path(__file__).resolve().parent / "data" / "xiaohongshu_history.db"


def _connect() -> sqlite3.Connection:
    """建立连接。Row 工厂让查询结果可以像字典一样用 row["theme"] 访问。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    建表（若不存在则创建）。

    字段说明：
    - titles_json: 5 个标题存成 JSON 字符串（SQLite 无「字符串数组」类型）
    - round_num: 优化到第几轮
    - created_at / updated_at: 方便按时间排序、看最近修改
    """
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme TEXT NOT NULL,
                style TEXT NOT NULL,
                user_notes TEXT,
                titles_json TEXT NOT NULL,
                content TEXT NOT NULL,
                round_num INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_record(
    theme: str,
    style: str,
    user_notes: str,
    result: Xiaohongshu,
    round_num: int = 1,
) -> int:
    """
    插入一条新记录（用户点击「开始写作」成功后调用）。
    返回新行的 id，供后续「优化」时 UPDATE 同一条记录。
    """
    init_db()
    now = _now_str()
    titles_json = json.dumps(result.titles, ensure_ascii=False)

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO posts (
                theme, style, user_notes, titles_json, content,
                round_num, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                theme,
                style,
                user_notes or "",
                titles_json,
                result.content,
                round_num,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_record(
    record_id: int,
    result: Xiaohongshu,
    round_num: int,
) -> None:
    """更新已有记录（多轮优化后调用，不新增一行，避免历史列表刷屏）。"""
    init_db()
    titles_json = json.dumps(result.titles, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            UPDATE posts
            SET titles_json = ?, content = ?, round_num = ?, updated_at = ?
            WHERE id = ?
            """,
            (titles_json, result.content, round_num, _now_str(), record_id),
        )
        conn.commit()


def list_records(limit: int = 30) -> List[Dict[str, Any]]:
    """列出最近的历史，按更新时间倒序。"""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, theme, style, round_num, created_at, updated_at,
                   titles_json
            FROM posts
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    records = []
    for row in rows:
        titles = json.loads(row["titles_json"])
        records.append(
            {
                "id": row["id"],
                "theme": row["theme"],
                "style": row["style"],
                "round_num": row["round_num"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "preview_title": titles[0] if titles else row["theme"],
            }
        )
    return records


def get_record(record_id: int) -> Optional[Dict[str, Any]]:
    """按 id 读取完整一条，用于「从历史加载到当前编辑区」。"""
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        return None

    return {
        "id": row["id"],
        "theme": row["theme"],
        "style": row["style"],
        "user_notes": row["user_notes"] or "",
        "titles": json.loads(row["titles_json"]),
        "content": row["content"],
        "round_num": row["round_num"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def record_to_xiaohongshu(record: Dict[str, Any]) -> Xiaohongshu:
    """把数据库记录转回 Pydantic 对象，供页面展示和继续优化。"""
    return Xiaohongshu(titles=record["titles"], content=record["content"])


def delete_record(record_id: int) -> None:
    """删除一条历史（可选功能）。"""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (record_id,))
        conn.commit()
