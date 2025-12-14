from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Tuple

from pydantic import BaseModel, Field

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from av.pypi_crawler import PyPICrawler


SYSTEM_PROMPT = """你是一个 Python 依赖规划器。根据项目信息，提出一个简洁的 pip 包安装列表。分析项目结构和现有依赖，推荐最合适的包。

你可以使用以下工具：

1. `run_bash_command` - 在项目目录中执行 bash 命令来探索项目：
   - 查看项目结构（ls, find, tree 等）
   - 读取配置文件（cat, head, tail 等）
   - 搜索代码中的导入（grep, find 等）
   - 查看 README 或其他文档

2. `search_pypi_packages` - 在 PyPI 上搜索包，用于查找可能的包名

3. `get_package_info` - 获取 PyPI 包的详细信息，包括版本、依赖、描述等

4. `verify_package_name` - 验证包名是否在 PyPI 上存在，确保使用正确的包名

5. `get_package_dependencies` - 获取包的依赖列表，用于分析依赖关系

根据你的分析需要，可以多次调用这些工具来检索不同方面的信息，比如：
- 依赖配置文件（requirements.txt, pyproject.toml, setup.py）
- 导入语句和使用的库
- 项目结构和主要功能模块
- 验证和查找正确的 PyPI 包名

使用工具检索到相关信息后，综合分析并提出最佳的依赖计划。"""


class DependencyPlan(BaseModel):
    """依赖规划的结构化输出。"""

    deps: List[str] = Field(
        description="要安装的 pip 包名称列表。使用在 PyPI 上出现的确切包名。"
    )
    notes: str = Field(
        description="对依赖选择的简要说明以及任何重要的注意事项。"
    )


