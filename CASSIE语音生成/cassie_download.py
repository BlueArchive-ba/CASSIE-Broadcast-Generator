import os
import sys
import time
import zipfile
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    DownloadColumn, TransferSpeedColumn, TimeRemainingColumn,
    TaskProgressColumn, TimeElapsedColumn, MofNCompleteColumn,
)
from rich.prompt import Confirm, Prompt
from rich.text import Text
from rich import box

GITHUB_URL = "https://github.com/BlueArchive-ba/CASSIE/releases/download/v1.3.0/cassie.zip"
MIRROR_PREFIX = "https://gh-proxy.com/"
DEFAULT_THREADS = 16
MIN_THREADS = 4
MAX_THREADS = 32
CHUNK_SIZE = 1024 * 64
MAX_RETRY = 3

console = Console()


def human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def ask_threads():
    console.print(Panel.fit(
        f"[bold cyan]下载线程设置[/bold cyan]\n\n"
        f"线程越多速度可能越快，但太多会被服务器限流，反而变慢。\n"
        f"建议范围: [yellow]{MIN_THREADS}[/yellow] - [yellow]{MAX_THREADS}[/yellow]，"
        f"默认 [green]{DEFAULT_THREADS}[/green]",
        border_style="cyan",
        box=box.ROUNDED,
    ))
    while True:
        ans = Prompt.ask(
            f"  请输入线程数",
            default=str(DEFAULT_THREADS),
            show_default=True,
        ).strip()
        try:
            n = int(ans)
            if MIN_THREADS <= n <= MAX_THREADS:
                return n
            console.print(f"  [red]请输入 {MIN_THREADS} 到 {MAX_THREADS} 之间的整数。[/red]")
        except ValueError:
            console.print("  [red]请输入一个整数。[/red]")


def get_remote_size(url):
    try:
        r = requests.head(url, timeout=30, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        size = r.headers.get("Content-Length")
        if size is None:
            return None
        return int(size)
    except Exception as e:
        console.print(f"  [red]获取文件大小失败:[/red] {e}")
        return None


def download_chunk(url, start, end, part_path, progress, task_id, lock, retry=MAX_RETRY):
    headers = {"Range": f"bytes={start}-{end}", "User-Agent": "Mozilla/5.0"}
    for attempt in range(1, retry + 1):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                written = 0
                with open(part_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        written += len(chunk)
                        with lock:
                            progress.update(task_id, advance=len(chunk))
                expected = end - start + 1
                if written != expected:
                    raise ValueError(f"分片大小不符: {written} != {expected}")
                return True
        except Exception as e:
            if attempt < retry:
                time.sleep(2 * attempt)
            else:
                raise


def download_multi_thread(url, dest_path, threads):
    size = get_remote_size(url)
    if size is None:
        console.print("[yellow]无法获取文件大小，改用单线程下载。[/yellow]")
        return download_single_thread(url, dest_path)

    console.print(Panel.fit(
        f"[bold]下载信息[/bold]\n\n"
        f"文件大小: [cyan]{human_size(size)}[/cyan]\n"
        f"线程数:   [cyan]{threads}[/cyan]\n"
        f"保存到:   [cyan]{dest_path}[/cyan]",
        border_style="cyan",
        box=box.ROUNDED,
    ))
    console.print()

    part_dir = dest_path.parent / (dest_path.name + ".parts")
    part_dir.mkdir(exist_ok=True)

    chunk_size = size // threads
    ranges = []
    for i in range(threads):
        start = i * chunk_size
        end = start + chunk_size - 1 if i < threads - 1 else size - 1
        ranges.append((i, start, end))

    lock = threading.Lock()
    failed = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    with progress:
        overall_task = progress.add_task("[cyan]总进度", total=size)

        def make_chunk_task(idx, start, end):
            part_size = end - start + 1
            return progress.add_task(
                f"[dim]分片 {idx + 1:>2}/{threads}[/dim]",
                total=part_size,
                visible=False,
            )

        def chunk_worker(idx, start, end):
            part_path = part_dir / f"part_{idx}"
            task_id = make_chunk_task(idx, start, end)
            try:
                download_chunk(url, start, end, part_path, progress, task_id, lock)
                progress.update(task_id, visible=True, description=f"[green]分片 {idx + 1:>2}/{threads}[/green]")
            except Exception as e:
                with lock:
                    failed.append((idx, start, end, str(e)))
                progress.update(task_id, visible=True, description=f"[red]分片 {idx + 1:>2}/{threads}[/red]")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for idx, start, end in ranges:
                futures.append(executor.submit(chunk_worker, idx, start, end))
            for fut in as_completed(futures):
                fut.result()

        elapsed = time.time() - start_time
        progress.update(overall_task, completed=size)

    console.print()
    console.print(f"  下载耗时: [cyan]{int(elapsed)}[/cyan] 秒")
    console.print(f"  平均速度: [cyan]{human_size(size / max(elapsed, 0.01))}/s[/cyan]")

    if failed:
        console.print()
        console.print(Panel.fit(
            "[bold red]以下分片下载失败[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))
        fail_table = Table(show_header=True, header_style="bold red", box=box.SIMPLE)
        fail_table.add_column("分片", justify="right", style="cyan")
        fail_table.add_column("起始字节", justify="right")
        fail_table.add_column("结束字节", justify="right")
        fail_table.add_column("错误", style="red")
        for idx, start, end, err in failed:
            fail_table.add_row(str(idx + 1), str(start), str(end), err)
        console.print(fail_table)
        console.print("[yellow]请重新运行本程序，已下载的分片会被跳过。[/yellow]")
        return False

    console.print()
    with console.status("[bold cyan]正在合并分片...[/bold cyan]", spinner="dots"):
        with open(dest_path, "wb") as out:
            for idx, _, _ in ranges:
                part_path = part_dir / f"part_{idx}"
                with open(part_path, "rb") as f:
                    while True:
                        buf = f.read(CHUNK_SIZE)
                        if not buf:
                            break
                        out.write(buf)

        for idx, _, _ in ranges:
            (part_dir / f"part_{idx}").unlink(missing_ok=True)
        part_dir.rmdir()

    actual = dest_path.stat().st_size
    if actual != size:
        console.print(f"  [red]文件大小校验失败: {actual} != {size}[/red]")
        return False
    console.print("  [green]分片合并完成，文件大小校验通过[/green]")
    return True


def download_single_thread(url, dest_path):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, stream=True, timeout=60, headers=headers) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))

            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            )
            with progress:
                task = progress.add_task("[cyan]下载中", total=total)
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
            return True
    except requests.exceptions.RequestException as e:
        console.print(f"\n  [red]下载失败:[/red] {e}")
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        return False


