from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class PackageInfo:
    """PyPI 包信息数据类"""

    name: str
    version: str
    summary: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    homepage_url: Optional[str] = None
    project_url: Optional[str] = None
    requires_python: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> PackageInfo:
        """
        从 PyPI JSON API 响应创建 PackageInfo
        
        Args:
            data: PyPI JSON API 响应数据，可以包含 releases 键（项目级别）
                  或者 urls 键（版本级别）
        """
        info = data.get("info", {})
        releases = data.get("releases", {})
        
        # 获取版本号
        # 如果存在 releases，使用其中的最新版本
        # 否则使用 info 中的 version（通常是从特定版本 API 获取的）
        if releases:
            versions = sorted(releases.keys(), reverse=True)
            version = versions[0] if versions else info.get("version", "")
        else:
            version = info.get("version", "")
        
        # 提取依赖信息
        requires_dist = info.get("requires_dist", [])
        dependencies = list(requires_dist) if requires_dist else []
        
        # 提取项目 URL
        project_urls = info.get("project_urls", {}) or {}
        homepage_url = project_urls.get("Homepage") or info.get("home_page")
        
        return cls(
            name=info.get("name", ""),
            version=version,
            summary=info.get("summary"),
            description=info.get("description"),
            author=info.get("author"),
            license=info.get("license"),
            homepage_url=homepage_url,
            project_url=info.get("project_url") or f"https://pypi.org/project/{info.get('name', '')}/",
            requires_python=info.get("requires_python"),
            dependencies=dependencies,
        )


@dataclass
class SearchResult:
    """PyPI 搜索结果数据类"""

    name: str
    version: str
    summary: Optional[str] = None
    score: Optional[float] = None


@dataclass
class DistributionFile:
    """PyPI 分发文件数据类"""

    filename: str
    url: str
    packagetype: str
    size: int
    upload_time: Optional[str] = None
    requires_python: Optional[str] = None
    hashes: Dict[str, str] = field(default_factory=dict)
    yanked: bool = False
    yanked_reason: Optional[str] = None


class PyPISearchParser(HTMLParser):
    """HTML 解析器，用于解析 PyPI 搜索结果页面"""

    def __init__(self) -> None:
        super().__init__()
        self.results: List[SearchResult] = []
        self.current_package: Optional[Dict[str, Any]] = None
        self.in_package_section = False
        self.current_tag: Optional[str] = None
        self.current_data: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.current_tag = tag
        attrs_dict = dict(attrs)

        # 查找搜索结果容器
        if tag == "a" and "class" in attrs_dict:
            classes = attrs_dict["class"].split() if attrs_dict.get("class") else []
            if "package-snippet" in classes or "snippet" in classes:
                self.in_package_section = True
                href = attrs_dict.get("href", "")
                # 提取包名（从 URL 如 /project/package-name/ 中）
                match = re.search(r"/project/([^/]+)/", href)
                if match:
                    self.current_package = {"name": match.group(1), "href": href}
                return

        # 查找版本号（通常在 span 标签中）
        if tag == "span" and self.in_package_section:
            classes = attrs_dict.get("class", "").split()
            if "package-snippet__version" in classes or "version" in classes:
                self.current_data = []

        # 查找摘要文本
        if tag == "p" and self.in_package_section:
            classes = attrs_dict.get("class", "").split()
            if "package-snippet__description" in classes or "description" in classes:
                self.current_data = []

    def handle_data(self, data: str) -> None:
        if not self.in_package_section:
            return

        data = data.strip()
        if not data:
            return

        if self.current_tag == "span":
            # 版本号
            version_match = re.search(r"(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9]+)?)", data)
            if version_match and self.current_package:
                self.current_package["version"] = version_match.group(1)
        elif self.current_tag == "p":
            # 摘要
            if self.current_package and "summary" not in self.current_package:
                self.current_package["summary"] = data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_package_section:
            if self.current_package:
                result = SearchResult(
                    name=self.current_package.get("name", ""),
                    version=self.current_package.get("version", ""),
                    summary=self.current_package.get("summary"),
                )
                self.results.append(result)
                self.current_package = None
            self.in_package_section = False
        self.current_tag = None
        self.current_data = []


