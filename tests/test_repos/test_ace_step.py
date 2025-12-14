"""ACE-Step 子模块的测试脚本。

测试针对 ACE-Step 项目的依赖分析和项目扫描功能。
ACE-Step 是一个音乐生成基础模型项目，包含复杂的依赖关系。
"""

from pathlib import Path

import pytest

from tests.test_repos.conftest import get_test_repo_path, skip_if_submodule_not_initialized

# 获取 ACE-Step 项目路径
ACE_STEP_PATH = get_test_repo_path("ACE-Step")


@pytest.fixture
def ace_step_path() -> Path:
    """返回 ACE-Step 项目的路径。"""
    return ACE_STEP_PATH


@skip_if_submodule_not_initialized(ACE_STEP_PATH)
class TestACEStep:
    """ACE-Step 项目的测试类。"""

    def test_ace_step_path_exists(self, ace_step_path: Path) -> None:
        """验证 ACE-Step 路径存在。"""
        assert ace_step_path.exists(), f"ACE-Step path does not exist: {ace_step_path}"
        assert ace_step_path.is_dir()


