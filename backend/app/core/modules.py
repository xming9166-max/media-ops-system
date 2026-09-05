"""模块自动发现与注册工具。

框架核心能力：按约定扫描 ``app.modules`` 下的业务模块，自动收集 Router 与 Model，
使新增业务模块时无需修改 ``app.factory`` 或 ``alembic/env.py``。

约定：
- 每个业务模块是一个 Python 包，位于 ``app.modules.<domain>``
- 路由：模块内 ``router.py`` 暴露 ``router``（fastapi.APIRouter 实例）
- 模型：模块内 ``model.py`` 定义 SQLAlchemy 模型（被导入即注册到 Base.metadata）

扫描过程不执行模块内其他文件，避免导入副作用。
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator
from typing import TYPE_CHECKING

from app.core.db.base import Base

if TYPE_CHECKING:
    from fastapi import APIRouter


MODULES_PACKAGE = "app.modules"


def iter_module_names() -> Iterator[str]:
    """遍历 ``app.modules`` 下的所有子包名（如 ``app.modules.health``）。"""
    package = importlib.import_module(MODULES_PACKAGE)
    if not hasattr(package, "__path__"):
        return
    for _, name, is_pkg in pkgutil.iter_modules(package.__path__, prefix=f"{MODULES_PACKAGE}."):
        if is_pkg:
            yield name


def import_module_routers() -> list[APIRouter]:
    """按约定导入各模块的 router，返回可用 router 列表。

    缺失 router.py 或 router 对象的模块会被静默跳过，避免空包阻塞启动。
    """
    from fastapi import APIRouter

    routers: list[APIRouter] = []
    for module_name in iter_module_names():
        router_module_name = f"{module_name}.router"
        try:
            router_module = importlib.import_module(router_module_name)
        except ModuleNotFoundError:
            continue
        router = getattr(router_module, "router", None)
        if isinstance(router, APIRouter):
            routers.append(router)
    return routers


def import_module_models() -> None:
    """按约定导入各模块的 model.py，确保 Base.metadata 包含所有业务模型。

    Alembic autogenerate 依赖此函数在迁移前完成模型注册。
    """
    for module_name in iter_module_names():
        model_module_name = f"{module_name}.model"
        try:
            importlib.import_module(model_module_name)
        except ModuleNotFoundError:
            continue


def get_target_metadata() -> Base.metadata:
    """返回已注册全部模块模型的 Base.metadata。"""
    import_module_models()
    return Base.metadata
