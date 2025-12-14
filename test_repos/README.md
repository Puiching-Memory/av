# 测试仓库集合

此文件夹包含用于测试 `av` 环境配置 agent 性能的第三方 Python 库。

这些库通过 git submodule 维护，涵盖了不同复杂度和类型的 Python 项目，用于评估 agent 在以下场景下的表现：

- 简单库的依赖检测
- 复杂科学计算库的依赖分析
- Web 框架的依赖配置
- 机器学习库的版本兼容性处理
- 多依赖项目的智能解析

## 包含的测试库

- ACE-Step # 该项目存在经典的环境配置版本不明确问题，随着未来更新现在出现了API miss 错误

## 使用方法

### 初始化所有 submodule

```bash
git submodule update --init --recursive
```

### 添加新的测试库

```bash
git submodule add <repository_url> test_repos/<library_name>
```

### 更新所有 submodule

```bash
git submodule update --remote
```

### 测试 agent 性能

在任意测试库目录中运行：

```bash
cd test_repos/<library_name>
av venv            # 创建虚拟环境并安装依赖（默认不需要参数）
av venv --dry-run  # 查看依赖分析计划（不实际安装）
av venv -y         # 自动安装依赖（跳过确认）
```

## 维护说明

- 定期更新 submodule 以获取最新版本
- 添加新库时，确保选择有代表性的项目
- 记录每个库的测试结果，用于性能基准测试

