from datetime import timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from deerflow.scheduler.manager import SchedulerManager
from deerflow.scheduler.template_engine import render_template

UTC8 = timezone(timedelta(hours=8))


def test_builtin_date():
    result = render_template("今天是 {{date}}", {}, "testuser")
    assert "{{date}}" not in result
    assert len(result.split("-")) == 3


def test_builtin_datetime():
    result = render_template("时间 {{datetime}}", {}, "testuser")
    assert "{{datetime}}" not in result


def test_builtin_time():
    result = render_template("时间 {{time}}", {}, "testuser")
    assert "{{time}}" not in result


def test_builtin_day_of_week():
    result = render_template("星期 {{day_of_week}}", {}, "testuser")
    assert "{{day_of_week}}" not in result
    assert result.startswith("星期")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    assert result.split(" ")[1] in weekdays


def test_builtin_user_name():
    result = render_template("用户 {{user_name}} 你好", {}, "testuser")
    assert result == "用户 testuser 你好"


def test_custom_variable():
    result = render_template(
        "查询 {{report_type}} 情况",
        {"report_type": "销售"},
        "testuser",
    )
    assert result == "查询 销售 情况"


def test_custom_overrides_builtin():
    result = render_template(
        "用户 {{user_name}}",
        {"user_name": "自定义名"},
        "testuser",
    )
    assert result == "用户 自定义名"


def test_unmatched_variable_preserved():
    result = render_template("未知 {{unknown_var}} 保留", {}, "testuser")
    assert result == "未知 {{unknown_var}} 保留"


def test_multiple_variables():
    result = render_template(
        "{{user_name}} 在 {{date}} 查询 {{report_type}}",
        {"report_type": "库存"},
        "testuser",
    )
    assert "testuser" in result
    assert "库存" in result
    assert "{{" not in result


class TestSchedulerManager:
    def test_singleton(self):
        mgr1 = SchedulerManager.get_instance()
        mgr2 = SchedulerManager.get_instance()
        assert mgr1 is mgr2

    def test_compute_next_run_valid(self):
        result = SchedulerManager.compute_next_run("0 9 * * *")
        assert result is not None

    def test_compute_next_run_invalid(self):
        result = SchedulerManager.compute_next_run("invalid")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_and_remove_task(self):
        mgr = SchedulerManager()
        mock_executor = MagicMock()
        mock_executor.execute_task = AsyncMock()
        mgr.set_executor(mock_executor)
        mgr.start()
        mgr.register_task("test-task-id", "0 9 * * *")
        mgr.remove_task("test-task-id")
        mgr.stop()


class TestTemplateEngineExtended:
    def test_empty_template(self):
        result = render_template("", {}, "user")
        assert result == ""

    def test_no_variables(self):
        result = render_template("plain text", {}, "user")
        assert result == "plain text"

    def test_empty_custom_variables(self):
        result = render_template("hello {{user_name}}", {}, "alice")
        assert result == "hello alice"

    def test_multiple_same_variable(self):
        result = render_template("{{user_name}} says hi to {{user_name}}", {}, "bob")
        assert result == "bob says hi to bob"
