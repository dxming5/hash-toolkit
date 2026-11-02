"""加解密算法：AES(CBC/GCM)、DES、3DES、RSA 密钥对生成/加解密/签名验签。

- 对称加密密文统一格式：Base64(IV|Nonce + 密文[+Tag])
- 密钥以 UTF-8 文本输入，长度必须符合算法要求
- RSA 密钥以 PEM 文本输入/输出
"""

import base64
import os
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# TripleDES 已移至 decrepit 模块（cryptography 47+）；旧版本回退到 primitives 导入
try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
except ImportError:  # pragma: no cover - 旧版本 cryptography
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES

from .registry import AlgorithmInput, register

_IV_LEN = 16
_GCM_NONCE_LEN = 12
_GCM_TAG_LEN = 16


def _key_bytes(key: str, sizes: Tuple[int, ...]) -> Optional[bytes]:
    """校验密钥长度，返回密钥字节；不合法时返回 None。"""
    raw = key.encode("utf-8")
    if len(raw) not in sizes:
        return None
    return raw


def _to_bytes(text: str) -> bytes:
    return (text or "").encode("utf-8")


def _text_result(raw: bytes, label: str) -> Dict[str, Any]:
    """解密明文转文本；二进制内容以 hex 展示并支持下载。"""
    try:
        return {"outputs": [{"label": label, "value": raw.decode("utf-8")}]}
    except UnicodeDecodeError:
        return {
            "outputs": [
                {
                    "label": label,
                    "value": raw.hex(),
                    "filename": f"{label}.bin",
                    "note": "解密结果为二进制数据，已按十六进制展示，可下载原始内容",
                }
            ]
        }


# ==================== AES ====================

_AES_INPUTS: List[AlgorithmInput] = [
    AlgorithmInput(
        "mode", "select", "加密模式",
        options=[{"value": "cbc", "label": "CBC（PKCS7 填充）"}, {"value": "gcm", "label": "GCM（带完整性认证）"}],
        default="cbc",
    ),
    AlgorithmInput(
        "key", "key", "密钥",
        placeholder="UTF-8 文本密钥，长度须为 16/24/32 字节（对应 AES-128/192/256）",
    ),
    AlgorithmInput("text", "text", "明文内容", placeholder="要加密的文本"),
]


def _aes_cbc_encrypt(plain: bytes, key: bytes) -> bytes:
    iv = os.urandom(_IV_LEN)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return iv + enc.update(padded) + enc.finalize()


def _aes_cbc_decrypt(raw: bytes, key: bytes) -> bytes:
    iv, ct = raw[:_IV_LEN], raw[_IV_LEN:]
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _aes_gcm_encrypt(plain: bytes, key: bytes) -> bytes:
    nonce = os.urandom(_GCM_NONCE_LEN)
    enc = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ct = enc.update(plain) + enc.finalize()
    return nonce + ct + enc.tag


def _aes_gcm_decrypt(raw: bytes, key: bytes) -> bytes:
    nonce, ct, tag = raw[:_GCM_NONCE_LEN], raw[_GCM_NONCE_LEN:-_GCM_TAG_LEN], raw[-_GCM_TAG_LEN:]
    dec = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
    return dec.update(ct) + dec.finalize()


@register(
    "aes-encrypt", "AES 加密", "crypto",
    "AES 对称加密。CBC 模式为通用分组加密（PKCS7 填充）；GCM 模式附带完整性认证标签，"
    "可检测密文是否被篡改。密文输出为 Base64 文本。",
    _AES_INPUTS,
)
def aes_encrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = _key_bytes(inputs.get("key", ""), (16, 24, 32))
    if key is None:
        return {"error": "AES 密钥长度无效：UTF-8 编码后须为 16/24/32 字节"}
    plain = _to_bytes(inputs.get("text", ""))
    if not plain:
        return {"error": "请输入明文内容"}
    mode = inputs.get("mode", "cbc")
    if mode == "gcm":
        raw = _aes_gcm_encrypt(plain, key)
        label = "AES-GCM 密文（Base64，含 Nonce 与认证标签）"
    else:
        raw = _aes_cbc_encrypt(plain, key)
        label = "AES-CBC 密文（Base64，含 IV）"
    return {"outputs": [{"label": label, "value": base64.b64encode(raw).decode("ascii")}]}


