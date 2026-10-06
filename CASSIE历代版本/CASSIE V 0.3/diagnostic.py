import os
import json
import platform
import subprocess
import sys
import importlib.metadata
import time

PROJECT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def print_section(title):
    print("\n" + "=" * 70)
    print(f"{title}")
    print("=" * 70)

def print_subsection(title):
    print(f"\n--- {title} ---")

def print_item(status, name, detail=""):
    if status is None:
        status_char = "?"
        color = YELLOW
    elif status:
        status_char = "✓"
        color = GREEN
    else:
        status_char = "✗"
        color = RED
    print(f"  {color}{status_char}{RESET} {name}: {detail}")

def ask_yes_no(prompt):
    while True:
        ans = input(f"{prompt} (Y/N): ").strip().lower()
        if ans in ('y', 'yes'):
            return True
        elif ans in ('n', 'no'):
            return False
        else:
            print("请输入 Y 或 N")

def run_command(cmd, description):
    print(f"  执行: {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"  {description} " + GREEN + "成功" + RESET)
        return True
    except subprocess.CalledProcessError:
        print(f"  {description} " + RED + "失败" + RESET)
        return False

def pip_install(package_name):
    pip_cmd = [sys.executable, '-m', 'pip', 'install', package_name]
    print(f"  执行: {' '.join(pip_cmd)}")
    try:
        subprocess.run(pip_cmd, check=True)
        print(f"  {package_name} " + GREEN + "安装成功" + RESET)
        return True
    except subprocess.CalledProcessError:
        print(f"  {package_name} " + RED + "安装失败" + RESET)
        return False

def get_package_version(package_name):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None

def check_python_version():
    version = sys.version_info
    required = (3, 6, 15)
    ok = version >= required
    detail = f"{version.major}.{version.minor}.{version.micro} (需要 >= 3.6.15)"
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

def check_files():
    results = []
    exists = os.path.exists('cassie_play.py')
    results.append(('cassie_play.py', exists, '存在' if exists else '缺失'))
    cassie_exists = os.path.exists('cassie/')
    if cassie_exists:
        words_exists = os.path.exists('cassie/words/')
        sounds_exists = os.path.exists('cassie/sounds/')
        if words_exists and sounds_exists:
            results.append(('cassie/', True, '存在，包含 words/ 和 sounds/ 子文件夹'))
        else:
            missing = []
            if not words_exists:
                missing.append('words/')
            if not sounds_exists:
                missing.append('sounds/')
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
        print(f"{YELLOW}words 文件夹有多余文件: {', '.join(sorted(words_extra))}")
    if sounds_extra:
        print(f"{YELLOW}sounds 文件夹有多余文件: {', '.join(sorted(sounds_extra))}")

    if not details:
        return True, "所有音频文件匹配"
    else:
        return False, "; ".join(details)

def install_ffmpeg():
    system = platform.system()
    if system == 'Darwin':
        print("  检测到 macOS，将尝试使用 Homebrew 安装 ffmpeg...")
        if not run_command('brew install ffmpeg', 'ffmpeg 安装'):
            print("  如果 Homebrew 未安装，请先安装 Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
    elif system == 'Windows':
        print("  检测到 Windows，请手动下载 ffmpeg 并添加到 PATH。")
        print("  下载地址: https://ffmpeg.org/download.html")
        print("  安装后请重启终端再运行此诊断工具。")
    else:
        print(f"  不支持的系统: {system}，请手动安装 ffmpeg")

def install_colorednoise():
    print("  正在安装 colorednoise 和 numpy...")
    if pip_install('colorednoise') and pip_install('numpy'):
        print("  colorednoise 和 numpy " + GREEN + "安装成功" + RESET)
    else:
        print("  " + RED + "安装失败" + RESET + "，请手动执行: pip install colorednoise numpy")

def main():
    os.chdir(PROJECT_BASE_PATH)
    print_section("CASSIE 广播生成器 - 诊断工具")
    print("开始时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    system = platform.system()
    overall_success = True
    pending_fixes = []

    print_subsection("操作系统详细检测")
    print(f"  系统名称: {system}")
    if system == 'Darwin':
        ver = platform.mac_ver()[0] or "未知"
        print(f"  macOS 版本: {ver}")
        print(f"  架构: {platform.machine()}")
        print(f"  处理器: {platform.processor()}")
        if ver and int(ver.split('.')[0]) < 13:
            print(f"  {YELLOW}提示: macOS 版本低于 13.0，浏览器系统音频共享可能受限{RESET}")
    elif system == 'Windows':
        ver = platform.version()
        print(f"  Windows 版本: {ver}")
        print(f"  架构: {platform.machine()}")
        if int(ver.split('.')[0]) < 10:
            print(f"  {YELLOW}提示: Windows 版本低于 10，浏览器系统音频共享可能受限{RESET}")
    else:
        print(f"  {RED}不支持的操作系统{RESET}")
        overall_success = False

    print_subsection("Python 版本检测")
    py_ok, py_detail, py_ver = check_python_version()
    print(f"  Python 版本: {py_ver}")
    print(f"  构建日期: {sys.version.split('[')[0] if '[' in sys.version else sys.version.split()[0]}")
    print(f"  编译器: {sys.version.split('[')[-1][:-1] if '[' in sys.version else '未知'}")
    print(f"  平台: {platform.platform()}")
    if not py_ok:
        print(f"  {RED}Python 版本过低，请升级到 3.6.5 或更高版本{RESET}")
        overall_success = False
    else:
        print(f"  {GREEN}Python 版本符合要求{RESET}")

    print_subsection("第三方库检测")
    libs = {
        'bottle': check_bottle,
        'pygame': check_pygame,
        'pydub': check_pydub,
        'colorednoise': check_colorednoise,
        'numpy': check_numpy,
        'cheroot': check_cheroot,
    }
    for name, func in libs.items():
        ok, detail = func()
        if ok:
            ver = get_package_version(name)
            print(f"  {GREEN}✓{RESET} {name}: 已安装 (版本: {ver})")
        else:
            print(f"  {RED}✗{RESET} {name}: 未安装 (需要最新版本)")
            overall_success = False
            if name in ('colorednoise', 'numpy'):
                pending_fixes.append((name, f'安装 {name}'))

    print_subsection("ffmpeg 检测")
    has_ffmpeg, ffmpeg_ver = check_ffmpeg()
    if has_ffmpeg:
        print(f"  {GREEN}✓{RESET} ffmpeg: 已安装 ({ffmpeg_ver})")
    else:
        print(f"  {RED}✗{RESET} ffmpeg: 未安装 (需要用于音频处理)")
        overall_success = False
        pending_fixes.append(('ffmpeg', '安装 ffmpeg'))

    print_subsection("必要文件和文件夹检测")
    file_results = check_files()
    for name, status, detail in file_results:
        if status:
            print(f"  {GREEN}✓{RESET} {name}: {detail}")
        else:
            print(f"  {RED}✗{RESET} {name}: {detail}")
            if name not in ('presets.json', 'word_list.json', 'sound_list.json'):
                overall_success = False

    print_subsection("音频文件匹配检测")
    audio_status, audio_detail = check_audio_files()
    if audio_status is None:
        print(f"  {audio_detail}")
        overall_success = False
    else:
        if audio_status:
            print(f"  {GREEN}✓{RESET} 音频文件匹配: {audio_detail}")
        else:
            print(f"  {RED}✗{RESET} 音频文件匹配: {audio_detail}")
            overall_success = False

    if pending_fixes:
        print("\n" + "=" * 70)
        print("检测到以下问题，可选择自动修复:")
        for i, (key, desc) in enumerate(pending_fixes, 1):
            print(f"  {i}. {desc}")

        for key, desc in pending_fixes:
            if key == 'ffmpeg':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    install_ffmpeg()
                    if check_ffmpeg()[0]:
                        overall_success = True
                    else:
                        print("  ffmpeg " + RED + "安装失败" + RESET)
            elif key == 'colorednoise':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    install_colorednoise()
                    if check_colorednoise()[0] and check_numpy()[0]:
                        overall_success = True
                    else:
                        print("  " + RED + "安装失败" + RESET)
            elif key == 'numpy':
                if ask_yes_no(f"  是否自动安装 {desc}？"):
                    if pip_install('numpy'):
                        overall_success = True
                    else:
                        print("  numpy " + RED + "安装失败" + RESET)
    else:
        print("\n没有检测到可自动修复的问题。")

    print("\n" + "=" * 70)
    print("诊断完成时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    if overall_success:
        print(GREEN + "检测成功" + RESET)
        print("所有项目均已通过检测，系统环境就绪。")
    else:
        print(RED + "检测失败" + RESET)
        print("部分问题需要手动处理，请参考上述提示。")
    print("=" * 70)

if __name__ == "__main__":
    main()