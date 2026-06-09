from McpServerTemplate.core import engine
import os
import json
from typing import Annotated, Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, field_validator
from mcp.server import FastMCP
from mcp.server.fastmcp.server import Context
from mcp.types import TextContent

server = FastMCP("utility-tools")


# ==================== Pydantic 数据校验工具（最简示例） ====================

class UserInfo(BaseModel):
    """用户信息模型 - 演示 Pydantic 的数据校验能力"""
    name: str = Field(..., min_length=1, max_length=50, description="用户名")
    age: int = Field(..., ge=0, le=150, description="年龄")
    email: str = Field(..., description="邮箱地址")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('邮箱格式不正确')
        return v


@server.tool()
async def validate_user_data(
    name: Annotated[str, Field(description="用户名（长度1-50）")],
    age: Annotated[int, Field(ge=0, le=150, description="年龄（0-150）")],
    email: Annotated[str, Field(description="邮箱地址")],
) -> Dict[str, Any]:
    """使用 Pydantic 校验用户数据 - 演示入参校验和错误返回"""
    try:
        user = UserInfo(name=name, age=age, email=email)
        return {
            "data": user.model_dump(),
            "json": user.model_dump_json(),
        }
    except Exception as e:
        return {
            "content": [TextContent(type="text", text=str(e))],
            "isError": True,
        }


# ==================== 出参 Schema 验证工具（BaseModel 返回类型） ====================

class ValidateUserDataV2Output(BaseModel):
    """validate_user_data_v2 的出参模型"""
    name: str = Field(description="用户名")
    age: int = Field(description="年龄")
    email: str = Field(description="邮箱地址")


@server.tool()
async def validate_user_data_v2(
    name: Annotated[str, Field(min_length=1, max_length=50, description="用户名（长度1-50）")],
    age: Annotated[int, Field(ge=0, le=150, description="年龄（0-150）")],
    email: Annotated[str, Field(description="邮箱地址")],
) -> ValidateUserDataV2Output:
    """使用 Pydantic 校验用户数据 V2 - 演示带 outputSchema 的版本"""
    user = UserInfo(name=name, age=age, email=email)
    return ValidateUserDataV2Output(
        name=user.name,
        age=user.age,
        email=user.email,
    )


# ==================== 环境变量调试工具 ====================

@server.tool()
async def get_env_configs() -> Dict[str, str]:
    """获取平台注入的环境变量配置（调试用）"""
    return {
        "BASE_ENV": os.environ.get("BASE_ENV", ""),
        "SENSITIVE_ENV": os.environ.get("SENSITIVE_ENV", ""),
    }


# ==================== 复杂嵌套参数工具 ====================

class Credentials(BaseModel):
    """认证凭证"""
    username: str = Field(description="用户名")
    password: Optional[str] = Field(default=None, description="密码，敏感信息可选")
    auth_type: str = Field(description="认证方式，可选: basic, oauth, apikey")


class DataSourceConfig(BaseModel):
    """数据源连接配置"""
    host: str = Field(description="数据源主机地址")
    port: int = Field(ge=1, le=65535, description="端口号")
    credentials: Credentials = Field(description="认证凭证")
    options: Optional[Dict[str, Any]] = Field(default=None, description="额外连接选项，键值对形式")


class DataSource(BaseModel):
    """数据源"""
    type: str = Field(description="数据源类型，可选: database, api, file")
    config: DataSourceConfig = Field(description="数据源连接配置")


class TransformStep(BaseModel):
    """数据转换步骤"""
    name: str = Field(description="转换步骤名称")
    type: str = Field(description="转换类型，可选: filter, map, aggregate, sort")
    params: Optional[Dict[str, Any]] = Field(default=None, description="转换参数，键值对形式")


class RetryPolicy(BaseModel):
    """重试策略"""
    max_attempts: int = Field(ge=1, le=10, description="最大重试次数")
    backoff_seconds: float = Field(ge=0, description="重试间隔秒数")
    retry_on_errors: Optional[List[str]] = Field(default=None, description="需要重试的错误类型列表")


class ScheduleConfig(BaseModel):
    """调度配置"""
    frequency: str = Field(description="调度频率，可选: hourly, daily, weekly, monthly")
    time: str = Field(description="执行时间，格式 HH:mm")
    retry_policy: Optional[RetryPolicy] = Field(default=None, description="重试策略，不传则不重试")


