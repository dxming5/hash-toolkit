"""哈希摘要算法：MD5、SHA 系列、BLAKE2b、CRC32。

支持文本与文件两种输入（二选一）；文件采用分块流式计算，大文件不占内存。
"""

import hashlib
import zlib
from typing import Any, Dict, List

from .registry import AlgorithmInput, register

_CHUNK = 1024 * 1024  # 1MB 分块

# 文本/文件二选一的通用输入定义
_TEXT_FILE_INPUTS: List[AlgorithmInput] = [
    AlgorithmInput(
        "text", "text", "文本内容",
        required=False, placeholder="要计算哈希的文本（与文件二选一）",
    ),
    AlgorithmInput("file", "file", "文件", required=False),
]


def _read_source(inputs: Dict[str, Any]):
    """返回 (file-like | None, bytes | None)，file 优先于文本。

    文本字段为 None 表示未提供输入；显式传入空串则计算空串哈希。
    """
    file_obj = inputs.get("file")
    if file_obj is not None:
        return file_obj, None
    text = inputs.get("text")
    if text is None:
        return None, None
    return None, text.encode("utf-8")


def _hash_hex(inputs: Dict[str, Any], alg_name: str) -> Dict[str, Any]:
    file_obj, data = _read_source(inputs)
    if file_obj is None and not data:
        return {"error": "请输入文本或选择文件"}
    h = hashlib.new(alg_name)
    if file_obj is not None:
        while chunk := file_obj.read(_CHUNK):
            h.update(chunk)
    else:
        h.update(data)
    return {"outputs": [{"label": f"{alg_name} 摘要", "value": h.hexdigest()}]}


# ---- 批量注册 hashlib 支持的哈希算法 ----
_HASH_ALGS = [
    ("md5", "MD5",
     "MD5 消息摘要算法，输出 128 位（32 个十六进制字符）。不再推荐用于安全场景，"
     "常用于文件完整性校验。"),
    ("sha1", "SHA-1",
     "SHA-1 安全哈希算法，输出 160 位（40 个十六进制字符）。已不推荐用于数字签名，"
     "仍广泛用于 Git 等版本管理。"),
    ("sha256", "SHA-256",
     "SHA-2 家族 256 位摘要（64 个十六进制字符），目前应用最广泛的安全哈希算法。"),
    ("sha512", "SHA-512",
     "SHA-2 家族 512 位摘要（128 个十六进制字符），输出更长，抗碰撞能力更强。"),
    ("sha3_256", "SHA3-256",
     "SHA-3（Keccak）家族 256 位摘要，结构不同于 SHA-2，提供多样化安全选择。"),
    ("blake2b", "BLAKE2b",
     "BLAKE2b 高速哈希算法，默认输出 512 位（128 个十六进制字符），"
     "速度优于 MD5 且安全性更强。"),
]

for _alg_id, _name, _desc in _HASH_ALGS:
    def _make(alg_id: str = _alg_id, name: str = _name, desc: str = _desc):
        @register(alg_id, name, "hashing", desc, _TEXT_FILE_INPUTS)
        def _handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
            return _hash_hex(inputs, alg_id)
    _make()


@register(
    "crc32", "CRC32", "hashing",
    "CRC32 循环冗余校验，输出 32 位（8 个十六进制字符）。仅用于快速完整性校验，"
    "不具备安全性，常用于 zip/gzip 等格式。",
    _TEXT_FILE_INPUTS,
)
def crc32(inputs: Dict[str, Any]) -> Dict[str, Any]:
    file_obj, data = _read_source(inputs)
    if file_obj is None and not data:
        return {"error": "请输入文本或选择文件"}
    c = 0
    if file_obj is not None:
        while chunk := file_obj.read(_CHUNK):
            c = zlib.crc32(chunk, c)
    else:
        c = zlib.crc32(data, c)
    return {"outputs": [{"label": "CRC32 校验值", "value": f"{c & 0xFFFFFFFF:08x}"}]}