def refine_plan_with_langchain(
    base_path: Path, pypi_crawler: PyPICrawler
) -> Tuple[List[str], str]:
    """使用 LangChain 1.x 的结构化输出和工具调用生成安装计划。"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [], "错误：未设置 OPENAI_API_KEY。请设置它以使用依赖规划器。"

    # 定义 bash 工具函数
    def run_bash_command(command: str) -> str:
        """
        在项目目录中执行 bash 命令来探索项目。
        
        Args:
            command: 要执行的 bash 命令，例如：
                   - "ls -la" - 查看目录内容
                   - "cat pyproject.toml" - 读取配置文件
                   - "find . -name '*.py' | head -20" - 查找 Python 文件
                   - "grep -r '^import\\|^from' --include='*.py' . | head -50" - 搜索导入语句
                   - "cat README.md" - 读取 README
        
        Returns:
            命令的输出结果
        """
        try:
            # 在项目目录中执行命令
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(base_path),
                capture_output=True,
                text=True,
                timeout=30,  # 30 秒超时
            )
            
            if result.returncode != 0:
                return f"命令执行失败（退出码 {result.returncode}）：\n{result.stderr}"
            
            output = result.stdout.strip()
            if not output:
                return "命令执行成功，但无输出。"
            
            # 限制输出长度，避免 token 过多
            max_length = 10000
            if len(output) > max_length:
                return output[:max_length] + f"\n[... 输出已截断，共 {len(output)} 字符 ...]"
            
            return output
        except subprocess.TimeoutExpired:
            return "命令执行超时（超过 30 秒）。"
        except Exception as e:
            return f"执行命令时出错：{str(e)}"
    
    # 创建 bash 工具
    bash_tool = StructuredTool.from_function(
        func=run_bash_command,
        name="run_bash_command",
        description="在项目目录中执行 bash 命令来探索项目。可以用于查看文件、搜索代码、读取配置等。",
    )
    
    # 创建 PyPI 工具函数
    def search_pypi_packages(query: str, limit: int = 10) -> str:
        """
        在 PyPI 上搜索包。
        
        Args:
            query: 搜索关键词，例如 "requests", "numpy", "web framework" 等
            limit: 返回结果数量限制，默认 10
        
        Returns:
            搜索结果，包含包名、版本和描述
        """
        try:
            results = pypi_crawler.search_packages(query, limit=limit)
            if not results:
                return f"未找到与 '{query}' 相关的包。"
            
            output_parts = [f"找到 {len(results)} 个相关包：\n"]
            for i, result in enumerate(results, 1):
                output_parts.append(
                    f"{i}. {result.name} (版本: {result.version})"
                )
                if result.summary:
                    output_parts.append(f"   描述: {result.summary}")
                output_parts.append("")
            
            return "\n".join(output_parts)
        except Exception as e:
            return f"搜索 PyPI 时出错：{str(e)}"
    
    def get_package_info_tool(package_name: str, version: str | None = None) -> str:
        """
        获取 PyPI 包的详细信息。
        
        Args:
            package_name: 包名称
            version: 版本号（可选），如果不提供则返回最新版本
        
        Returns:
            包的详细信息，包括版本、依赖、描述、作者等
        """
        try:
            info = pypi_crawler.get_package_info(package_name, version)
            if info is None:
                return f"包 '{package_name}' 在 PyPI 上不存在。"
            
            output_parts = [
                f"包名: {info.name}",
                f"版本: {info.version}",
            ]
            
            if info.summary:
                output_parts.append(f"摘要: {info.summary}")
            
            if info.description:
                desc = info.description[:500]  # 限制描述长度
                output_parts.append(f"描述: {desc}{'...' if len(info.description) > 500 else ''}")
            
            if info.author:
                output_parts.append(f"作者: {info.author}")
            
            if info.license:
                output_parts.append(f"许可证: {info.license}")
            
            if info.requires_python:
                output_parts.append(f"Python 要求: {info.requires_python}")
            
            if info.dependencies:
                deps_str = ", ".join(info.dependencies[:10])  # 只显示前 10 个依赖
                output_parts.append(f"依赖: {deps_str}")
                if len(info.dependencies) > 10:
                    output_parts.append(f"  ... 还有 {len(info.dependencies) - 10} 个依赖")
            
            if info.homepage_url:
                output_parts.append(f"主页: {info.homepage_url}")
            
            return "\n".join(output_parts)
        except Exception as e:
            return f"获取包信息时出错：{str(e)}"
    
    def verify_package_name_tool(package_name: str) -> str:
        """
        验证包名是否在 PyPI 上存在。
        
        Args:
            package_name: 要验证的包名称
        
        Returns:
            验证结果，如果存在则返回包的基本信息
        """
        try:
            exists = pypi_crawler.verify_package_name(package_name)
            if exists:
                # 获取包的基本信息
                info = pypi_crawler.get_package_info(package_name)
                if info:
                    return f"包 '{package_name}' 存在于 PyPI 上。\n最新版本: {info.version}\n摘要: {info.summary or '无'}"
                return f"包 '{package_name}' 存在于 PyPI 上。"
            else:
                return f"包 '{package_name}' 在 PyPI 上不存在。请检查包名是否正确，或使用 search_pypi_packages 搜索。"
        except Exception as e:
            return f"验证包名时出错：{str(e)}"
    
    def get_package_dependencies_tool(package_name: str, version: str | None = None) -> str:
        """
        获取包的依赖列表。
        
        Args:
            package_name: 包名称
            version: 版本号（可选），如果不提供则返回最新版本的依赖
        
        Returns:
            依赖列表
        """
        try:
            deps = pypi_crawler.get_package_dependencies(package_name, version)
            if deps is None:
                return f"无法获取包 '{package_name}' 的依赖信息（包可能不存在）。"
            
            if not deps:
                return f"包 '{package_name}' 没有依赖。"
            
            return f"包 '{package_name}' 的依赖（共 {len(deps)} 个）：\n" + "\n".join(f"  - {dep}" for dep in deps[:20]) + (f"\n  ... 还有 {len(deps) - 20} 个依赖" if len(deps) > 20 else "")
        except Exception as e:
            return f"获取包依赖时出错：{str(e)}"
    
    # 创建 PyPI 工具
    search_tool = StructuredTool.from_function(
        func=search_pypi_packages,
        name="search_pypi_packages",
        description="在 PyPI 上搜索包。用于查找可能的包名或搜索相关功能的包。",
    )
    
    get_info_tool = StructuredTool.from_function(
        func=get_package_info_tool,
        name="get_package_info",
        description="获取 PyPI 包的详细信息，包括版本、依赖、描述、作者等。用于验证包的存在和了解包的详细信息。",
    )
    
    verify_tool = StructuredTool.from_function(
        func=verify_package_name_tool,
        name="verify_package_name",
        description="验证包名是否在 PyPI 上存在。用于确保使用的包名正确。",
    )
    
    get_deps_tool = StructuredTool.from_function(
        func=get_package_dependencies_tool,
        name="get_package_dependencies",
        description="获取包的依赖列表。用于分析包的依赖关系。",
    )
    
    # 创建 LLM 实例并绑定所有工具
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_with_tools = llm.bind_tools([bash_tool, search_tool, get_info_tool, verify_tool, get_deps_tool])
    
    # 创建提示模板
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "user",
                "请分析这个项目并提出最佳的依赖计划。你可以使用 run_bash_command 工具来探索项目，使用 PyPI 相关工具来验证和查找包信息。",
            ),
        ]
    )
    
    # 执行多轮对话，让 LLM 可以多次调用工具
    messages = prompt.format_messages()
    max_iterations = 10  # 最多执行 10 轮工具调用
    iteration = 0
    
    try:
        while iteration < max_iterations:
            iteration += 1
            
            # 调用 LLM（带工具）
            response = llm_with_tools.invoke(messages)
            
            # 添加到消息历史
            messages.append(response)
            
            # 检查是否有工具调用
            if hasattr(response, "tool_calls") and response.tool_calls:
                # 执行工具调用
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    if tool_name == "run_bash_command":
                        result = run_bash_command(**tool_args)
                    elif tool_name == "search_pypi_packages":
                        result = search_pypi_packages(**tool_args)
                    elif tool_name == "get_package_info":
                        result = get_package_info_tool(**tool_args)
                    elif tool_name == "verify_package_name":
                        result = verify_package_name_tool(**tool_args)
                    elif tool_name == "get_package_dependencies":
                        result = get_package_dependencies_tool(**tool_args)
                    else:
                        result = f"未知工具: {tool_name}"
                    
                    # 添加工具结果到消息历史
                    messages.append(
                        ToolMessage(
                            content=result,
                            tool_call_id=tool_call["id"],
                        )
                    )
                
                # 继续对话，让 LLM 处理工具结果
                continue
            else:
                # 没有工具调用，LLM 已经给出最终答案
                break
        
        # 添加最终请求，要求生成依赖计划
        from langchain_core.messages import HumanMessage
        messages.append(
            HumanMessage(
                content="基于你通过工具探索到的项目信息，请提供最终的依赖计划。"
            )
        )
        
        # 使用结构化输出 LLM 处理整个对话历史
        structured_llm = llm.with_structured_output(DependencyPlan)
        result: DependencyPlan = structured_llm.invoke(messages)
    except Exception as exc:  # pragma: no cover - 防御性处理 API 失败
        return [], f"LangChain 失败：{exc}"

    if not result.deps or not isinstance(result.deps, list):
        return [], "LangChain 未返回依赖项"

    return [str(dep) for dep in result.deps], result.notes or "已应用 LangChain 计划"
