"""实用工具：UUID 生成、HMAC、随机密码生成。"""

import hashlib
import hmac
import secrets
import string
import uuid as uuid_mod
from typing import Any, Dict, List

from .registry import AlgorithmInput, register

# ==================== UUID ====================

_UUID_COUNT_INPUT = AlgorithmInput(
    "count", "number", "生成个数",
    default=5, min=1, max=100,
)
_UUID_DESC = "批量生成 UUID。v4 为随机版本（推荐），v1 基于时间戳与 MAC 地址。格式为标准 8-4-4-4-12。"


def _uuid_generate(inputs: Dict[str, Any], version: int) -> Dict[str, Any]:
    try:
        count = int(inputs.get("count", 5))
    except (TypeError, ValueError):
        return {"error": "生成个数必须是数字"}
    if not 1 <= count <= 100:
        return {"error": "生成个数须在 1-100 之间"}
    lines = []
    for _ in range(count):
        lines.append(str(uuid_mod.uuid4() if version == 4 else uuid_mod.uuid1()))
    return {"outputs": [{"label": f"UUID v{version}（{count} 个）", "value": "\n".join(lines)}]}


@register("uuid4", "UUID v4 生成", "utility", _UUID_DESC, [_UUID_COUNT_INPUT])
def uuid4(inputs: Dict[str, Any]) -> Dict[str, Any]:
    return _uuid_generate(inputs, 4)


@register("uuid1", "UUID v1 生成", "utility", _UUID_DESC, [_UUID_COUNT_INPUT])
def uuid1(inputs: Dict[str, Any]) -> Dict[str, Any]:
    return _uuid_generate(inputs, 1)


# ==================== HMAC ====================

@register(
    "hmac", "HMAC 消息认证码", "utility",
    "基于密钥的哈希消息认证码，用于验证消息完整性与真实性（双方共享同一密钥）。"
    "输出十六进制摘要。",
    [
        AlgorithmInput(
            "algo", "select", "哈希算法",
            options=[{"value": "sha1", "label": "HMAC-SHA1"}, {"value": "sha256", "label": "HMAC-SHA256"}],
            default="sha256",
        ),
        AlgorithmInput("key", "key", "密钥", placeholder="共享密钥"),
        AlgorithmInput("text", "text", "消息内容", placeholder="要认证的消息"),
    ],
)
def hmac_code(inputs: Dict[str, Any]) -> Dict[str, Any]:
    algo = inputs.get("algo", "sha256")
    key = (inputs.get("key") or "").encode("utf-8")
    msg = (inputs.get("text") or "").encode("utf-8")
    if not key:
        return {"error": "请输入密钥"}
    if not msg:
        return {"error": "请输入消息内容"}
    digest = hmac.new(key, msg, hashlib.sha1 if algo == "sha1" else hashlib.sha256).hexdigest()
    return {"outputs": [{"label": f"HMAC-{algo.upper()} 摘要", "value": digest}]}


# ==================== 随机密码 ====================

@register(
    "password", "随机密码生成", "utility",
    "使用加密安全随机源生成随机密码，支持自定义长度、字符集与批量生成。",
    [
        AlgorithmInput("length", "number", "密码长度", default=16, min=4, max=128),
        AlgorithmInput(
            "charset", "select", "字符集",
            options=[
                {"value": "all", "label": "大小写字母 + 数字 + 符号（推荐）"},
                {"value": "alnum", "label": "大小写字母 + 数字"},
                {"value": "lower_num", "label": "小写字母 + 数字"},
                {"value": "digits", "label": "仅数字"},
            ],
            default="all",
        ),
        AlgorithmInput("count", "number", "生成个数", default=5, min=1, max=50),
    ],
)
def password_gen(inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        length = int(inputs.get("length", 16))
        count = int(inputs.get("count", 5))
    except (TypeError, ValueError):
        return {"error": "长度与个数必须是数字"}
    if not 4 <= length <= 128:
        return {"error": "密码长度须在 4-128 之间"}
    if not 1 <= count <= 50:
        return {"error": "生成个数须在 1-50 之间"}
    charset_map = {
        "all": string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.<>?",
        "alnum": string.ascii_letters + string.digits,
        "lower_num": string.ascii_lowercase + string.digits,
        "digits": string.digits,
    }
    charset = charset_map.get(inputs.get("charset", "all"), charset_map["all"])
    lines = ["".join(secrets.choice(charset) for _ in range(length)) for _ in range(count)]
    return {"outputs": [{"label": f"随机密码（{count} 个）", "value": "\n".join(lines)}]}
