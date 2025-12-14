from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from av.agent import refine_plan_with_langchain
from av.pypi_crawler import PyPICrawler

console = Console()
app = typer.Typer(add_completion=False, help="Agent-powered Python environment manager")


def run_command(command: list[str]) -> int:
    process = subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr, text=True)
    return process.returncode


def show_plan(deps: list[str], note: str) -> None:
    table = Table(title="Installation Plan", show_header=True, header_style="bold green")
    table.add_column("Source", style="cyan")
    table.add_column("Details", style="white")
    table.add_row("LangChain", note)
    table.add_row("Dependencies", "\n".join(deps) if deps else "<empty>")
    console.print(table)


@app.command()
def venv(
    venv_path: Optional[Path] = typer.Argument(None, help="Virtual environment path (default: .venv)"),
    project_path: Optional[Path] = typer.Option(None, "--project", "-p", help="Project directory to analyze (default: current directory)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation and install"),
    dry_run: bool = typer.Option(False, help="Only show plan, do not install"),
) -> None:
    """Create a virtual environment and install project dependencies with uv."""
    # 确定虚拟环境路径
    if venv_path is None:
        venv_path = Path(".venv")
    else:
        venv_path = Path(venv_path)
    
    # 确定项目路径（用于扫描依赖）
    if project_path is None:
        project_path = Path.cwd()
    else:
        project_path = project_path.resolve()
    
    # 验证项目路径存在且是目录
    if not project_path.exists():
        console.print(f"[red]Error: Project path does not exist: {project_path}[/red]")
        raise typer.Exit(code=1)
    
    if not project_path.is_dir():
        console.print(f"[red]Error: Project path is not a directory: {project_path}[/red]")
        raise typer.Exit(code=1)
    
    # 计算虚拟环境的绝对路径
    if venv_path.is_absolute():
        venv_abs_path = venv_path.resolve()
        venv_relative = venv_path
    else:
        venv_abs_path = (project_path / venv_path).resolve()
        venv_relative = venv_path
    
    # 创建虚拟环境
    venv_exists = venv_abs_path.exists()
    skip_create = False
    
    if venv_exists:
        if dry_run:
            # 在 dry_run 模式下，如果虚拟环境已存在，跳过创建
            skip_create = True
        else:
            # 如果虚拟环境已存在，询问是否清除
            if not yes:
                proceed_clear = Confirm.ask(
                    f"Virtual environment already exists at {venv_abs_path}. Clear and recreate?",
                    default=False
                )
                if not proceed_clear:
                    # 用户选择不清理，使用已存在的虚拟环境
                    skip_create = True
                # 如果用户选择清理，skip_create 保持 False，会继续创建
            # 使用 -y 标志时，自动清理（skip_create 保持 False）
    
    if not skip_create:
        console.print(f"[cyan]Creating virtual environment at: {venv_abs_path}[/cyan]")
        venv_command = ["uv", "venv", str(venv_relative)]
        
        if venv_exists:
            # 如果虚拟环境已存在，添加 --clear 标志
            venv_command.append("--clear")
        
        code = run_command(venv_command)
        if code != 0:
            console.print(f"[red]Failed to create virtual environment with exit code {code}[/red]")
            raise typer.Exit(code=code)
        
        console.print(f"[green]Virtual environment created successfully.[/green]")
    else:
        console.print(f"[green]Using existing virtual environment.[/green]")
    
    # 使用 LangChain 生成依赖计划（不使用 RAG）
    console.print(f"[cyan]Analyzing project at: {project_path}[/cyan]")
    with PyPICrawler() as crawler:
        deps, note = refine_plan_with_langchain(project_path, pypi_crawler=crawler)

    show_plan(deps, note)

    if not deps:
        console.print("[yellow]No dependencies detected; nothing to install.[/yellow]")
        raise typer.Exit(code=0)

    if dry_run:
        console.print("[yellow]Dry run mode: skipping installation.[/yellow]")
        raise typer.Exit(code=0)

    # 安装依赖到虚拟环境
    proceed = yes or Confirm.ask("Install dependencies into virtual environment?", default=True)
    if not proceed:
        raise typer.Exit(code=0)

    # 确定虚拟环境中的 Python 可执行文件路径（使用绝对路径）
    import sys
    venv_abs_path = venv_path.resolve() if venv_path.is_absolute() else (project_path / venv_path).resolve()
    if sys.platform == "win32":
        python_exe = venv_abs_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_abs_path / "bin" / "python"
    
    # 使用 uv pip install 安装依赖，指定虚拟环境的 Python
    command = ["uv", "pip", "install", "--python", str(python_exe), *deps]
    console.print(f"[bold]Running:[/bold] {' '.join(command)}")
    code = run_command(command)
    if code != 0:
        console.print(f"[red]uv install failed with exit code {code}[/red]")
        raise typer.Exit(code=code)

    console.print(f"[green]Dependencies installed successfully into {venv_abs_path}.[/green]")


def main(argv: Optional[list[str]] = None) -> None:
    app(standalone_mode=True, prog_name="av", args=argv)


if __name__ == "__main__":
    main()
