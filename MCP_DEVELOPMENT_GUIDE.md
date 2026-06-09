# MCP Server 开发指南

本模板用于开发 MCP Server 工具，开发完成后可直接托管到平台上运行。

## 重要：`open_platform_server.py` 文件名不能改

此文件是 faas 启动的入口，文件名必须保持不变。文件内容可以任意修改（删除示例、新增工具等）。

## 快速开始：新增一个工具

在 `open_platform_server.py` 中添加函数：

```python
from typing import Annotated, Any, Dict, Optional
from pydantic import Field

@server.tool()
async def my_tool(
    query: Annotated[str, Field(description="搜索关键词")],
    limit: Annotated[int, Field(ge=1, description="返回数量上限，默认10")] = 10,
) -> Dict[str, Any]:
    """搜索相关内容"""
    # 业务逻辑
    return {"results": []}
```

## 参数描述规范

### 使用 Annotated + Field 添加描述

**每个参数都必须有描述**，否则 LLM 无法判断何时使用该参数。使用 `Annotated[type, Field(description=...)]` 为参数添加描述和约束：

```python
from typing import Annotated
from pydantic import Field

@server.tool()
async def add(
    a: Annotated[int, Field(description="第一个操作数")],
    b: Annotated[int, Field(description="第二个操作数")],
) -> Dict[str, Any]:
    """加法运算"""
    return {"result": a + b}
```

`Field` 还支持约束校验，会体现在 JSON Schema 中：

```python
async def validate_user(
    name: Annotated[str, Field(min_length=1, max_length=50, description="用户名")],
    age: Annotated[int, Field(ge=0, le=150, description="年龄")],
    email: Annotated[str, Field(description="邮箱地址")],
) -> Dict[str, Any]:
    ...
```

### 为什么不用 docstring Args？

FastMCP 不会将 docstring `Args:` 段的参数描述写入 JSON Schema，只会体现在工具描述（toolDesc）中。使用 `Annotated[type, Field(description=...)]` 才能让描述出现在每个参数的 `description` 字段中，LLM 能更准确地理解参数含义。

### 类型注解

| Python 类型 | 说明 |
|------------|------|
| `str` | 字符串 |
| `int` | 整数 |
| `float` | 浮点数 |
| `bool` | 布尔值 |
| `Optional[str]` | 可选参数，可为 None |
| `List[int]` | 整数数组 |
| `Dict[str, Any]` | 字典 |

### 可选参数

使用 `Optional` 或默认值定义可选参数，配合 `Annotated + Field` 添加描述：

```python
async def search(
    query: Annotated[str, Field(description="搜索关键词")],
    limit: Annotated[int, Field(ge=1, description="返回数量上限，默认10")] = 10,
    sort: Annotated[Optional[str], Field(description="排序方式，为空则默认排序")] = None,
):
    """搜索"""
```

**注意**：使用可选参数时，必须在代码中做空值判断（`if x is not None` 或 `x or default_value`）。

### 复杂嵌套参数

当参数结构复杂（多层嵌套对象、对象数组等），使用 Pydantic BaseModel 作为参数类型：

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DataSource(BaseModel):
    """数据源"""
    type: str = Field(description="数据源类型，可选: database, api, file")
    host: str = Field(description="主机地址")
    port: int = Field(ge=1, le=65535, description="端口号")

class PipelineInput(BaseModel):
    """管道配置"""
    name: str = Field(description="管道名称")
    source: DataSource = Field(description="数据源配置")
    tags: Optional[List[str]] = Field(default=None, description="标签列表")

@server.tool()
async def analyze_pipeline(pipeline: Annotated[PipelineInput, Field(description="管道完整配置")]) -> Dict[str, Any]:
    """分析管道配置"""
    ...
```

BaseModel 中每个字段使用 `Field(description=...)` 添加描述，嵌套模型会自动展开为完整的 JSON Schema。

## 工具声明规范

### @server.tool() 装饰器

- 函数的 docstring 第一行是工具描述，LLM 据此判断何时调用此工具
- 描述应当简洁明确，说明工具的功能而非实现细节

```python
# 好的描述
"""对两个数进行加法运算"""