@register(
    "aes-decrypt", "AES 解密", "crypto",
    "解密 AES 密文（Base64 输入，须与加密时模式一致）。密钥错误或密文被篡改时给出提示。",
    [
        AlgorithmInput(
            "mode", "select", "加密模式",
            options=[{"value": "cbc", "label": "CBC（PKCS7 填充）"}, {"value": "gcm", "label": "GCM（带完整性认证）"}],
            default="cbc",
        ),
        AlgorithmInput(
            "key", "key", "密钥",
            placeholder="UTF-8 文本密钥，长度须为 16/24/32 字节",
        ),
        AlgorithmInput("text", "text", "密文内容", placeholder="Base64 格式的密文"),
    ],
)
def aes_decrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = _key_bytes(inputs.get("key", ""), (16, 24, 32))
    if key is None:
        return {"error": "AES 密钥长度无效：UTF-8 编码后须为 16/24/32 字节"}
    try:
        raw = base64.b64decode(inputs.get("text", ""), validate=True)
    except ValueError:
        return {"error": "密文不是合法的 Base64 文本"}
    mode = inputs.get("mode", "cbc")
    try:
        if mode == "gcm":
            plain = _aes_gcm_decrypt(raw, key)
        else:
            plain = _aes_cbc_decrypt(raw, key)
    except InvalidTag:
        return {"error": "GCM 认证失败：密钥错误或密文被篡改"}
    except ValueError:
        return {"error": "解密失败：密钥错误、密文损坏或模式不匹配"}
    return _text_result(plain, "AES 解密明文")


# ==================== DES / 3DES（兼容遗留场景） ====================

_DES_KEY_INPUT = AlgorithmInput(
    "key", "key", "密钥",
    placeholder="UTF-8 文本密钥，DES 须 8 字节，3DES 须 16/24 字节",
)
_DES_TEXT_INPUT = AlgorithmInput("text", "text", "明文内容", placeholder="要加密的文本")
_DES_CT_INPUT = AlgorithmInput("text", "text", "密文内容", placeholder="Base64 格式的密文")


# cryptography 已移除单重 DES；利用 3DES-EDE 三键相同（K1=K2=K3）数学等价于单重 DES
def _des(key: bytes):
    return TripleDES(key * 3)


def _tdes_key(key: bytes) -> bytes:
    """two-key 3DES（16 字节）按标准扩展 K3=K1 为 24 字节，消除弃用警告。"""
    return key + key[:8] if len(key) == 16 else key


def _des_cbc_encrypt(plain: bytes, key: bytes, cipher_alg) -> bytes:
    iv = os.urandom(8)
    padder = padding.PKCS7(64).padder()
    padded = padder.update(plain) + padder.finalize()
    enc = Cipher(cipher_alg(key), modes.CBC(iv)).encryptor()
    return iv + enc.update(padded) + enc.finalize()


