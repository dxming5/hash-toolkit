# Hash-Toolkit 算法集合工具

本地运行的 Web 算法工具箱：哈希摘要、编码转换、加解密、实用工具。浏览器访问，数据仅在本机内存中处理，不落盘、不上传。

## 快速开始

```powershell
# 1. 安装依赖
python -m pip install -r requirements.txt

# 2. 启动服务（监听 127.0.0.1，仅本机可访问）
python -m uvicorn app:app --host 127.0.0.1 --port 8000

# 3. 浏览器打开
# http://127.0.0.1:8000
```

## 算法清单

| 分类 | 算法 |
| --- | --- |
| 哈希摘要 | MD5、SHA-1、SHA-256、SHA-512、SHA3-256、BLAKE2b、CRC32（支持文本与文件） |
| 编码转换 | Base64、Base32、URL 编码、Hex 编解码 |
| 加解密 | AES-CBC/GCM 加解密、DES 加解密、3DES 加解密、RSA 密钥对生成/公钥加密/私钥解密/签名/验签 |
| 实用工具 | UUID v4/v1 批量生成、HMAC-SHA1/SHA256、随机密码生成 |

## 项目结构

```
hash-toolkit/
├── app.py                    # FastAPI 入口：API 路由 + 静态页面
├── algorithms/
│   ├── __init__.py           # 导入所有算法模块，触发注册
│   ├── registry.py           # 注册表核心：@register 装饰器 + 输入/算法描述模型
│   ├── hashing.py            # 哈希摘要（hashlib，文件流式计算）
│   ├── encoding.py           # 编码转换（base64/urllib）
│   ├── crypto.py             # 加解密（cryptography）
│   └── utility.py            # 实用工具（uuid/hmac/secrets）
├── static/                   # 前端单页（无构建工具、无 CDN 依赖）
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── tests/test_algorithms.py  # 标准向量测试（NIST/RFC 4231 等）
└── requirements.txt
```

## 架构：算法注册表

后端每个算法是一个**自描述注册项**，前端通过 `GET /api/algorithms` 拉取目录并**动态渲染表单**，因此新增算法前端零改动。

```
@register(id, 名称, 分类, 描述, inputs)
def handler(inputs: dict) -> dict: ...
```

- `inputs`：字段定义列表，类型支持 `text`（多行文本）、`key`（密钥）、`file`（文件拖拽）、`select`（下拉）、`number`（数字）
- `handler` 返回约定：
  - 成功：`{"outputs": [{"label", "value", "filename"?}]}`（`filename` 非空时前端提供下载按钮）
  - 失败：`{"error": "可读错误信息"}`

## 新增算法（两步）

以新增 SM3 哈希为例（`algorithms/hashing.py`）：

```python
@register(
    "sm3", "SM3", "hashing",
    "SM3 国密哈希算法，输出 256 位摘要。",
    _TEXT_FILE_INPUTS,  # 复用文本/文件输入定义
)
def sm3(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # 实现 SM3 计算，返回 {"outputs": [...]} 或 {"error": "..."}
    ...
```

1. 在 `algorithms/` 对应模块写 handler 并加 `@register(...)`
2. 若新增了模块文件，在 `algorithms/__init__.py` 中追加 import

刷新页面即可看到新算法，无需改动前端。

## 运行测试

```powershell
python -m pytest tests/ -v
```

覆盖标准向量：MD5/SHA 官方摘要、RFC 4231 HMAC 向量、AES/DES 往返、GCM 篡改检测、RSA 加解密与签名验签、编码往返一致性。

## 设计说明

- **安全**：仅监听 `127.0.0.1`；无数据库、无状态；RSA 私钥仅在浏览器内存中生成展示
- **大文件**：文件哈希采用 1MB 分块流式计算，内存占用恒定
- **兼容性**：DES 依赖 cryptography 已移除，内部通过 3DES-EDE 三键相同（K1=K2=K3）数学等价实现；two-key 3DES（16 字节密钥）自动扩展 K3=K1
- **错误处理**：非法密钥、损坏密文、非法编码输入均返回可读提示，服务不崩溃

## 常见问题

- **pip 安装慢/失败**：使用国内镜像 `python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
- **AES 密钥报"长度无效"**：密钥为 UTF-8 文本，字节长度须为 16/24/32（即中文密钥按 3 字节/字计算）
- **RSA 加密报"明文过长"**：2048 位密钥 OAEP 最多约 190 字节，长文本请用 AES