# 不好的描述 — 过于宽泛
"""计算"""
```

### 无参数工具

不需要任何参数时，函数签名无需参数：

```python
@server.tool()
async def get_env_configs() -> Dict[str, str]:
    """获取平台注入的环境变量配置"""
    return {
        "BASE_ENV": os.environ.get("BASE_ENV", ""),
        "SENSITIVE_ENV": os.environ.get("SENSITIVE_ENV", ""),
    }
```

## 返回格式规范

### 正常返回

返回 dict，FastMCP 框架会自动包装为 MCP 标准格式：

```python
return {"result": 42}
```

### 错误返回

**不要 throw 异常**，而是返回 `isError: True`：

```python
from mcp.types import TextContent

if invalid_input:
    return {
        "content": [TextContent(type="text", text="清晰描述错误原因")],
        "isError": True,
    }
```

LLM 会根据 `isError` 判断工具调用失败，并决定是否重试或告知用户。错误信息应当清晰描述失败原因，帮助 LLM 决定下一步行为。

### try/except 模式

```python
@server.tool()
async def my_tool(data: str) -> Dict[str, Any]:
    """工具描述

    Args:
         输入数据
    """
    try:
        result = process(data)
        return {"result": result}
    except Exception as e:
        return {
            "content": [TextContent(type="text", text=str(e))],
            "isError": True,
        }
```

## 环境变量

平台通过环境变量注入配置，工具内通过 `os.environ` 获取：

| 变量名 | 用途 | 示例 |
|--------|------|------|
| `BASE_ENV` | 基础配置（环境标识、服务地址等） | `{"env":"prod","apiBase":"https://..."}` |
| `SENSITIVE_ENV` | 敏感凭证（API Key、Secret 等） | `{"apiKey":"sk-xxx"}` |

读取时始终提供默认值：

```python
import os

api_key = os.environ.get("SENSITIVE_ENV", "")
```

## 文件结构

```
McpServerTemplate/
├── pyproject.toml                          # 项目配置和依赖
├── MCP_DEVELOPMENT_GUIDE.md                # 开发指南（本文件）
└── src/McpServerTemplate/
    ├── __init__.py                          # 入口，启动 MCP Server
    └── open_platform_server.py             # MCP 工具定义（本文件）
```

## 外部 API 调用

模板已内置 `httpx` 依赖，支持调用外部 HTTP API。

### 基本模式

```python
import httpx
import json
from typing import Annotated, Any, Dict, Optional
from pydantic import Field

@server.tool()
async def fetch_external_data(
    resource: Annotated[str, Field(description="资源类型")] = "posts",
    resource_id: Annotated[Optional[str], Field(description="资源ID，为空则获取列表")] = None,
) -> Dict[str, Any]:
    """调用外部API获取数据"""
    url = f"https://api.example.com/{resource}"
    if resource_id is not None and resource_id.strip() != "":
        url += f"/{resource_id}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        return {
            "content": [TextContent(type="text", text=json.dumps({
                "url": url,
                "status_code": resp.status_code,
                "data": data,
            }, ensure_ascii=False))],
        }
    except httpx.HTTPStatusError as e:
        return {
            "content": [TextContent(type="text", text=f"HTTP错误: {e.response.status_code} - {e.response.text}")],
            "isError": True,
        }
    except httpx.RequestError as e:
        return {
            "content": [TextContent(type="text", text=f"请求失败: {str(e)}")],
            "isError": True,
        }
