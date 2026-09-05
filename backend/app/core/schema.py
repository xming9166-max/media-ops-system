"""通用 Schema 基类与分页模型。

提供:
- BaseSchema: 所有 Schema 的基类(当前不做任何封装,仅作为统一入口,
  便于后续统一管理配置如 model_config)
- PageQuery / PageResult: 通用分页查询入参/出参
"""

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """所有 Schema 的基类。

    便于后续统一管理配置(如 model_config)。
    当前不做任何封装,仅作为统一入口。
    """

    model_config = ConfigDict(extra="forbid")


class PageQuery(BaseSchema):
    """通用分页查询入参。"""

    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class PageResult[T](BaseSchema):
    """通用分页查询出参。"""

    items: list[T]
    total: int
    page: int
    page_size: int
