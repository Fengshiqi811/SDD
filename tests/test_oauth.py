"""飞书 OAuth 流程单元测试。"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import httpx

from shared.oauth import add_app_to_tasklist, build_authorize_url, exchange_code


def test_build_authorize_url_contains_required_parameters():
    url = build_authorize_url(
        app_id="cli_test",
        redirect_uri="http://127.0.0.1:5000/oauth/callback",
        state="state-1",
        scopes=["offline_access", "task:tasklist:write"],
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.feishu.cn"
    assert query["client_id"] == ["cli_test"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["http://127.0.0.1:5000/oauth/callback"]
    assert query["scope"] == ["offline_access task:tasklist:write"]
    assert query["state"] == ["state-1"]


def test_exchange_code_returns_token_data():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "code-1"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "success",
                "data": {"access_token": "u-token", "refresh_token": "r-token"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        data = exchange_code(
            app_id="cli_test",
            app_secret="secret",
            code="code-1",
            redirect_uri="http://127.0.0.1:5000/oauth/callback",
            client=client,
        )

    assert data["access_token"] == "u-token"
    assert data["refresh_token"] == "r-token"


def test_add_app_to_tasklist_uses_user_token_and_app_member():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer u-token"
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"members": [{"id": "cli_test", "type": "app"}]}
        return httpx.Response(200, json={"code": 0, "msg": "success", "data": {}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = add_app_to_tasklist(
            user_access_token="u-token",
            tasklist_guid="guid-1",
            app_id="cli_test",
            client=client,
        )

    assert result == {}