class PyPICrawler:
    """
    PyPI 爬虫客户端，提供与 PyPI API 交互的功能。
    
    主要功能：
    - 查询包信息（支持最新版本和特定版本）
    - 验证包是否存在
    - 搜索包（通过 HTML 解析）
    - 获取包元数据
    - 获取分发文件列表（Simple API）
    
    设计说明：
    - 使用 PyPI 官方 JSON API（https://docs.pypi.org/api/）而不是通过 pip 调用
    - pip 的内部 API 不稳定，官方不推荐作为库使用
    - 对于查询 PyPI 上的包信息，直接调用 PyPI API 是最佳实践
    - 对于已安装的包，使用标准库 `importlib.metadata` 查询
    - 对于 requirements 解析，使用 `packaging` 库
    
    参考：
    - PyPI API 文档：https://docs.pypi.org/api/
    - pip 使用指南：https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program
    """

    BASE_URL = "https://pypi.org"
    JSON_API_URL = f"{BASE_URL}/pypi/{{package_name}}/json"
    JSON_API_VERSION_URL = f"{BASE_URL}/pypi/{{package_name}}/{{version}}/json"
    SIMPLE_API_URL = f"{BASE_URL}/simple/{{package_name}}/"
    SEARCH_API_URL = f"{BASE_URL}/search"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        follow_redirects: bool = True,
    ):
        """
        初始化 PyPI 爬虫客户端。

        Args:
            base_url: PyPI 基础 URL，默认为官方 PyPI (https://pypi.org)
            timeout: 请求超时时间（秒）
            follow_redirects: 是否跟随重定向
        """
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        self._client: Optional[httpx.Client] = None

    def __enter__(self) -> PyPICrawler:
        """支持上下文管理器协议"""
        self._client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=self.follow_redirects,
            )
        return self._client

    def get_package_json(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        从 PyPI JSON API 获取包的原始 JSON 数据。

        Args:
            package_name: 包名称
            version: 版本号，如果为 None 则返回最新版本的所有信息（包含 releases）

        Returns:
            包的 JSON 数据，如果包不存在则返回 None
            
        References:
            - Project API: GET /pypi/<project>/json
            - Release API: GET /pypi/<project>/<version>/json
        """
        if version:
            url = self.JSON_API_VERSION_URL.format(
                package_name=package_name, version=version
            )
        else:
            url = self.JSON_API_URL.format(package_name=package_name)
        client = self._get_client()

        try:
            response = client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except httpx.RequestError as e:
            raise RuntimeError(
                f"Failed to fetch package info for {package_name}: {e}"
            ) from e

    def get_package_info(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[PackageInfo]:
        """
        获取包的详细信息。

        Args:
            package_name: 包名称
            version: 版本号，如果为 None 则返回最新版本的信息

        Returns:
            PackageInfo 对象，如果包不存在则返回 None
        """
        json_data = self.get_package_json(package_name, version)
        if json_data is None:
            return None

        try:
            return PackageInfo.from_json(json_data)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(
                f"Failed to parse package info for {package_name}: {e}"
            ) from e

    def package_exists(self, package_name: str) -> bool:
        """
        检查包是否存在于 PyPI 上。

        Args:
            package_name: 包名称

        Returns:
            如果包存在返回 True，否则返回 False
        """
        json_data = self.get_package_json(package_name)
        return json_data is not None

    def get_package_metadata(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取包的元数据（info 部分）。

        Args:
            package_name: 包名称
            version: 版本号，如果为 None 则返回最新版本

        Returns:
            包的元数据字典（info 部分），如果包不存在则返回 None
        """
        json_data = self.get_package_json(package_name, version)
        if json_data is None:
            return None

        return json_data.get("info", {})

    def search_packages(self, query: str, limit: int = 20) -> List[SearchResult]:
        """
        搜索 PyPI 上的包。
        
        注意：
        - PyPI 没有官方的 JSON 搜索 API
        - pip search 命令已被移除（从 pip 21.0 起）
        - 此方法通过解析 HTML 搜索结果页面实现
        - 页面结构可能变化，如果解析失败可能返回空列表
        
        这是目前唯一可行的搜索方案。

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            SearchResult 对象列表
        """
        client = self._get_client()
        params = {"q": query}

        try:
            response = client.get(
                self.SEARCH_API_URL,
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PyPICrawler/1.0)",
                },
            )
            response.raise_for_status()

            # 解析 HTML 搜索结果
            parser = PyPISearchParser()
            parser.feed(response.text)
            results = parser.results[:limit]
            
            # 如果解析失败，尝试简单的正则表达式匹配作为备用方案
            if not results:
                results = self._fallback_search_parse(response.text, limit)
            
            return results
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to search packages: {e}") from e

    def _fallback_search_parse(self, html: str, limit: int) -> List[SearchResult]:
        """备用搜索解析方法，使用正则表达式"""
        results: List[SearchResult] = []
        # 匹配搜索结果链接：/project/package-name/
        pattern = r'href="/project/([^/"]+)/[^"]*"[^>]*>([^<]+)</a>'
        matches = re.finditer(pattern, html)
        
        seen = set()
        for match in matches:
            package_name = match.group(1)
            display_name = match.group(2).strip()
            
            if package_name in seen:
                continue
            seen.add(package_name)
            
            # 尝试提取版本号（通常在附近的文本中）
            version = "unknown"
            version_match = re.search(
                rf'{re.escape(package_name)}.*?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9]+)?)',
                html[match.start() : match.end() + 200],
            )
            if version_match:
                version = version_match.group(1)
            
            results.append(
                SearchResult(name=package_name, version=version, summary=None)
            )
            
            if len(results) >= limit:
                break
        
        return results

    def get_package_dependencies(
        self, package_name: str, version: Optional[str] = None
    ) -> List[str]:
        """
        获取包的依赖列表。

        Args:
            package_name: 包名称
            version: 版本号，如果为 None 则返回最新版本的依赖

        Returns:
            依赖列表
        """
        metadata = self.get_package_metadata(package_name, version)
        if metadata is None:
            return []

        requires_dist = metadata.get("requires_dist")
        if requires_dist is None:
            return []

        return list(requires_dist) if isinstance(requires_dist, list) else []

    def verify_package_name(self, package_name: str) -> bool:
        """
        验证包名是否在 PyPI 上存在（package_exists 的别名）。

        Args:
            package_name: 包名称

        Returns:
            如果包存在返回 True，否则返回 False
        """
        return self.package_exists(package_name)

    def get_package_distributions(
        self, package_name: str, use_json: bool = True
    ) -> Optional[List[DistributionFile]]:
        """
        使用 Simple API 获取包的所有分发文件列表。

        Args:
            package_name: 包名称
            use_json: 是否使用 JSON 格式（推荐），False 则解析 HTML

        Returns:
            DistributionFile 对象列表，如果包不存在则返回 None
            
        References:
            - Simple API: GET /simple/<project>/
            - PEP 691: JSON API for Simple Repository
        """
        url = self.SIMPLE_API_URL.format(package_name=package_name)
        client = self._get_client()

        try:
            if use_json:
                # 使用 JSON 格式（PEP 691）
                headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                files = []
                for file_info in data.get("files", []):
                    dist_file = DistributionFile(
                        filename=file_info.get("filename", ""),
                        url=file_info.get("url", ""),
                        packagetype=self._guess_packagetype(file_info.get("filename", "")),
                        size=file_info.get("size", 0),
                        upload_time=file_info.get("upload-time"),
                        requires_python=file_info.get("requires-python"),
                        hashes=file_info.get("hashes", {}),
                        yanked=file_info.get("yanked", False),
                    )
                    files.append(dist_file)
                return files
            else:
                # 解析 HTML 格式（PEP 503）
                headers = {"Accept": "application/vnd.pypi.simple.v1+html"}
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return self._parse_html_distributions(response.text)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except httpx.RequestError as e:
            raise RuntimeError(
                f"Failed to fetch distributions for {package_name}: {e}"
            ) from e

    def _parse_html_distributions(self, html: str) -> List[DistributionFile]:
        """解析 HTML 格式的 Simple API 响应"""
        files: List[DistributionFile] = []
        # 匹配链接：<a href="url" data-requires-python="...">filename</a>
        pattern = r'<a[^>]*href="([^"]+)"[^>]*>(.+?)</a>'
        
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = match.group(1)
            filename = match.group(2).strip()
            
            # 提取 data 属性
            link_tag = match.group(0)
            requires_python_match = re.search(
                r'data-requires-python="([^"]*)"', link_tag
            )
            requires_python = (
                requires_python_match.group(1) if requires_python_match else None
            )
            
            # 提取哈希值（URL 片段）
            hash_match = re.search(r'#(sha256|md5|sha1)=([a-fA-F0-9]+)', url)
            hashes = {}
            if hash_match:
                hash_type = hash_match.group(1)
                hash_value = hash_match.group(2)
                hashes[hash_type] = hash_value
            
            dist_file = DistributionFile(
                filename=filename,
                url=url.split("#")[0],  # 移除哈希片段
                packagetype=self._guess_packagetype(filename),
                size=0,  # HTML 格式不包含大小信息
                requires_python=requires_python,
                hashes=hashes,
            )
            files.append(dist_file)
        
        return files

    def _guess_packagetype(self, filename: str) -> str:
        """根据文件名猜测包类型"""
        if filename.endswith(".whl"):
            return "bdist_wheel"
        elif filename.endswith((".tar.gz", ".zip")):
            return "sdist"
        elif filename.endswith(".egg"):
            return "bdist_egg"
        else:
            return "unknown"

    def get_package_versions(self, package_name: str) -> List[str]:
        """
        获取包的所有版本列表。

        Args:
            package_name: 包名称

        Returns:
            版本号列表（从新到旧排序），如果包不存在则返回空列表
        """
        json_data = self.get_package_json(package_name)
        if json_data is None:
            return []

        releases = json_data.get("releases", {})
        # 按版本号排序（简单的字符串排序，对于复杂版本号可能不准确）
        versions = sorted(releases.keys(), reverse=True)
        return versions

