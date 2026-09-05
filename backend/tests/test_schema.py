"""测试通用 Schema 基类与分页模型。"""

import pytest
from pydantic import ValidationError

from app.core.schema import BaseSchema, PageQuery, PageResult


class DemoSchema(BaseSchema):
    """用于验证 BaseSchema 可正常继承。"""

    name: str


class TestBaseSchema:
    """BaseSchema 校验。"""

    def test_inherits_pydantic_base_model(self):
        schema = DemoSchema(name="test")
        assert schema.name == "test"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            DemoSchema(name="test", extra_field="not_allowed")


class TestPageQuery:
    """PageQuery 默认值与边界校验。"""

    def test_default_values(self):
        query = PageQuery()
        assert query.page == 1
        assert query.page_size == 20

    def test_custom_values(self):
        query = PageQuery(page=3, page_size=50)
        assert query.page == 3
        assert query.page_size == 50

    def test_page_must_be_positive(self):
        with pytest.raises(ValidationError):
            PageQuery(page=0)

    def test_page_size_within_range(self):
        with pytest.raises(ValidationError):
            PageQuery(page_size=0)
        with pytest.raises(ValidationError):
            PageQuery(page_size=101)


class TestPageResult:
    """PageResult 泛型出参。"""

    def test_generic_typed_items(self):
        result = PageResult[str](
            items=["a", "b"],
            total=2,
            page=1,
            page_size=20,
        )
        assert result.items == ["a", "b"]
        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20

    def test_int_items(self):
        result = PageResult[int](items=[1, 2, 3], total=3, page=1, page_size=10)
        assert result.items == [1, 2, 3]