```

### 要点

1. **使用 `httpx.AsyncClient`**：MCP Server 是异步框架，必须用异步 HTTP 客户端，不要用同步的 `requests`
2. **设置超时**：必须设置 `timeout`，避免请求挂死导致工具超时无响应
3. **异常处理**：区分 `HTTPStatusError`（服务端返回错误状态码）和 `RequestError`（网络连接失败等），分别返回有意义的错误信息
4. **返回格式**：外部 API 的响应数据应通过 `json.dumps` 序列化后放入 `TextContent` 返回，不要直接返回 dict
5. **认证**：如需 API Key，从环境变量读取：
   ```python
   api_key = os.environ.get("SENSITIVE_ENV", "")
   headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
   resp = await client.get(url, headers=headers)
   ```
6. **参数类型注意**：平台可能将整数参数作为字符串传入，对于可选的整数 ID 参数，建议用 `Optional[str]` 接收后手动转换，避免 Pydantic 校验报错

## 依赖版本约束（重要：避免 ABI 不兼容）

托管平台运行时 **Python = 3.10**。带 C / Rust extension 的依赖**必须在 `pyproject.toml` 里 pin 上限版本**，否则 pip 会拉到最新版，新版的 binary wheel 可能编译时用了 3.11+ 才引入的 C API，运行时在 3.10 上就会缺符号，工具一调用就崩。

### 典型报错

```
/tmp/hosted_mcp/pip_packages/<pkg>/.../_xxx.abi3.so:
undefined symbol: PyType_GetName
```

`PyType_GetName` 是 CPython 3.11 才有的 API。看到这类 `undefined symbol: PyType_<XxxNew>` 报错，几乎都是"包没 pin、装到了 3.11+ 才能跑的版本"。

### 已知需要 pin 上限的常见依赖

| 包 | 安全 pin 范围（Python 3.10） | 出问题的版本 |
|----|------------------------------|--------------|
| `cryptography` | `>=42.0.0,<44.0.0` | `>=44.0.0`（用了 PyType_GetName） |
| `pydantic-core` | 由 `pydantic>=2.0.0` 间接带入，通常无需手动 pin | — |
| `orjson` / `uvloop` / `grpcio` 等其他 Rust/C 扩展包 | 同理需要留意 | — |

### pyproject.toml 写法

```toml
dependencies = [
    "mcp>=1.27.0",
    "pydantic>=2.0.0",
    "httpx>=0.27.0",
    # ⚠️ native 包必须 pin 上限
    "cryptography>=42.0.0,<44.0.0",
]
```

### 排查路径

1. 看到 `undefined symbol: PyType_<XxxNew>` 报错，**不要怀疑业务代码**，先去 `pyproject.toml` 看相关 native 依赖有没有上限
2. 没上限就加上限，重新打包托管
3. 业务侧用到的常用 API（如 `cryptography` 的 `load_pem_public_key` / `PKCS1v15`）在新旧版本里都稳定存在，**降版本不会影响业务代码**

## 多文件拆分的导入规范

当工具数量增多需要拆分为多个文件时，**必须使用同级目录直接导入**，不能使用包名绝对导入或相对导入。

### 平台加载机制

托管平台通过 `import_module_by_path` 直接加载 `open_platform_server.py`，并将服务目录（如 `/tmp/hosted_mcp/src/YourProject/`）加入 `sys.path`，而非其父目录。因此：

- ❌ **不要使用包名绝对导入**：`from YourProject.xxx import ...`（平台找不到 `YourProject` 这个包）
- ❌ **不要使用相对导入**：`from .xxx import ...`（文件不是作为包的一部分加载的）
- ✅ **使用同级目录直接导入**：`from xxx import ...`（文件在同一目录下，直接按模块名导入）

```python
# ❌ 错误 - 平台上会报 No module named 'YourProject'
from YourProject.hotel_config import configure_from_env

# ❌ 错误 - 平台上会报 attempted relative import with no known parent package
from .hotel_config import configure_from_env

# ✅ 正确 - 同级目录直接导入
from hotel_config import configure_from_env
```

`__init__.py` 中的 `from YourProject.open_platform_server import server as mcp` 是本地开发用的，平台不会加载 `__init__.py`，所以不影响部署。但 `open_platform_server.py` 及其依赖链中的**所有文件**必须使用同级目录直接导入。

### 多文件示例

```
src/YourProject/
├── __init__.py                  # 本地开发入口，平台不加载
├── open_platform_server.py      # 平台加载入口，定义 server 和 @server.tool()
├── hotel_config.py              # 业务配置
└── hotel_query_service.py       # 业务逻辑
```

```python
# open_platform_server.py ✅
from hotel_config import configure_from_env
from hotel_query_service import query_hotels_by_city

# hotel_query_service.py ✅
import hotel_config as config
```

## 命名约定

| 元素 | 约定 | 示例 |
|------|------|------|
| 工具函数名 | 动词或动词短语 | `add`, `batch_calculate`, `get_env_configs` |
| 工具 docstring | 简洁的功能描述 | `"""对两个数进行加法运算"""` |
| 参数描述 | 使用 `Annotated[type, Field(description=...)]` | `Annotated[str, Field(description="搜索关键词")]` |
| 参数约束 | 使用 `Field` 的约束参数 | `Field(ge=0, le=150, description="年龄")` |