def _des_cbc_decrypt(raw: bytes, key: bytes, cipher_alg) -> bytes:
    iv, ct = raw[:8], raw[8:]
    dec = Cipher(cipher_alg(key), modes.CBC(iv)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(64).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


@register(
    "des-encrypt", "DES 加密", "crypto",
    "DES 对称加密（CBC 模式，PKCS7 填充）。56 位密钥已可被暴力破解，"
    "仅用于兼容遗留系统，新场景请使用 AES。",
    [_DES_KEY_INPUT, _DES_TEXT_INPUT],
)
def des_encrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = _key_bytes(inputs.get("key", ""), (8,))
    if key is None:
        return {"error": "DES 密钥长度无效：UTF-8 编码后须为 8 字节"}
    plain = _to_bytes(inputs.get("text", ""))
    if not plain:
        return {"error": "请输入明文内容"}
    raw = _des_cbc_encrypt(plain, key, _des)
    return {"outputs": [{"label": "DES 密文（Base64，含 IV）", "value": base64.b64encode(raw).decode("ascii")}]}


@register(
    "des-decrypt", "DES 解密", "crypto",
    "解密 DES 密文（Base64 输入）。仅用于兼容遗留系统，新场景请使用 AES。",
    [_DES_KEY_INPUT, _DES_CT_INPUT],
)
def des_decrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = _key_bytes(inputs.get("key", ""), (8,))
    if key is None:
        return {"error": "DES 密钥长度无效：UTF-8 编码后须为 8 字节"}
    try:
        raw = base64.b64decode(inputs.get("text", ""), validate=True)
    except ValueError:
        return {"error": "密文不是合法的 Base64 文本"}
    try:
        plain = _des_cbc_decrypt(raw, key, _des)
    except ValueError:
        return {"error": "解密失败：密钥错误或密文损坏"}
    return _text_result(plain, "DES 解密明文")


@register(
    "3des-encrypt", "3DES 加密", "crypto",
    "三重 DES 对称加密（CBC 模式，PKCS7 填充）。较 DES 安全，但已逐步被 AES 取代，"
    "常用于金融行业遗留接口兼容。",
    [_DES_KEY_INPUT, _DES_TEXT_INPUT],
)
def tdes_encrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = _key_bytes(inputs.get("key", ""), (16, 24))
    if key is None:
        return {"error": "3DES 密钥长度无效：UTF-8 编码后须为 16/24 字节"}
    key = _tdes_key(key)
    plain = _to_bytes(inputs.get("text", ""))
    if not plain:
        return {"error": "请输入明文内容"}
    raw = _des_cbc_encrypt(plain, key, TripleDES)
    return {"outputs": [{"label": "3DES 密文（Base64，含 IV）", "value": base64.b64encode(raw).decode("ascii")}]}


@register(
    "3des-decrypt", "3DES 解密", "crypto",
    "解密三重 DES 密文（Base64 输入）。常用于金融行业遗留接口兼容。",
    [_DES_KEY_INPUT, _DES_CT_INPUT],
)
def tdes_decrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = _key_bytes(inputs.get("key", ""), (16, 24))
    if key is None:
        return {"error": "3DES 密钥长度无效：UTF-8 编码后须为 16/24 字节"}
    key = _tdes_key(key)
    try:
        raw = base64.b64decode(inputs.get("text", ""), validate=True)
    except ValueError:
        return {"error": "密文不是合法的 Base64 文本"}
    try:
        plain = _des_cbc_decrypt(raw, key, TripleDES)
    except ValueError:
        return {"error": "解密失败：密钥错误或密文损坏"}
    return _text_result(plain, "3DES 解密明文")


# ==================== RSA ====================

@register(
    "rsa-keygen", "RSA 密钥对生成", "crypto",
    "生成 RSA 公钥/私钥对（PEM 格式）。密钥越大越安全但生成越慢，4096 位可能需要数十秒。"
    "私钥请妥善保管，工具本身不会存储任何内容。",
    [
        AlgorithmInput(
            "bits", "select", "密钥长度",
            options=[
                {"value": "2048", "label": "2048 位（推荐）"},
                {"value": "3072", "label": "3072 位"},
                {"value": "4096", "label": "4096 位"},
            ],
            default="2048",
        ),
    ],
)
def rsa_keygen(inputs: Dict[str, Any]) -> Dict[str, Any]:
    bits = int(inputs.get("bits", "2048"))
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return {
        "outputs": [
            {"label": "私钥（PEM）", "value": priv_pem, "filename": "private_key.pem"},
            {"label": "公钥（PEM）", "value": pub_pem, "filename": "public_key.pem"},
        ]
    }


def _load_public_key(pem: str):
    try:
        return serialization.load_pem_public_key(pem.encode("utf-8"))
    except ValueError:
        return None


def _load_private_key(pem: str):
    try:
        return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except ValueError:
        return None


@register(
    "rsa-encrypt", "RSA 公钥加密", "crypto",
    "使用 RSA 公钥加密（OAEP-SHA256 填充），输出 Base64 密文。"
    "2048 位密钥单次最多加密约 190 字节明文，长文本请改用 AES 并加密其密钥。",
    [
        AlgorithmInput("pubkey", "text", "公钥（PEM）", placeholder="-----BEGIN PUBLIC KEY----- ..."),
        AlgorithmInput("text", "text", "明文内容", placeholder="要加密的文本（较短）"),
    ],
)
def rsa_encrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    pub = _load_public_key(inputs.get("pubkey", ""))
    if pub is None:
        return {"error": "公钥不是合法的 PEM 格式"}
    plain = _to_bytes(inputs.get("text", ""))
    if not plain:
        return {"error": "请输入明文内容"}
    try:
        ct = pub.encrypt(plain, asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(), label=None,
        ))
    except ValueError:
        return {"error": "明文过长：超出该密钥长度下 OAEP 加密的最大长度（2048 位约 190 字节）"}
    return {"outputs": [{"label": "RSA 密文（Base64）", "value": base64.b64encode(ct).decode("ascii")}]}


