"""测试仓库的 pytest 配置和共享 fixture。

提供通用的测试工具和 fixture，供各个子模块测试使用。
"""

from pathlib import Path

import pytest

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_REPOS_PATH = PROJECT_ROOT / "test_repos"


def get_test_repo_path(repo_name: str) -> Path:
    """获取指定测试仓库的路径。

    Args:
        repo_name: 仓库名称（例如 "ACE-Step"）

    Returns:
        仓库的完整路径
    """
    return TEST_REPOS_PATH / repo_name


def skip_if_submodule_not_initialized(repo_path: Path) -> pytest.MarkDecorator:
    """如果子模块未初始化则跳过测试。

    Args:
        repo_path: 子模块的路径

    Returns:
        pytest.skipif 装饰器
    """
    return pytest.mark.skipif(
        not repo_path.exists(),
        reason=f"Submodule not initialized. Run: git submodule update --init --recursive",
    )


@pytest.fixture
def test_repos_path() -> Path:
    """返回 test_repos 目录的路径。"""
    return TEST_REPOS_PATH

