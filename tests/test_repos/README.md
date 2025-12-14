# 测试仓库子模块测试套件

此目录包含针对 `test_repos` 下各个子模块的独立测试脚本。

## 目录结构

```
tests/test_repos/
├── __init__.py          # 包初始化文件
├── conftest.py          # pytest 配置和共享 fixture
├── test_ace_step.py     # ACE-Step 子模块的测试
└── README.md            # 本文件
```

## 现有测试

### ACE-Step

测试文件：`test_ace_step.py`

测试内容：
- 项目路径验证

## 添加新子模块的测试

当 `test_repos` 目录下添加新的子模块时，请按照以下步骤创建对应的测试文件：

### 1. 创建测试文件

在 `tests/test_repos/` 目录下创建 `test_<模块名>.py` 文件。

例如，如果添加了 `example-lib` 子模块，创建 `test_example_lib.py`：

```python
"""Example-Lib 子模块的测试脚本。

测试针对 Example-Lib 项目的依赖分析和项目扫描功能。
"""

from pathlib import Path

import pytest

from tests.test_repos.conftest import get_test_repo_path, skip_if_submodule_not_initialized

# 获取项目路径
EXAMPLE_LIB_PATH = get_test_repo_path("example-lib")


@pytest.fixture
def example_lib_path() -> Path:
    """返回 Example-Lib 项目的路径。"""
    return EXAMPLE_LIB_PATH


@skip_if_submodule_not_initialized(EXAMPLE_LIB_PATH)
class TestExampleLib:
    """Example-Lib 项目的测试类。"""

    def test_example_lib_path_exists(self, example_lib_path: Path) -> None:
        """验证项目路径存在。"""
        assert example_lib_path.exists()
        assert example_lib_path.is_dir()

    # 添加更多测试方法...
```

### 2. 使用共享工具

使用 `conftest.py` 中提供的工具函数：

- `get_test_repo_path(repo_name)`: 获取子模块路径
- `skip_if_submodule_not_initialized(repo_path)`: 如果子模块未初始化则跳过测试

### 3. 测试命名规范

- 测试文件：`test_<模块名>.py`（使用下划线分隔）
- 测试类：`Test<模块名>`（使用驼峰命名）
- 测试方法：`test_<功能描述>`

### 4. 运行测试

运行特定子模块的测试：

```bash
pytest tests/test_repos/test_ace_step.py -v
```

运行所有子模块测试：

```bash
pytest tests/test_repos/ -v
```

## 注意事项

1. **子模块初始化**：测试会自动跳过未初始化的子模块。初始化子模块：
   ```bash
   git submodule update --init --recursive
   ```

2. **测试稳定性**：测试应该能够处理子模块中可能缺失的文件（如 pyproject.toml），不应因为文件不存在而失败。

3. **特定断言**：根据每个子模块的特点，添加针对性的断言来验证依赖检测的正确性。

4. **文档更新**：添加新测试后，请更新本 README 文件，在"现有测试"部分添加新子模块的说明。

