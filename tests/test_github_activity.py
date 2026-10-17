"""GitHub 活动采集测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from collector.github_activity import collect_activity

SINCE = datetime(2026, 10, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 13, tzinfo=timezone.utc)


def test_collect_activity_returns_pr_issue_review_counts():
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("q", "")
        if "type:pr" in query and "reviewed-by" in query:
            items = [{"number": 3, "title": "评审科研代码", "state": "open", "html_url": "u3"}]
        elif "type:issue" in query:
            items = [{"number": 2, "title": "修复实验脚本", "state": "closed", "html_url": "u2"}]
        else:
            items = [{"number": 1, "title": "提交日报洞察", "state": "open", "html_url": "u1"}]
        return httpx.Response(200, json={"items": items})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com") as client:
        result = collect_activity(
            ["Fengshiqi811/SDD"],
            SINCE,
            UNTIL,
            "Fengshiqi811",
            client=client,
        )

    assert result["success"] is True
    assert result["counts"] == {"pull_requests": 1, "issues": 1, "reviews": 1}
    assert result["pull_requests"][0]["title"] == "提交日报洞察"
    assert result["issues"][0]["number"] == 2
    assert result["reviews"][0]["number"] == 3