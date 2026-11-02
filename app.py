"""Hash-Toolkit 服务入口。

启动方式：python app.py
也可用可选方式：uvicorn app:app --host 127.0.0.1 --port 8000
浏览器访问 http://127.0.0.1:8000
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import algorithms  # noqa: F401  导入即触发所有算法注册
from algorithms.registry import get_algorithm, get_catalog

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Hash-Toolkit", description="算法集合工具：哈希、编码、加解密、实用工具")


@app.get("/api/algorithms")
def api_algorithms():
    """返回按分类分组的算法目录，前端据此渲染导航与表单。"""
    return {"groups": get_catalog()}


@app.post("/api/compute/{alg_id}")
async def api_compute(alg_id: str, request: Request):
    """执行指定算法。

    参数通过 multipart/form-data 提交，字段名与算法 inputs 定义的 name 对应；
    file 类型字段以文件上传形式提交。
    """
    alg = get_algorithm(alg_id)
    if alg is None:
        return JSONResponse({"error": f"未知算法：{alg_id}"}, status_code=404)

    form = await request.form()
    inputs = {}
    for inp in alg.inputs:
        if inp.type == "file":
            upload = form.get(inp.name)
            if upload is not None and getattr(upload, "filename", None):
                # 传文件对象（file-like），handler 内流式读取，大文件不占内存
                inputs[inp.name] = upload.file
            else:
                inputs[inp.name] = None
        else:
            val = form.get(inp.name)
            if val is not None:
                inputs[inp.name] = str(val)
            elif inp.default is not None:
                inputs[inp.name] = inp.default
            else:
                inputs[inp.name] = ""

    # 必填校验（text/file 二选一的场景由 handler 内校验）
    for inp in alg.inputs:
        val = inputs.get(inp.name)
        if inp.required and val in (None, ""):
            return JSONResponse({"error": f"缺少必填项：{inp.label}"}, status_code=400)

    try:
        # 计算可能耗时（哈希大文件、RSA 密钥生成），放入线程池避免阻塞事件循环
        result = await run_in_threadpool(alg.handler, inputs)
    except Exception as exc:  # noqa: BLE001  兜底：任何异常都不让服务崩溃
        return JSONResponse({"error": f"服务器内部错误：{exc}"}, status_code=500)

    return result


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
