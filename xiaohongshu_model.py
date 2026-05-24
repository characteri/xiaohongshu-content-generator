##这个文件用Pydantic定义了一个 “小红书文案” 的数据结构模板，强制要求 AI 生成的结果必须符合这个格式。


from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List ## 用于定义“列表”类型

class Xiaohongshu(BaseModel):
    titles: List[str] = Field(description="小红书的5个标题", min_items=5, max_items=5)
    content: str = Field(description="小红书的正文内容")