@register(
    "rsa-decrypt", "RSA 私钥解密", "crypto",
    "使用 RSA 私钥解密 Base64 密文（OAEP-SHA256 填充）。",
    [
        AlgorithmInput("privkey", "text", "私钥（PEM）", placeholder="-----BEGIN PRIVATE KEY----- ..."),
        AlgorithmInput("text", "text", "密文内容", placeholder="Base64 格式的密文"),
    ],
)
def rsa_decrypt(inputs: Dict[str, Any]) -> Dict[str, Any]:
    priv = _load_private_key(inputs.get("privkey", ""))
    if priv is None:
        return {"error": "私钥不是合法的 PEM 格式"}
    try:
        raw = base64.b64decode(inputs.get("text", ""), validate=True)
    except ValueError:
        return {"error": "密文不是合法的 Base64 文本"}
    try:
        plain = priv.decrypt(raw, asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(), label=None,
        ))
    except ValueError:
        return {"error": "解密失败：私钥与密文不匹配或密文损坏"}
    return _text_result(plain, "RSA 解密明文")


@register(
    "rsa-sign", "RSA 签名", "crypto",
    "使用 RSA 私钥对文本签名（SHA-256 + PSS），输出 Base64 签名值。",
    [
        AlgorithmInput("privkey", "text", "私钥（PEM）", placeholder="-----BEGIN PRIVATE KEY----- ..."),
        AlgorithmInput("text", "text", "待签名内容", placeholder="要签名的文本"),
    ],
)
def rsa_sign(inputs: Dict[str, Any]) -> Dict[str, Any]:
    priv = _load_private_key(inputs.get("privkey", ""))
    if priv is None:
        return {"error": "私钥不是合法的 PEM 格式"}
    data = _to_bytes(inputs.get("text", ""))
    if not data:
        return {"error": "请输入待签名内容"}
    sig = priv.sign(
        data,
        asym_padding.PSS(
            mgf=asym_padding.MGF1(hashes.SHA256()),
            salt_length=asym_padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {"outputs": [{"label": "RSA 签名值（Base64）", "value": base64.b64encode(sig).decode("ascii")}]}


@register(
    "rsa-verify", "RSA 验签", "crypto",
    "使用 RSA 公钥验证签名（SHA-256 + PSS）是否与原文匹配。",
    [
        AlgorithmInput("pubkey", "text", "公钥（PEM）", placeholder="-----BEGIN PUBLIC KEY----- ..."),
        AlgorithmInput("text", "text", "原始内容", placeholder="签名时的原始文本"),
        AlgorithmInput("signature", "text", "签名值", placeholder="Base64 格式的签名"),
    ],
)
def rsa_verify(inputs: Dict[str, Any]) -> Dict[str, Any]:
    pub = _load_public_key(inputs.get("pubkey", ""))
    if pub is None:
        return {"error": "公钥不是合法的 PEM 格式"}
    try:
        sig = base64.b64decode(inputs.get("signature", ""), validate=True)
    except ValueError:
        return {"error": "签名值不是合法的 Base64 文本"}
    data = _to_bytes(inputs.get("text", ""))
    if not data:
        return {"error": "请输入原始内容"}
    try:
        pub.verify(
            sig,
            data,
            asym_padding.PSS(
                mgf=asym_padding.MGF1(hashes.SHA256()),
                salt_length=asym_padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return {"outputs": [{"label": "验签结果", "value": "签名有效"}]}
    except InvalidSignature:
        return {"outputs": [{"label": "验签结果", "value": "签名无效（内容被篡改或公钥不匹配）"}]}
