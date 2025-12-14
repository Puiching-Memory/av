# av
基于 uv 构建的Agent-powered Python 环境管理器 — 您的智能依赖守护者。

> ⚠️ **警告**：当前项目处于早期开发状态，尚未准备好用于生产环境。功能可能不完整、不稳定或可能发生破坏性变更。

[English](README.md) | 中文

## 功能说明
- `av venv`: 创建虚拟环境（默认：`.venv`），扫描当前项目，提出依赖建议（动态检测 + 如果设置了 `OPENAI_API_KEY` 则使用 LangChain），然后使用 `uv pip install ...` 将依赖安装到虚拟环境中。
- 作为 Python 包发布，可通过 PyInstaller 打包成单个二进制文件。

## 依赖检测机制

`av` 使用基于 LangChain 1.x 的 AI agent 智能分析项目并提出依赖建议：

1. **基于 Agent 的分析**：当设置了 `OPENAI_API_KEY` 时，AI agent 会自主使用多种工具探索项目：
   - **Bash 命令**：执行命令来探索项目结构、读取配置文件、搜索导入语句
   - **PyPI 集成**：搜索 PyPI、验证包名、获取包信息和依赖关系

2. **自主发现**：Agent 自主决定需要探索的内容：
   - 读取依赖配置文件（`pyproject.toml`、`requirements.txt`、`setup.py`）
   - 搜索代码中的导入语句
   - 检查项目结构和文档
   - 在 PyPI 上验证包名
   - 获取包元数据和依赖关系

3. **结构化输出**：使用 LangChain 1.x 的结构化输出生成依赖计划，包括：
   - 推荐的包列表（使用正确的 PyPI 包名）
   - 说明依赖选择理由的注释

4. **无预提取**：与传统方法不同，`av` 不会预提取代码或使用 RAG。Agent 根据需要动态使用工具发现信息。

## 环境要求

- **Python**: >=3.10（运行时），推荐 3.13 用于开发
- **uv**: 最新版本，从 [astral-sh/uv](https://github.com/astral-sh/uv) 安装

## 快速开始
1) 安装 [uv](https://github.com/astral-sh/uv) 并确保它在 `PATH` 中。
2) 使用 Python 3.10+ 创建环境并安装依赖：`uv venv --python 3.10 && uv pip install -e .[dev]`（或使用 Python 3.13 用于开发）。
3) 创建虚拟环境并安装依赖：`uv run av venv`（默认不需要任何参数）。
4) 运行预览计划：`uv run av venv --dry-run`。
5) 自动安装（跳过确认）：`uv run av venv -y`。

可选：设置 `OPENAI_API_KEY` 以启用基于 LangChain 1.x 工具调用的 AI 驱动依赖分析。

## 二进制构建

### 自动构建

项目配置了 GitHub Actions 自动构建工作流：

- **构建工作流** (`build.yml`): 
  - 在推送到 `main`/`master` 分支或创建 PR 时自动触发
  - 支持 Windows、Linux、macOS 三个平台
  - 构建产物作为 artifacts 保存 30 天

- **发布工作流** (`release.yml`):
  - 在创建 `v*` 标签时自动触发（如 `v1.0.0`）
  - 在所有平台构建二进制文件
  - 自动创建 GitHub Release 并上传所有平台的构建产物

#### 使用方式

1. **查看构建结果**: 在 GitHub 仓库的 "Actions" 标签页查看构建状态
2. **下载构建产物**: 在 Actions 运行完成后，点击对应的运行，在 "Artifacts" 部分下载
3. **创建发布**: 推送一个版本标签即可自动创建发布：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

## 测试仓库

项目包含一个 `test_repos` 文件夹，通过 git submodule 维护多个第三方 Python 库，用于测试环境配置 agent 的性能。

### 初始化 submodule

```bash
git submodule update --init --recursive
```

### 测试 agent 性能

在任意测试库目录中运行：

```bash
cd test_repos/<library_name>
av venv            # 创建虚拟环境并安装依赖
av venv --dry-run  # 查看依赖分析计划（不实际安装）
av venv -y         # 自动安装依赖（跳过确认）
```

更多信息请查看 [test_repos/README.md](test_repos/README.md)。

## 项目结构
- CLI 入口：[src/av/cli.py](src/av/cli.py)
- AI agent 工具调用：[src/av/agent.py](src/av/agent.py)
- PyPI 爬虫：[src/av/pypi_crawler.py](src/av/pypi_crawler.py)

