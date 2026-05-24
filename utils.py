from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from prompt_template import (
    refine_system_template_text,
    refine_user_template_text,
    system_template_text,
    user_template_text,
)
from style_prompts import get_style_instructions
from xiaohongshu_model import Xiaohongshu

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def _normalize_user_notes(user_notes: str) -> str:
    text = (user_notes or "").strip()
    return text if text else "（用户未提供，请仅根据主题创作）"


def _format_previous_draft(previous: Xiaohongshu) -> str:
    titles_block = "\n".join(f"{i}. {t}" for i, t in enumerate(previous.titles, 1))
    return f"标题：\n{titles_block}\n\n正文：\n{previous.content}"


def _build_chain(system_text: str, user_text: str, api_key: str):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("user", user_text),
    ])
    model = ChatOpenAI(
        model=DEFAULT_MODEL,
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
    )
    output_parser = PydanticOutputParser(pydantic_object=Xiaohongshu)
    chain = prompt | model | output_parser
    return chain, output_parser


def generate_xiaohongshu(
    theme: str,
    api_key: str,
    style: str = "干货",
    user_notes: str = "",
) -> Xiaohongshu:
    chain, output_parser = _build_chain(
        system_template_text, user_template_text, api_key
    )
    return chain.invoke({
        "parser_instructions": output_parser.get_format_instructions(),
        "style_instructions": get_style_instructions(style),
        "theme": theme,
        "user_notes": _normalize_user_notes(user_notes),
    })


def refine_xiaohongshu(
    previous: Xiaohongshu,
    feedback: str,
    theme: str,
    api_key: str,
    style: str = "干货",
    user_notes: str = "",
) -> Xiaohongshu:
    chain, output_parser = _build_chain(
        refine_system_template_text, refine_user_template_text, api_key
    )
    return chain.invoke({
        "parser_instructions": output_parser.get_format_instructions(),
        "style_instructions": get_style_instructions(style),
        "theme": theme,
        "user_notes": _normalize_user_notes(user_notes),
        "previous_draft": _format_previous_draft(previous),
        "feedback": feedback.strip(),
    })
