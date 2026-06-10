import re
from datetime import datetime, timedelta, timezone

UTC8 = timezone(timedelta(hours=8))

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


def _builtin_vars(user_name: str) -> dict[str, str]:
    now = datetime.now(UTC8)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": WEEKDAYS_CN[now.weekday()],
        "user_name": user_name,
    }


def render_template(
    template: str,
    custom_variables: dict[str, str],
    user_name: str,
) -> str:
    variables = _builtin_vars(user_name)
    variables.update(custom_variables)

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return _TEMPLATE_RE.sub(_replace, template)