def extract_with_progress(zip_path, extract_dir):
    with zipfile.ZipFile(zip_path, "r") as z:
        members = z.namelist()
        total = len(members)

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        )
        with progress:
            task = progress.add_task(f"[cyan]解压中", total=total)
            for member in members:
                progress.update(task, description=f"[cyan]解压: {member[:50]}")
                z.extract(member, extract_dir)
                progress.update(task, advance=1)


def main():
    console.print(Panel.fit(
        "[bold cyan]C.A.S.S.I.E. 音频包下载工具[/bold cyan]",
        box=box.DOUBLE,
        border_style="cyan",
    ))
    console.print()

    info_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    info_table.add_column("项目", style="cyan")
    info_table.add_column("值")
    info_table.add_row("下载地址", GITHUB_URL)
    info_table.add_row("保存位置", str(Path.cwd()))
    console.print(info_table)
    console.print()

    console.print(Panel(
        "[bold]本程序将执行以下操作：[/bold]\n\n"
        "  1. 从 GitHub Releases 下载音频压缩包\n"
        "  2. 下载完成后询问你是否解压\n"
        "  3. 解压完成后告诉你文件在哪，并引导你放入项目目录",
        border_style="dim",
        box=box.ROUNDED,
    ))
    console.print()

    if not Confirm.ask("[bold]是否开始下载？[/bold]", default=True):
        console.print("[yellow]已取消。[/yellow]")
        return

    console.print()
    threads = ask_threads()

    console.print()
    console.rule("[bold cyan]开始下载[/bold cyan]")

    zip_name = GITHUB_URL.split("/")[-1]
    zip_path = Path.cwd() / zip_name

    if zip_path.exists():
        console.print(f"[yellow]检测到已存在文件:[/yellow] {zip_path}")
        if not Confirm.ask("[bold]是否覆盖？[/bold使用]", default=False):
            console.print("[yellow]已取消下载。[/yellow]")
            return
        try:
            zip_path.unlink()
        except OSError as e:
            console.print(f"[red]无法删除旧文件: {e}[/red]")
            return

    console.print()
    console.print("[bold]尝试官方直连清单...[/bold]")
    console.print()
    ok = download_multi_thread(GITHUB_URL, zip_path, threads)

    if not ok:
        console.print()
        console.print("[red]官方直连下载失败。[/red]")
        if Confirm.ask("[bold]是否使用镜像 gh-proxy.com 重试？[/bold]", default=True):
            console.print()
            console.print(f"[bold]尝试镜像:[/bold] [cyan]{MIRROR_PREFIX}[/cyan]")
            console.print()
            mirror_url = MIRROR_PREFIX + GITHUB_URL
            ok = download_multi_thread(mirror_url, zip_path, threads)
            if not ok:
                console.print()
                console.print(Panel.fit(
                    "[bold red]镜像下载失败[/bold red]\n\n"
                    "建议：\n"
                    "  1. 检查网络连接\n"
                    "  2. 手动访问 GitHub 下载页面\n"
                    f"     [link]{GITHUB_URL}[/link]\n"
                    "  3. 尝试减少线程数后重试",
                    border_style="red",
                    box=box.ROUNDED,
                ))
                return
        else:
            return

    console.print()
    console.print(Panel.fit(
        f"[bold green]下载完成[/bold green]\n\n"
        f"文件: [cyan]{zip_path}[/cyan]\n"
        f"大小: [cyan]{human_size(zip_path.stat().st_size)}[/cyan]",
        border_style="green",
        box=box.ROUNDED,
    ))
    console.print()

    console.rule("[bold cyan]解压选项[/bold cyan]")
    if not Confirm.ask("[bold]是否自动解压？[/bold]", default=True):
        console.print()
        console.print(f"[yellow]已跳过解压。压缩包保留在:[/yellow]")
        console.print(f"  [cyan]{zip_path}[/cyan]")
        console.print()
        console.print("你可以手动解压后，将 sounds 和 words 文件夹")
        console.print("放入项目的 CASSIE 目录中。")
        return

    console.print()
    default_dir = zip_path.parent
    console.print(f"默认解压到: [cyan]{default_dir}[/cyan]")
    if Confirm.ask("[bold]是否修改解压目录？[/bold]", default=False):
        while True:
            custom = Prompt.ask("  请输入解压目录的完整路径").strip().strip('"')
            if not custom:
                console.print("  [red]路径不能为空。[/red]")
                continue
            custom_path = Path(custom)
            try:
                custom_path.mkdir(parents=True, exist_ok=True)
                extract_dir = custom_path
                break
            except OSError as e:
                console.print(f"  [red]无法创建目录: {e}[/red]")
    else:
        extract_dir = default_dir

    console.print()
    console.rule("[bold cyan]开始解压[/bold cyan]")
    try:
        extract_with_progress(zip_path, extract_dir)
    except zipfile.BadZipFile:
        console.print("\n[red]错误：压缩包损坏或不是有效的 zip 文件。[/red]")
        return
    except Exception as e:
        console.print(f"\n[red]解压失败: {e}[/red]")
        return

    console.print()
    console.print("[green]解压完成[/green]")
    console.print()
    console.rule("[bold cyan]清理[/bold cyan]")
    if Confirm.ask("[bold]是否删除压缩包？[/bold]", default=True):
        try:
            zip_path.unlink()
            console.print("[green]压缩包已删除[/green]")
        except OSError as e:
            console.print(f"[red]删除失败: {e}[/red]")
    else:
        console.print(f"压缩包保留在: [cyan]{zip_path}[/cyan]")

    console.print()
    console.rule("[bold cyan]下一步[/bold cyan]")
    console.print()
    console.print(Panel.fit(
        f"[bold]解压后的文件位于:[/bold]\n"
        f"  [cyan]{extract_dir}[/cyan]\n\n"
        f"请将这个文件夹放入项目的根目录，即:\n"
        f"  [green]CASSIE V 1.0.0[/green]\n\n"
        f"[dim]最终目录结构应为:[/dim]\n"
        f"  [green]CASSIE V 1.0.0/[/green]\n"
        f"    [yellow]cassie[/yellow]",
        border_style="green",
        box=box.DOUBLE,
    ))
    console.print()
    console.rule("[bold cyan]程序结束[/bold cyan]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]已中断。[/yellow]")
        sys.exit(1)