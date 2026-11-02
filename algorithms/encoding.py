"""编码转换算法：Base64、Base32、URL 编码、Hex 编解码。

解码结果为非 UTF-8 可读的二进制时，以十六进制形式返回。
"""

import base64
import binascii
import urllib.parse
from typing import Any, Dict, List

from .registry import AlgorithmInput, register

_MODE_INPUTS: List[AlgorithmInput] = [
    AlgorithmInput(
        "mode", "select", "操作",
        options=[{"value": "encode", "label": "编码"}, {"value": "decode", "label": "解码"}],
        default="encode",
    ),
    AlgorithmInput("text", "text", "内容", placeholder="输入要编码或解码的内容"),
]


def _binary_result(raw: bytes, label: str) -> Dict[str, Any]:
    """解码结果转文本；二进制内容以 hex 展示并支持下载。"""
    try:
        return {"outputs": [{"label": label, "value": raw.decode("utf-8")}]}
    except UnicodeDecodeError:
        return {
            "outputs": [
                {
                    "label": label,
                    "value": raw.hex(),
                    "filename": f"{label}.bin",
                    "note": "解码结果为二进制数据，已按十六进制展示，可下载原始内容",
                }
            ]
        }


@register(
    "base64", "Base64 编解码", "encoding",
    "Base64 编码/解码：将二进制数据表示为 64 个可打印字符，常用于邮件、JSON、图片内嵌等场景。",
    _MODE_INPUTS,
)
def base64_codec(inputs: Dict[str, Any]) -> Dict[str, Any]:
    mode = inputs.get("mode", "encode")
    text = (inputs.get("text") or "").encode("utf-8")
    if mode == "encode":
        return {"outputs": [{"label": "Base64 编码结果", "value": base64.b64encode(text).decode("ascii")}]}
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        return {"error": f"不是合法的 Base64 文本：{exc}"}
    return _binary_result(raw, "Base64 解码结果")


@register(
    "base32", "Base32 编解码", "encoding",
    "Base32 编码/解码：32 个字符（A-Z 与 2-7）表示二进制数据，常用于 TOTP 密钥等场景。",
    _MODE_INPUTS,
)
def base32_codec(inputs: Dict[str, Any]) -> Dict[str, Any]:
    mode = inputs.get("mode", "encode")
    text = (inputs.get("text") or "").encode("utf-8")
    if mode == "encode":
        return {"outputs": [{"label": "Base32 编码结果", "value": base64.b32encode(text).decode("ascii")}]}
    try:
        raw = base64.b32decode(text, casefold=True)
    except (binascii.Error, ValueError) as exc:
        return {"error": f"不是合法的 Base32 文本：{exc}"}
    return _binary_result(raw, "Base32 解码结果")


@register(
    "url", "URL 编解码", "encoding",
    "URL 百分号编码/解码：将特殊字符转换为 %XX 形式，用于 URL 参数与路径。",
    _MODE_INPUTS,
)
def url_codec(inputs: Dict[str, Any]) -> Dict[str, Any]:
    mode = inputs.get("mode", "encode")
    text = inputs.get("text") or ""
    if mode == "encode":
        return {"outputs": [{"label": "URL 编码结果", "value": urllib.parse.quote(text, safe="")}]}
    try:
        return {"outputs": [{"label": "URL 解码结果", "value": urllib.parse.unquote(text)}]}
    except Exception as exc:  # 百分号转义不完整时抛异常
        return {"error": f"URL 解码失败：{exc}"}


@register(
    "hex", "Hex 编解码", "encoding",
    "十六进制编码/解码：字节与十六进制字符串（0-9a-f）互转，常用于查看二进制内容。",
    _MODE_INPUTS,
)
def hex_codec(inputs: Dict[str, Any]) -> Dict[str, Any]:
    mode = inputs.get("mode", "encode")
    text = inputs.get("text") or ""
    if mode == "encode":
        return {"outputs": [{"label": "Hex 编码结果", "value": text.encode("utf-8").hex()}]}
    try:
        raw = bytes.fromhex(text.replace(" ", "").replace("\n", ""))
    except ValueError as exc:
        return {"error": f"不是合法的十六进制文本：{exc}"}
    return _binary_result(raw, "Hex 解码结果")
