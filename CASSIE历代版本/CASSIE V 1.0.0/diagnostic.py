import os
import json
import platform
import subprocess
import sys
import importlib.metadata
import time

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich import box

PROJECT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
console = Console()


def print_section(title):
    console.rule(f"[bold cyan]{title}[/bold cyan]")


def print_subsection(title):
    console.print(f"\n[bold]{title}[/bold]")


def ask_yes_no(prompt):
    return Confirm.ask(f"[bold]{prompt}[/bold]")


def run_command(cmd, description):
    console.print(f"  [dim]执行:[/dim] {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
        console.print(f"  {description} [green]成功[/green]")
        return True
    except subprocess.CalledProcessError:
        console.print(f"  {description} [red]失败[/red]")
        return False


def pip_install(package_name):
    pip_cmd = [sys.executable, '-m', 'pip', 'install', package_name]
    console.print(f"  [dim]执行:[/dim] {' '.join(pip_cmd)}")
    try:
        subprocess.run(pip_cmd, check=True)
        console.print(f"  {package_name} [green]安装成功[/green]")
        return True
    except subprocess.CalledProcessError:
        console.print(f"  {package_name} [red]安装失败[/red]")
        return False


def get_package_version(package_name):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def check_python_version():
    version = sys.version_info
    required = (3, 10, 15)
    ok = version >= required
    detail = f"{version.major}.{version.minor}.{version.micro} (需要 >= 3.10.15)"
    return ok, detail, f"{version.major}.{version.minor}.{version.micro}"


def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        version_line = result.stdout.splitlines()[0] if result.stdout else "未知"
        return True, version_line.strip()
    except FileNotFoundError:
        return False, "未安装"


def check_colorednoise():
    try:
        import colorednoise
        return True, get_package_version('colorednoise') or "已安装"
    except ImportError:
        return False, "未安装"


def check_numpy():
    try:
        import numpy
        return True, get_package_version('numpy') or "已安装"
    except ImportError:
        return False, "未安装"


def check_bottle():
    try:
        import bottle
        return True, get_package_version('bottle') or "已安装"
    except ImportError:
        return False, "未安装"


def check_pygame():
    try:
        import pygame
        return True, get_package_version('pygame') or "已安装"
    except ImportError:
        return False, "未安装"


def check_pydub():
    try:
        import pydub
        return True, get_package_version('pydub') or "已安装"
    except ImportError:
        return False, "未安装"


def check_cheroot():
    try:
        import cheroot
        return True, get_package_version('cheroot') or "已安装"
    except ImportError:
        return False, "未安装"


def check_requests():
    try:
        import requests
        return True, get_package_version('requests') or "已安装"
    except ImportError:
        return False, "未安装"


def check_rich():
    try:
        import rich
        return True, get_package_version('rich') or "已安装"
    except ImportError:
        return False, "未安装"


def check_files():
    results = []
    exists = os.path.exists('cassie_play.py')
    results.append(('cassie_play.py', exists, '存在' if exists else '缺失'))
    cassie_exists = os.path.exists('cassie/')
    if cassie_exists:
        words_exists = os.path.exists('cassie/words/')
        sounds_exists = os.path.exists('cassie/sounds/')
        alarms_exists = os.path.exists('cassie/alarms/')
        if words_exists and sounds_exists and alarms_exists:
            results.append(('cassie/', True, '存在，包含 words/、sounds/ 和 alarms/ 子文件夹'))
        else:
            missing = []
            if not words_exists:
                missing.append('words/')
            if not sounds_exists:
                missing.append('sounds/')
            if not alarms_exists:
                missing.append('alarms/')
            results.append(('cassie/', False, f'存在，但缺少子文件夹: {", ".join(missing)}'))
    else:
        results.append(('cassie/', False, '文件夹不存在'))
    if os.path.exists('cassie/words/'):
        wav_files = [f for f in os.listdir('cassie/words/') if f.endswith('.wav')]
        if wav_files:
            results.append(('cassie/words/', True, f'存在，包含 {len(wav_files)} 个 .wav 文件'))
        else:
            results.append(('cassie/words/', False, '存在但没有 .wav 文件'))
    else:
        results.append(('cassie/words/', False, '文件夹不存在'))
    if os.path.exists('cassie/sounds/'):
        wav_files = [f for f in os.listdir('cassie/sounds/') if f.endswith('.wav')]
        if wav_files:
            results.append(('cassie/sounds/', True, f'存在，包含 {len(wav_files)} 个 .wav 文件'))
        else:
            results.append(('cassie/sounds/', False, '存在但没有 .wav 文件'))
    else:
        results.append(('cassie/sounds/', False, '文件夹不存在'))
    static_exists = os.path.exists('static/')
    if static_exists:
        css_exists = os.path.exists('static/style.css')
        if css_exists:
            results.append(('static/', True, '存在，包含 style.css'))
        else:
            results.append(('static/', False, '存在但缺少 style.css'))
    else:
        results.append(('static/', False, '文件夹不存在'))
    exists = os.path.exists('presets.json')
    results.append(('presets.json', exists, '存在' if exists else '缺失'))
    exists = os.path.exists('word_list.json')
    results.append(('word_list.json', exists, '存在' if exists else '缺失'))
    exists = os.path.exists('sound_list.json')
    results.append(('sound_list.json', exists, '存在' if exists else '缺失'))
    for document in (os.path.join('docs', 'help.html'), os.path.join('docs', 'developer.html')):
        exists = os.path.exists(document)
        results.append((document, exists, '存在' if exists else '缺失'))
    vscode_exists = os.path.exists('.vscode/')
    if vscode_exists:
        settings_exists = os.path.exists('.vscode/settings.json')
        if settings_exists:
            results.append(('.vscode/', True, '存在，包含 settings.json'))
        else:
            results.append(('.vscode/', False, '存在但缺少 settings.json'))
    else:
        results.append(('.vscode/', False, '文件夹不存在'))
    pycache_exists = os.path.exists('__pycache__/')
    if pycache_exists:
        pyc_files = [f for f in os.listdir('__pycache__/') if f.endswith('.pyc')]
        results.append(('__pycache__/', True, f'存在，包含 {len(pyc_files)} 个 .pyc 文件'))
    else:
        results.append(('__pycache__/', False, '文件夹不存在'))
    return results


def check_audio_files():
    if not os.path.exists('word_list.json') or not os.path.exists('sound_list.json'):
        return None, "word_list.json 或 sound_list.json 不存在，跳过音频匹配检测"
    try:
        with open('word_list.json', 'r', encoding='utf-8') as f:
            words_expected = set(json.load(f))
        with open('sound_list.json', 'r', encoding='utf-8') as f:
            sounds_expected = set(json.load(f))
    except:
        return None, "JSON 文件格式错误"

    words_existing = set()
    if os.path.exists('cassie/words/'):
        for f in os.listdir('cassie/words/'):
            if f.endswith('.wav'):
                words_existing.add(f[:-4])

    sounds_existing = set()
    if os.path.exists('cassie/sounds/'):
        for f in os.listdir('cassie/sounds/'):
            if f.endswith('.wav'):
                sounds_existing.add(f[:-4])

    words_missing = words_expected - words_existing
    sounds_missing = sounds_expected - sounds_existing
    words_wrong = words_expected & sounds_existing
    sounds_wrong = sounds_expected & words_existing

    details = []
    if words_missing:
        details.append(f"words 文件夹缺失 {len(words_missing)} 个文件: {', '.join(sorted(words_missing))}")
    if sounds_missing:
        details.append(f"sounds 文件夹缺失 {len(sounds_missing)} 个文件: {', '.join(sorted(sounds_missing))}")
    if words_wrong:
        details.append(f"{len(words_wrong)} 个本应在 words 的文件出现在了 sounds 中: {', '.join(sorted(words_wrong))}")
    if sounds_wrong:
        details.append(f"{len(sounds_wrong)} 个本应在 sounds 的文件出现在了 words 中: {', '.join(sorted(sounds_wrong))}")
    words_extra = words_existing - words_expected
    sounds_extra = sounds_existing - sounds_expected
    if words_extra:
        console.print(f"[yellow]words 文件夹有多余文件: {', '.join(sorted(words_extra))}[/yellow]")
    if sounds_extra:
        console.print(f"[yellow]sounds 文件夹有多余文件: {', '.join(sorted(sounds_extra))}[/yellow]")

    if not details:
        return True, "所有音频文件匹配"
    else:
        return False, "; ".join(details)


def install_ffmpeg():
    system = platform.system()
    if system == 'Darwin':
        console.print("  检测到 macOS，将尝试使用 Homebrew 安装 ffmpeg...")
        if not run_command('brew install ffmpeg', 'ffmpeg 安装'):
            console.print("  如果 Homebrew 未安装，请先安装 Homebrew: [link]https://brew.sh[/link]")
    elif system == 'Windows':
        console.print("  检测到 Windows，请手动下载 ffmpeg 并添加到 PATH。")
        console.print("  下载地址: [link]https://ffmpeg.org/download.html[/link]")
        console.print("  安装后请重启终端再运行此诊断工具。")
    else:
        console.print(f"  不支持的系统: {system}，请手动安装 ffmpeg")


def install_colorednoise():
    console.print("  正在安装 colorednoise 和 numpy...")
    if pip_install('colorednoise') and pip_install('numpy'):
        console.print("  [green]colorednoise 和 numpy 安装成功[/green]")
    else:
        console.print("  [red]安装失败[/red]，请手动执行: pip install colorednoise numpy")


def main():
    os.chdir(PROJECT_BASE_PATH)
    console.print(Panel.fit(
        "[bold cyan]CASSIE 广播生成器 - 诊断工具[/bold cyan]",
        box=box.DOUBLE,
        border_style="cyan",
    ))
    console.print(f"[dim]开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

    system = platform.system()
    overall_success = True
    pending_fixes = []

    print_subsection("操作系统详细检测")
    os_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    os_table.add_column("项目", style="cyan")
    os_table.add_column("值")
    os_table.add_row("系统名称", system)
    if system == 'Darwin':
        ver = platform.mac_ver()[0] or "未知"
        os_table.add_row("macOS 版本", ver)
        os_table.add_row("架构", platform.machine())
        os_table.add_row("处理器", platform.processor())
        if ver and int(ver.split('.')[0]) < 13:
            os_table.add_row("提示", "[yellow]macOS 版本低于 13.0，浏览器系统音频共享可能受限[/yellow]")
    elif system == 'Windows':
        ver = platform.version()
        os_table.add_row("Windows 版本", ver)
        os_table.add_row("架构", platform.machine())
        if int(ver.split('.')[0]) < 10:
            os_table.add_row("提示", "[yellow]Windows 版本低于 10，浏览器系统音频共享可能受限[/yellow]")
    else:
        os_table.add_row("状态", "[red]不支持的操作系统[/red]")
        overall_success = False
    console.print(os_table)

    print_subsection("Python 版本检测")
    py_ok, py_detail, py_ver = check_python_version()
    py_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    py_table.add_column("项目", style="cyan")
    py_table.add_column("值")
    py_table.add_row("Python 版本", py_ver)
    py_table.add_row("构建日期", sys.version.split('[')[0] if '[' in sys.version else sys.version.split()[0])
    py_table.add_row("编译器", sys.version.split('[')[-1][:-1] if '[' in sys.version else '未知')
    py_table.add_row("平台", platform.platform())
    if not py_ok:
        py_table.add_row("状态", "[red]版本过低，请升级到 3.10.15 或更高[/red]")
        overall_success = False
    else:
        py_table.add_row("状态", "[green]符合要求[/green]")
    console.print(py_table)

    print_subsection("第三方库检测")
    libs = {
        'bottle': check_bottle,
        'pygame': check_pygame,
        'pydub': check_pydub,
        'colorednoise': check_colorednoise,
        'numpy': check_numpy,
        'cheroot': check_cheroot,
        'requests': check_requests,
        'rich': check_rich,
    }
    lib_table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    lib_table.add_column("库名", style="cyan")
    lib_table.add_column("状态", justify="center")
    lib_table.add_column("版本")
    for name, func in libs.items():
        ok, detail = func()
        if ok:
            ver = get_package_version(name)
            lib_table.add_row(name, "[green]已安装[/green]", ver or "-")
        else:
            lib_table.add_row(name, "[red]未安装[/red]", "-")
            overall_success = False
            if name in ('colorednoise', 'numpy', 'requests', 'rich'):
                pending_fixes.append((name, f'安装 {name}'))
    console.print(lib_table)

    print_subsection("ffmpeg 检测")
    has_ffmpeg, ffmpeg_ver = check_ffmpeg()
    if has_ffmpeg:
        console.print(f"  [green]✓[/green] ffmpeg: 已安装 ({ffmpeg_ver})")
    else:
        console.print(f"  [red]✗[/red] ffmpeg: 未安装 (需要用于音频处理)")
        overall_success = False
        pending_fixes.append(('ffmpeg', '安装 ffmpeg'))

    print_subsection("必要文件和文件夹检测")
    file_results = check_files()
    file_table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    file_table.add_column("项目", style="cyan")
    file_table.add_column("状态", justify="center")
    file_table.add_column("详情")
    for name, status, detail in file_results:
        status_text = "[green]存在[/green]" if status else "[red]缺失[/red]"
        if not status and name not in ('presets.json', 'word_list.json', 'sound_list.json'):
            overall_success = False
        file_table.add_row(name, status_text, detail)
    console.print(file_table)

    print_subsection("音频文件匹配检测")
    audio_status, audio_detail = check_audio_files()
    if audio_status is None:
        console.print(f"  [yellow]{audio_detail}[/yellow]")
        overall_success = False
    else:
        if audio_status:
            console.print(f"  [green]✓[/green] 音频文件匹配: {audio_detail}")
        else:
            console.print(f"  [red]✗[/red] 音频文件匹配: {audio_detail}")
            overall_success = False

    if pending_fixes:
        console.print()
        console.print(Panel(
            "[bold yellow]检测到以下问题，可选择自动修复[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        ))
        for i, (key, desc) in enumerate(pending_fixes, 1):
            console.print(f"  [cyan]{i}.[/cyan] {desc}")

        for key, desc in pending_fixes:
            if key == 'ffmpeg':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    install_ffmpeg()
                    if check_ffmpeg()[0]:
                        overall_success = True
                    else:
                        console.print("  [red]ffmpeg 安装失败[/red]")
            elif key == 'colorednoise':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    install_colorednoise()
                    if check_colorednoise()[0] and check_numpy()[0]:
                        overall_success = True
                    else:
                        console.print("  [red]安装失败[/red]")
            elif key == 'numpy':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    if pip_install('numpy'):
                        overall_success = True
                    else:
                        console.print("  [red]numpy 安装失败[/red]")
            elif key == 'requests':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    if pip_install('requests'):
                        overall_success = True
                    else:
                        console.print("  [red]requests 安装失败[/red]")
            elif key == 'rich':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    if pip_install('rich'):
                        overall_success = True
                    else:
                        console.print("  [red]rich 安装失败[/red]")
    else:
        console.print("\n[dim]没有检测到可自动修复的问题。[/dim]")

    # 素材缺失是新用户最常见的卡点，单独给一块可照着做的说明
    words_dir = 'cassie/words/'
    words_present = os.path.exists(words_dir) and any(
        name.endswith('.wav') for name in os.listdir(words_dir))
    if not words_present:
        console.print()
        console.print(Panel(
            "[bold red]没有找到音频素材[/bold red]\n\n"
            "本仓库和发布包都[bold]不包含音频素材[/bold]，"
            "必须单独下载后程序才能生成广播。\n\n"
            "运行下载器（推荐，会自动解压到正确位置）：\n"
            "  [bold cyan]cd ../CASSIE语音生成[/bold cyan]\n"
            "  [bold cyan]python cassie_download.py[/bold cyan]\n\n"
            "或从发布页获取：\n"
            "  [link]https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases[/link]\n\n"
            "[dim]下载完成后重新运行本诊断工具确认。[/dim]",
            box=box.ROUNDED,
            border_style="red",
        ))

    console.print()
    console.print(Panel.fit(
        f"[bold]诊断完成[/bold]\n"
        f"[dim]结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n\n"
        + ("[bold green]检测成功[/bold green]\n所有项目均已通过检测，系统环境就绪。"
           if overall_success else
           "[bold red]检测失败[/bold red]\n部分问题需要手动处理，请参考上述提示。"),
        box=box.DOUBLE,
        border_style="green" if overall_success else "red",
    ))


if __name__ == "__main__":
    main()