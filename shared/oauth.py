"""飞书 OAuth 2.0：用户授权、令牌交换与任务清单协作者绑定。"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL = "https://accounts.feishu.cn/oauth/v3/token"
TASK_LIST_MEMBERS_URL = "https://open.feishu.cn/open-apis/task/v2/tasklists/{tasklist_guid}/add_members"
DEFAULT_TIMEOUT = 30.0


class OAuthError(RuntimeError):
    """OAuth 或资源授权失败。"""


def build_authorize_url(
    *,
    app_id: str,
    redirect_uri: str,
    state: str,
    scopes: list[str],
) -> str:
    """构造飞书用户授权地址。"""
    query = urlencode(
        {
            "client_id": app_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "prompt": "consent",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code(
    *,
    app_id: str,
    app_secret: str,
    code: str,
    redirect_uri: str,
    client: httpx.Client | None = None,
) -> dict:
    """使用授权码换取 user_access_token 与 refresh_token。"""
    owns_client = client is None
    http_client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)
    try:
        response = http_client.post(
            TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "client_id": app_id,
                "client_secret": app_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise OAuthError("飞书 OAuth 令牌响应格式错误")
        if payload.get("code", 0) != 0:
            raise OAuthError(
                f"换取 user_access_token 失败: {payload.get('code')} {payload.get('msg')}"
            )
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        access_token = payload.get("access_token") or data.get("access_token")
        refresh_token = payload.get("refresh_token") or data.get("refresh_token")
        if not access_token:
            data_keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            raise OAuthError(
                "飞书 OAuth 响应缺少 access_token "
                f"(code={payload.get('code')}, msg={payload.get('msg')}, data_keys={data_keys})"
            )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token or "",
            "expires_in": payload.get("expires_in") or data.get("expires_in") or 0,
            "refresh_token_expires_in": payload.get("refresh_token_expires_in")
            or data.get("refresh_token_expires_in")
            or 0,
        }
    finally:
        if owns_client:
            http_client.close()


def add_app_to_tasklist(
    *,
    user_access_token: str,
    tasklist_guid: str,
    app_id: str,
    client: httpx.Client | None = None,
) -> dict:
    """使用用户权限把应用机器人加入任务清单，作为后续租户读取的授权依据。"""
    owns_client = client is None
    http_client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)
    try:
        response = http_client.post(
            TASK_LIST_MEMBERS_URL.format(tasklist_guid=tasklist_guid),
            headers={
                "Authorization": f"Bearer {user_access_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"members": [{"id": app_id, "type": "app"}]},
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise OAuthError("飞书任务清单授权响应格式错误")
        if payload.get("code", 0) != 0:
            raise OAuthError(
                f"加入任务清单失败: {payload.get('code')} {payload.get('msg')}"
            )
        return payload.get("data") or {}
    finally:
        if owns_client:
            http_client.close()
