"""算法注册表核心：@register 装饰器与算法描述模型。

每个算法通过 @register 装饰器注册为自描述的注册项：
- id / name / category / description：目录信息，前端据此展示
- inputs：输入字段定义，前端据此动态渲染表单控件
- handler：执行函数，签名 handler(inputs: dict) -> dict

handler 返回值约定：
- 成功：{"outputs": [{"label": str|None, "value": str, "filename": str|None}]}
        label 为结果标题，filename 非空时前端提供"下载"按钮
- 失败：{"error": "可读的错误信息"}
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# 算法分类目录（按此顺序展示；未声明的分类会兜底追加到末尾）
CATEGORIES: List[Dict[str, str]] = [
    {"id": "hashing", "name": "哈希摘要"},
    {"id": "encoding", "name": "编码转换"},
    {"id": "crypto", "name": "加解密"},
    {"id": "utility", "name": "实用工具"},
]


@dataclass
class AlgorithmInput:
    """单个输入字段定义，前端据此渲染表单控件。

    type 支持：
    - text：多行文本框
    - key：密钥输入（密码框，可切换可见性）
    - file：文件选择（支持拖拽）
    - select：下拉选择（options 为 [{"value", "label"}]）
    - number：数字输入（min/max 限定范围）
    """

    name: str
    type: str
    label: str
    required: bool = True
    placeholder: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None
    default: Any = None
    min: Optional[int] = None
    max: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "label": self.label,
            "required": self.required,
            "placeholder": self.placeholder,
            "options": self.options,
            "default": self.default,
            "min": self.min,
            "max": self.max,
        }


@dataclass
class Algorithm:
    id: str
    name: str
    category: str
    description: str
    inputs: List[AlgorithmInput]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "inputs": [inp.to_dict() for inp in self.inputs],
        }


_REGISTRY: Dict[str, Algorithm] = {}


def register(
    alg_id: str,
    name: str,
    category: str,
    description: str,
    inputs: List[AlgorithmInput],
) -> Callable:
    """装饰器：把函数注册为算法。"""

    def decorator(func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Callable:
        if alg_id in _REGISTRY:
            raise ValueError(f"算法 id 重复注册：{alg_id}")
        _REGISTRY[alg_id] = Algorithm(
            id=alg_id,
            name=name,
            category=category,
            description=description,
            inputs=inputs,
            handler=func,
        )
        return func

    return decorator


def get_algorithm(alg_id: str) -> Optional[Algorithm]:
    return _REGISTRY.get(alg_id)


def get_catalog() -> List[Dict[str, Any]]:
    """返回按分类分组的算法目录，供 /api/algorithms 使用。"""
    groups: List[Dict[str, Any]] = []
    for cat in CATEGORIES:
        algs = [a.to_dict() for a in _REGISTRY.values() if a.category == cat["id"]]
        if algs:
            groups.append({"id": cat["id"], "name": cat["name"], "algorithms": algs})
    # 兜底：已注册但未在 CATEGORIES 中声明的分类
    known = {c["id"] for c in CATEGORIES}
    for cat_id in sorted({a.category for a in _REGISTRY.values()} - known):
        algs = [a.to_dict() for a in _REGISTRY.values() if a.category == cat_id]
        groups.append({"id": cat_id, "name": cat_id, "algorithms": algs})
    return groups
