# av
Agent-powered Python environment manager built on uv — your intelligent dependency guardian.

> ⚠️ **Warning**: This project is in early development and is not ready for production use. Features may be incomplete, unstable, or subject to breaking changes.

[English](README.md) | [中文](README_zh.md)

## What it does
- `av venv`: creates a virtual environment (default: `.venv`), scans the current project, proposes dependencies (dynamic detection + LangChain if `OPENAI_API_KEY` is set), then installs them into the virtual environment with `uv pip install ...`.
- Ships as a Python package and can be bundled into a single binary via PyInstaller.

## How dependency detection works

`av` uses an AI agent powered by LangChain 1.x to intelligently analyze your project and propose dependencies:

1. **Agent-Based Analysis**: When `OPENAI_API_KEY` is set, an AI agent autonomously explores your project using multiple tools:
   - **Bash Commands**: Executes commands to explore project structure, read configuration files, and search for imports
   - **PyPI Integration**: Searches PyPI, verifies package names, and retrieves package information and dependencies

2. **Autonomous Discovery**: The agent decides what to explore:
   - Reads dependency configuration files (`pyproject.toml`, `requirements.txt`, `setup.py`)
   - Searches code for import statements
   - Examines project structure and documentation
   - Verifies package names on PyPI
   - Retrieves package metadata and dependencies

3. **Structured Output**: Uses LangChain 1.x structured output to generate a dependency plan with:
   - List of recommended packages (using correct PyPI names)
   - Notes explaining the dependency choices

4. **No Pre-extraction**: Unlike traditional approaches, `av` doesn't pre-extract code or use RAG. The agent uses tools to discover information as needed.

## Requirements

- **Python**: >=3.10 (runtime), 3.13 recommended for development
- **uv**: Latest version from [astral-sh/uv](https://github.com/astral-sh/uv)

## Quickstart
1) Install [uv](https://github.com/astral-sh/uv) and ensure it is on `PATH`.
2) Create an environment with Python 3.10+ and install deps: `uv venv --python 3.10 && uv pip install -e .[dev]` (or use Python 3.13 for development).
3) Create virtual environment and install dependencies: `uv run av venv` (no arguments needed by default).
4) Run a dry plan: `uv run av venv --dry-run`.
5) Install automatically without confirmation: `uv run av venv -y`.

Optional: set `OPENAI_API_KEY` to enable AI-powered dependency analysis using LangChain 1.x with tool calling.

## Binary build

### Automated builds

The project is configured with GitHub Actions automated build workflows:

- **Build workflow** (`build.yml`): 
  - Automatically triggered on pushes to `main`/`master` branches or PR creation
  - Supports Windows, Linux, and macOS platforms
  - Build artifacts are saved as artifacts for 30 days

- **Release workflow** (`release.yml`):
  - Automatically triggered when creating `v*` tags (e.g., `v1.0.0`)
  - Builds binaries for all platforms
  - Automatically creates GitHub Release and uploads build artifacts for all platforms

#### Usage

1. **View build results**: Check build status in the "Actions" tab of the GitHub repository
2. **Download build artifacts**: After the Actions run completes, click on the corresponding run and download from the "Artifacts" section
3. **Create a release**: Push a version tag to automatically create a release:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

## Test Repositories

The project includes a `test_repos` folder that maintains multiple third-party Python libraries via git submodules for testing the environment configuration agent's performance.

### Initialize Submodules

```bash
git submodule update --init --recursive
```

### Test Agent Performance

Run in any test repository directory:

```bash
cd test_repos/<library_name>
av venv            # Create virtual environment and install dependencies
av venv --dry-run  # View dependency analysis plan without installing
av venv -y         # Auto-install dependencies without confirmation
```

See [test_repos/README.md](test_repos/README.md) for more information.

## Project structure
- CLI entry: [src/av/cli.py](src/av/cli.py)
- AI agent with tool calling: [src/av/agent.py](src/av/agent.py)
- PyPI crawler: [src/av/pypi_crawler.py](src/av/pypi_crawler.py)