class AnalyzeDataPipelineInput(BaseModel):
    """数据管道分析入参"""
    name: str = Field(description="数据管道名称")
    source: DataSource = Field(description="数据源配置")
    transform_steps: List[TransformStep] = Field(description="数据转换步骤列表，至少一个步骤")
    schedule: ScheduleConfig = Field(description="调度配置")
    enabled: Optional[bool] = Field(default=True, description="是否启用")
    tags: Optional[List[str]] = Field(default=None, description="标签列表")


@server.tool()
async def analyze_data_pipeline(pipeline: AnalyzeDataPipelineInput) -> Dict[str, Any]:
    """分析数据管道配置，校验数据源、转换步骤和调度策略的完整性

    测试复杂嵌套入参的解析能力，包含多层嵌套对象、对象数组、可选字段、枚举等结构。
    """
    try:
        issues = []

        # 校验数据源
        if pipeline.source.type == "database" and pipeline.source.config.port == 0:
            issues.append("database 类型数据源 port 不能为 0")
        if pipeline.source.config.credentials.auth_type == "basic" and not pipeline.source.config.credentials.password:
            issues.append("basic 认证需要提供 password")

        # 校验转换步骤
        step_names = [s.name for s in pipeline.transform_steps] if pipeline.transform_steps else []
        if len(step_names) != len(set(step_names)):
            issues.append("转换步骤名称不能重复")

        # 校验调度
        if pipeline.schedule.retry_policy:
            if pipeline.schedule.retry_policy.max_attempts > 5 and pipeline.schedule.frequency == "hourly":
                issues.append("每小时调度不建议重试超过 5 次")

        return {
            "pipeline": pipeline.name,
            "source_type": pipeline.source.type,
            "source_host": pipeline.source.config.host,
            "step_count": len(pipeline.transform_steps) if pipeline.transform_steps else 0,
            "schedule_frequency": pipeline.schedule.frequency,
            "enabled": pipeline.enabled,
            "tags": pipeline.tags or [],
            "issues": issues,
            "valid": len(issues) == 0,
        }
    except Exception as e:
        return {
            "content": [TextContent(type="text", text=f"管道分析错误: {str(e)}")],
            "isError": True,
        }


# ==================== 请求 Header 读取工具 ====================

@server.tool()
async def get_request_headers(ctx: Context) -> Dict[str, Any]:
    """获取当前 MCP 请求的 HTTP Header 信息

    通过 Context 访问底层 Starlette Request 对象，读取请求头。
    仅在 HTTP 传输模式（SSE/StreamableHTTP）下有效，stdio 模式下返回空。
    """
    request = ctx.request_context.request
    if request is None:
        return {
            "transport": "stdio",
            "note": "当前为 stdio 传输模式，无 HTTP 请求对象",
        }

    headers = dict(request.headers)

    # HTTP header 大小写不敏感，尝试多种格式获取
    def get_header(key: str) -> Optional[str]:
        lower_key = key.lower()
        upper_key = key.upper()
        return headers.get(lower_key) or headers.get(upper_key) or headers.get(key)

    trace_id = get_header('X-Trace-Id')
    tenant_id = get_header('X-Tenant-Id')

    return {
        "transport": "http",
        "x_trace_id": trace_id,
        "x_tenant_id": tenant_id,
    }


# ==================== 外部 API 调用工具 ====================

@server.tool()
async def fetch_jsonplaceholder(
    resource: Annotated[str, Field(description="资源类型，可选值: posts, comments, albums, photos, todos, users")] = "posts",
    resource_id: Annotated[Optional[str], Field(description="资源ID，为空则获取列表，指定则获取单条")] = None,
) -> Dict[str, Any]:
    """调用 JSONPlaceholder 公共 API 获取模拟数据"""
    # 平台可能传空字符串，需要手动处理
    if resource_id is not None and resource_id.strip() != "":
        rid = int(resource_id)
    else:
        rid = None

    allowed_resources = {"posts", "comments", "albums", "photos", "todos", "users"}
    if resource not in allowed_resources:
        return {
            "content": [TextContent(
                type="text",
                text=f"不支持的资源类型: {resource}，可选值: {', '.join(sorted(allowed_resources))}"
            )],
            "isError": True,
        }

    url = f"https://jsonplaceholder.typicode.com/{resource}"
    if rid is not None:
        url += f"/{rid}"

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
from .utils import helper
