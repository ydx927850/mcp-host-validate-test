"""阿里云API市场签名认证工具函数

实现阿里云API市场的AppKey+AppSecret签名认证，基于HmacSHA256算法。
签名串格式：HTTPMethod\nAccept\nContent-MD5\nContent-Type\nDate\nHeaders\nPathAndParameters

使用方式：
    from platforms.aliyun_market import build_aliyun_signature

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    build_aliyun_signature(
        method="GET",
        url="https://xxx.market.alicloudapi.com/api/xxx",
        headers=headers,
        query_params={"key": "value"},
        body=None,
        app_key="your_app_key",
        app_secret="your_app_secret",
    )
    # headers 已被原地修改，添加了 X-Ca-* 签名 header
"""

import hashlib
import hmac
import base64
import time
import uuid
from urllib.parse import urlparse, urlencode
from typing import Dict, Optional


def build_aliyun_signature(
    method: str,
    url: str,
    headers: Dict[str, str],
    query_params: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    app_key: str = "",
    app_secret: str = "",
) -> None:
    """构建阿里云API市场签名，原地修改headers添加签名相关header

    Args:
        method: HTTP方法（GET/POST等）
        url: 完整请求URL
        headers: 请求header字典，函数会原地添加签名header
        query_params: URL查询参数字典
        body: 请求体字符串（POST时使用）
        app_key: 阿里云AppKey
        app_secret: 阿里云AppSecret
    """
    # Step 1: 添加签名辅助 header
    headers["X-Ca-Key"] = app_key
    headers["X-Ca-Timestamp"] = str(int(time.time() * 1000))
    headers["X-Ca-Nonce"] = str(uuid.uuid4())
    headers["X-Ca-Signature-Method"] = "HmacSHA256"

    # Step 2: 构建签名串
    # HTTPMethod
    sign_str = method.upper() + "\n"

    # Accept
    accept = headers.get("Accept", "")
    sign_str += accept + "\n"

    # Content-MD5
    content_md5 = ""
    if body is not None and body != "":
        content_md5 = hashlib.md5(body.encode("utf-8")).hexdigest().upper()
        headers["Content-MD5"] = content_md5
    sign_str += content_md5 + "\n"

    # Content-Type
    content_type = headers.get("Content-Type", "")
    sign_str += content_type + "\n"

    # Date
    date = headers.get("Date", "")
    sign_str += date + "\n"

    # Headers: 按header名排序，格式为 "key1:value1\nkey2:value2\n"
    # 只参与以 X-Ca- 开头的自定义header
    ca_headers = {k: v for k, v in headers.items() if k.lower().startswith("x-ca-")}
    sorted_ca_keys = sorted(ca_headers.keys(), key=lambda x: x.lower())
    header_str = ""
    for key in sorted_ca_keys:
        header_str += f"{key.lower()}:{ca_headers[key]}\n"
    sign_str += header_str

    # PathAndParameters: URL path + sorted query string
    parsed = urlparse(url)
    path = parsed.path or "/"
    if query_params:
        sorted_params = sorted(query_params.items(), key=lambda x: x[0])
        query_string = urlencode(sorted_params)
        sign_str += path + "?" + query_string
    else:
        sign_str += path

    # Step 3: HmacSHA256 签名 + Base64 编码
    signature = base64.b64encode(
        hmac.new(
            app_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    # Step 4: 设置 X-Ca-Signature-Headers 和 X-Ca-Signature header
    headers["X-Ca-Signature-Headers"] = ",".join(k.lower() for k in sorted_ca_keys)
    headers["X-Ca-Signature"] = signature
