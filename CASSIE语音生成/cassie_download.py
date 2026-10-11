
import hashlib
import json
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
from rich import box

ASSET_URL = "https://github.com/BlueArchive-ba/CASSIE/releases/download/0.1/cassie.zip"

MIRRORS = [
    ("ghfast.top", "https://ghfast.top/"),
    ("gh-proxy.com", "https://gh-proxy.com/"),
    ("ghproxy.net", "https://ghproxy.net/"),
    ("ghfile.geekertao.top", "https://ghfile.geekertao.top/"),
    ("官方直连(GitHub)", ""),
]

ENV_MIRROR = "CASSIE_MIRROR"

KNOWN_SHA256 = "58399841a6c15555cab18ddaa82c46c23d35e88b7d26ba006361bd2f2fe2a00e"

def expected_sha():

    override = os.environ.get("CASSIE_SHA256", "").strip()
    if override:
        return override
    if os.environ.get("CASSIE_SKIP_SHA", "").strip() in ("1", "true", "yes"):
        return None
    return KNOWN_SHA256

RANGE_SIZE = 2 * 1024 * 1024
DEFAULT_THREADS = 12
MIN_THREADS = 1
MAX_THREADS = 32
CHUNK_SIZE = 256 * 1024
PROBE_SAMPLE = 1024 * 1024
PROBE_TIMEOUT = 12
RANGE_DEADLINE = 180

MIN_RATE = 24 * 1024
RATE_CHECK_EVERY = 3.0
RATE_GRACE = 12.0
READ_TIMEOUT = 30
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

console = Console()

def human_size(n):
    n = float(n)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"

def human_speed(bps):
    return human_size(bps) + "/s"

def build_mirror_list():

    mirrors = list(MIRRORS)
    override = os.environ.get(ENV_MIRROR, "").strip()
    if override:
        extra = [m.strip() for m in override.split(";") if m.strip()]
        mirrors = [(f"自定义{i+1}", m) for i, m in enumerate(extra)] + \
                  [m for m in mirrors if m[1] not in extra]
    return mirrors

def new_session():

    s = requests.Session()
    s.headers.update(UA)
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=4, pool_maxsize=4, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def probe_size(session, url, timeout=PROBE_TIMEOUT):

    try:
        r = session.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and r.headers.get("Content-Length"):
            return int(r.headers["Content-Length"]), True
    except requests.RequestException:
        pass

    try:
        r = session.get(url, headers={"Range": "bytes=0-0"},
                        timeout=timeout, stream=True)
        with r:
            if r.status_code == 206:
                cr = r.headers.get("Content-Range", "")
                if "/" in cr:
                    try:
                        return int(cr.rsplit("/", 1)[-1]), True
                    except ValueError:
                        pass
            if r.status_code == 200 and r.headers.get("Content-Length"):
                return int(r.headers["Content-Length"]), False
    except requests.RequestException:
        pass

    return None, False

def probe_one(name, prefix, expected_size=None):

    url = prefix + ASSET_URL
    session = new_session()
    info = {"name": name, "prefix": prefix, "url": url, "ok": False,
            "reason": "", "ttfb": None, "speed": None, "size": None}

    t0 = time.time()
    try:
        r = session.get(url, headers={"Range": "bytes=0-0"},
                        timeout=PROBE_TIMEOUT, stream=True)
        with r:
            if r.status_code != 206:
                info["reason"] = f"HTTP {r.status_code}（不支持 Range）"
                return info
            cr = r.headers.get("Content-Range", "")
            if "/" not in cr:
                info["reason"] = "缺 Content-Range"
                return info
            total = int(cr.rsplit("/", 1)[-1])
        info["ttfb"] = time.time() - t0
        info["size"] = total
    except Exception as e:
        info["reason"] = type(e).__name__
        return info

    if expected_size and total != expected_size:
        info["reason"] = f"大小不符 {human_size(total)}"
        return info

    start = max(0, total // 2)
    end = min(start + PROBE_SAMPLE - 1, total - 1)
    if end < start:
        info["reason"] = "文件过小"
        return info
    t1 = time.time()
    got = 0
    try:
        r = session.get(url, headers={"Range": f"bytes={start}-{end}"},
                        timeout=PROBE_TIMEOUT, stream=True)
        with r:
            if r.status_code != 206:
                info["reason"] = f"测速请求 HTTP {r.status_code}"
                return info
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    got += len(chunk)
    except Exception as e:
        if got <= 0:
            info["reason"] = "测速失败 " + type(e).__name__
            return info
        info["partial"] = True
        info["reason"] = "测速未跑完（" + type(e).__name__ + "），按已收字节估算"

    dt = max(time.time() - t1, 1e-6)
    if got <= 0:
        info["reason"] = "测速拿到 0 字节"
        return info
    info["speed"] = got / dt
    info["ok"] = True
    return info

def probe_mirrors(mirrors, expected_size=None, workers=None):

    workers = workers or min(len(mirrors), 8)
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]正在探测镜像可用性与速度", total=len(mirrors))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(probe_one, n, p, expected_size): (n, p)
                       for n, p in mirrors}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    n, p = futures[fut]
                    results.append({"name": n, "prefix": p, "url": p + ASSET_URL,
                                    "ok": False, "reason": type(e).__name__,
                                    "ttfb": None, "speed": None, "size": None})
                progress.update(task, advance=1)

    results.sort(key=lambda r: (not r["ok"], -(r["speed"] or 0)))
    return results

def show_probe_table(results):
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE_HEAVY)
    table.add_column("镜像", style="cyan")
    table.add_column("可用", justify="center")
    table.add_column("首字节", justify="right")
    table.add_column("实测速度", justify="right")
    table.add_column("说明", style="dim")
    for r in results:
        if r["ok"]:
            table.add_row(
                r["name"], "[green]✓[/green]",
                f"{r['ttfb']:.2f}s" if r["ttfb"] else "-",
                f"[green]{human_speed(r['speed'])}[/green]",
                r.get("reason", "") if r.get("partial") else "")
        else:
            table.add_row(r["name"], "[red]✗[/red]", "-", "-", r.get("reason", ""))
    console.print(table)

def preallocate(dest, total):

    if dest.exists() and dest.stat().st_size >= total:
        return
    if dest.exists():
        with open(dest, "r+b") as f:
            f.truncate(total)
    else:
        with open(dest, "wb") as f:
            f.truncate(total)

def load_state(path, range_size, total, dest):

    if not path.exists():
        return set()
    if not dest.exists() or dest.stat().st_size < total:
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("range_size") != range_size or data.get("total") != total:
            return set()
        return set(data.get("done", []))
    except (OSError, ValueError):
        return set()

def save_state(path, range_size, total, done):
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(
            {"range_size": range_size, "total": total, "done": sorted(done)}),
            encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass

def download_single(url, dest, total=None):

    session = new_session()
    with session.get(url, stream=True, timeout=(15, 60)) as r:
        r.raise_for_status()
        total = total or int(r.headers.get("Content-Length", 0)) or None
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(), DownloadColumn(),
            TransferSpeedColumn(), TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]下载中（单线程）", total=total)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))
    return True

class MirrorState:

    __slots__ = ("name", "url", "speed", "inflight", "errors",
                 "cooldown_until", "fetched", "ranges", "failed", "last_error",
                 "active")

    def __init__(self, name, url, speed):
        self.name = name
        self.url = url
        self.speed = max(float(speed or 0.0), 4096.0)
        self.inflight = 0
        self.errors = 0
        self.cooldown_until = 0.0
        self.fetched = 0
        self.ranges = 0
        self.failed = 0
        self.last_error = ""
        self.active = 0.0

def score_of(st, now):

    if st.cooldown_until > now:
        return -1.0
    return st.speed / (1.0 + st.inflight * 1.6)

def verify_file(path, total, expected_sha256=None):

    problems = []
    try:
        actual = path.stat().st_size
    except OSError as e:
        return [f"读不到文件: {e}"]

    if total and actual != total:
        problems.append(f"大小不符: {actual:,} != {total:,}")

    if path.suffix.lower() == ".zip" and actual > 4:
        with open(path, "rb") as f:
            magic = f.read(4)
        if magic[:2] != b"PK":
            problems.append(f"不是 zip：头 4 字节为 {magic.hex()}（应为 504b0304）")
        else:
            with open(path, "rb") as f:
                f.seek(max(0, actual - 65536))
                tail = f.read()
            if b"PK\x05\x06" not in tail:
                problems.append("zip 末尾找不到中央目录结束记录（PK\\x05\\x06），文件不完整")

    if expected_sha256:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h.update(chunk)
        got = h.hexdigest()
        if got.lower() != expected_sha256.strip().lower():
            problems.append(f"sha256 不符:\n     期望 {expected_sha256}\n     实际 {got}")

    return problems

def download_parallel(mirrors, dest, total, threads, expected_sha256=None):

    state_path = dest.with_suffix(dest.suffix + ".state")

    preallocate(dest, total)

    ranges = []
    for start in range(0, total, RANGE_SIZE):
        ranges.append((start, min(start + RANGE_SIZE - 1, total - 1)))
    total_ranges = len(ranges)

    done = load_state(state_path, RANGE_SIZE, total, dest)
    done = {i for i in done if 0 <= i < total_ranges}
    already_bytes = sum(ranges[i][1] - ranges[i][0] + 1 for i in done)
    if done:
        console.print(f"  [cyan]断点续传：跳过 {len(done)} 个已完成区间"
                      f"（{human_size(already_bytes)}）[/cyan]")

    lock = threading.Lock()
    queue = [i for i in range(total_ranges) if i not in done]
    failed_ranges = []
    failover_count = [0]

    usable = [m for m in mirrors if m.get("ok", True) and m.get("url")]
    usable.sort(key=lambda m: -(m.get("speed") or 0))
    if not usable:
        return False
    states = [MirrorState(m.get("name") or m["url"], m["url"], m.get("speed"))
              for m in usable]

    run_bytes = [0]
    run_ranges = [0]

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(), DownloadColumn(),
        TransferSpeedColumn(), TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    start_time = time.time()
    with progress:
        task = progress.add_task("[cyan]下载中", total=total)
        if already_bytes:
            progress.update(task, advance=already_bytes)

        def take_range():
            with lock:
                if not queue:
                    return None
                return queue.pop()

        def note_progress():

            with lock:
                left = len(queue)
            busy = sum(1 for s in states if s.inflight > 0)
            if left == 0:
                progress.update(task, description=(
                    "[cyan]下载中[/cyan] [yellow]· 正在收尾最后几个区间[/yellow]"))
            else:
                progress.update(task, description=(
                    f"[cyan]下载中[/cyan] [dim]· 剩余 {left} 个区间 · "
                    f"{busy} 个镜像在传[/dim]"))

        def choose_mirror(attempts=None):

            now = time.time()
            best, best_score = None, -1.0
            for st in states:
                if attempts and attempts.get(st, 0) >= 2:
                    continue
                sc = score_of(st, now)
                if sc > best_score:
                    best_score, best = sc, st
            return best if best is not None and best_score >= 0 else None

        def fetch_range(session, idx, st, force=False):

            start, end = ranges[idx]
            size = end - start + 1
            written = 0
            t0 = time.time()
            last_check = t0
            kind = "conn"
            try:
                r = session.get(st.url, headers={"Range": f"bytes={start}-{end}"},
                                timeout=(12, READ_TIMEOUT), stream=True)
                with r:
                    if r.status_code == 429:
                        kind = "busy"
                        raise RuntimeError("HTTP 429")
                    if r.status_code in (403, 404, 410):
                        kind = "fatal"
                        raise RuntimeError("HTTP %d" % r.status_code)
                    if r.status_code != 206:
                        raise RuntimeError("HTTP %d" % r.status_code)
                    with open(dest, "r+b") as f:
                        f.seek(start)
                        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                            if not chunk:
                                continue
                            f.write(chunk)
                            written += len(chunk)
                            progress.update(task, advance=len(chunk))
                            now = time.time()
                            if not force and now - last_check >= RATE_CHECK_EVERY:
                                last_check = now
                                spent = now - t0
                                if spent >= RATE_GRACE and written / spent < MIN_RATE:
                                    kind = "slow"
                                    raise RuntimeError(
                                        "速率仅 %.0f KB/s" % (written / spent / 1024))
                if written != size:
                    kind = "short"
                    raise RuntimeError("字节数不符 %d/%d" % (written, size))
                dt = max(time.time() - t0, 1e-6)
                with lock:
                    run_bytes[0] += written
                    st.fetched += written
                    st.ranges += 1
                    st.errors = 0
                    st.active += dt
                    st.speed = 0.72 * st.speed + 0.28 * (written / dt)
                return True, ""
            except Exception as e:
                if written:
                    progress.update(task, advance=-written)
                now = time.time()
                with lock:
                    st.errors += 1
                    st.failed += 1
                    st.last_error = str(e)[:30]
                    if kind == "fatal":
                        st.cooldown_until = now + 180.0
                        st.speed = max(st.speed * 0.1, 4096.0)
                    elif kind == "short":
                        st.cooldown_until = now + 120.0
                        st.speed = max(st.speed * 0.2, 4096.0)
                    elif kind == "busy":
                        st.cooldown_until = now + 25.0
                        st.speed = max(st.speed * 0.5, 4096.0)
                    elif kind == "slow":
                        st.cooldown_until = now + min(20.0 + 15.0 * st.failed, 120.0)
                        st.speed = max(st.speed * 0.45, 4096.0)
                    elif st.errors >= 2:
                        st.cooldown_until = now + 15.0
                        st.speed = max(st.speed * 0.4, 4096.0)
                return False, kind

        def worker(wid):
            session = new_session()
            while True:
                idx = take_range()
                if idx is None:
                    return
                attempts = {}
                kinds = []
                deadline = time.time() + RANGE_DEADLINE
                succeeded = False
                while True:
                    st = choose_mirror(attempts)
                    if st is None:
                        if all(attempts.get(s, 0) >= 2 for s in states):
                            break
                        if time.time() > deadline:
                            break
                        time.sleep(0.5)
                        continue
                    with lock:
                        st.inflight += 1
                    try:
                        ok, kind = fetch_range(session, idx, st)
                    finally:
                        with lock:
                            st.inflight -= 1
                    if ok:
                        succeeded = True
                        break
                    attempts[st] = attempts.get(st, 0) + 1
                    kinds.append(kind)
                    with lock:
                        failover_count[0] += 1
                    if time.time() > deadline:
                        break
                    time.sleep(min(0.6 * sum(attempts.values()), 3))

                if not succeeded and kinds and all(k == "slow" for k in kinds):
                    for st in sorted(states, key=lambda s: -s.speed):
                        with lock:
                            st.inflight += 1
                        try:
                            ok, _ = fetch_range(session, idx, st, force=True)
                        finally:
                            with lock:
                                st.inflight -= 1
                        if ok:
                            succeeded = True
                            break
                        with lock:
                            failover_count[0] += 1

                with lock:
                    if succeeded:
                        done.add(idx)
                        run_ranges[0] += 1
                    else:
                        failed_ranges.append(idx)
                note_progress()

        with ThreadPoolExecutor(max_workers=max(1, threads)) as ex:
            futures = [ex.submit(worker, i) for i in range(max(1, threads))]
            for fut in as_completed(futures):
                fut.result()

        elapsed = time.time() - start_time

    save_state(state_path, RANGE_SIZE, total, done)

    accounted = len(done) + len(failed_ranges)
    missing = [i for i in range(total_ranges) if i not in done and i not in failed_ranges]

    console.print()
    if len(states) > 1:
        table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        table.add_column("镜像", style="cyan")
        table.add_column("完成区间", justify="right")
        table.add_column("本次下载", justify="right")
        table.add_column("平均速度", justify="right")
        table.add_column("最近错误", style="dim")
        for st in sorted(states, key=lambda s: -s.fetched):
            spd = st.fetched / st.active if st.active > 0.05 else 0.0
            table.add_row(st.name, str(st.ranges), human_size(st.fetched),
                          human_speed(spd) if spd else "-",
                          st.last_error)
        console.print("  [bold]各镜像实际分到的活（运行时按实测吞吐动态分配）[/bold]")
        console.print(table)
    else:
        console.print(f"  使用镜像: [cyan]{states[0].name}[/cyan]")

    if failover_count[0]:
        console.print(f"  重试/切换镜像: [yellow]{failover_count[0]}[/yellow] 次")
    console.print(f"  下载耗时: [cyan]{elapsed:.0f}[/cyan] 秒")
    console.print(f"  本次下载: [cyan]{human_size(run_bytes[0])}[/cyan]"
                  f"，平均速度 [cyan]{human_speed(run_bytes[0] / max(elapsed, 1e-6))}[/cyan]")

    if failed_ranges or missing or accounted != total_ranges:
        console.print()
        console.print(Panel.fit(
            f"[bold red]下载不完整[/bold red]\n\n"
            f"区间总数 {total_ranges}，成功 {len(done)}，失败 {len(failed_ranges)}"
            + (f"，未领取 {len(missing)}" if missing else "") + "\n\n"
            "已完成的部分已经保留，[bold]直接重新运行本程序[/bold] 会从断点继续，\n"
            "不会重新下载已经拿到的数据。",
            border_style="red", box=box.ROUNDED,
        ))
        return False

    state_path.unlink(missing_ok=True)
    return True

def extract_with_progress(zip_path, extract_dir):
    with zipfile.ZipFile(zip_path, "r") as z:
        members = z.namelist()
        total = len(members)
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(), TaskProgressColumn(), TimeElapsedColumn(),
            console=console,
        )
        with progress:
            task = progress.add_task("[cyan]解压中", total=total)
            for member in members:
                progress.update(task, description=f"[cyan]解压: {member[:50]}")
                z.extract(member, extract_dir)
                progress.update(task, advance=1)

def ask_threads():
    console.print(Panel.fit(
        f"[bold cyan]并发设置[/bold cyan]\n\n"
        f"这是[bold]所有镜像合起来[/bold]的总并发数，不是每个镜像各开这么多。\n"
        f"分片只有 {human_size(RANGE_SIZE)} 大小，程序会按各镜像的[bold]实时实测速度[/bold]\n"
        f"把区间分配给它们：快的多分、变慢的少分、出错的进冷却。\n\n"
        f"所以并发给大一点（例如 16~24）才能让分配算法体现出镜像之间的快慢差别；\n"
        f"但也别太大，公约镜像容易被限流（返回 429）。\n"
        f"建议范围: [yellow]{MIN_THREADS}[/yellow] - [yellow]{MAX_THREADS}[/yellow]，"
        f"默认 [green]{DEFAULT_THREADS}[/green]",
        border_style="cyan", box=box.ROUNDED,
    ))
    while True:
        ans = Prompt.ask("  请输入并发数", default=str(DEFAULT_THREADS),
                         show_default=True).strip()
        try:
            n = int(ans)
            if MIN_THREADS <= n <= MAX_THREADS:
                return n
            console.print(f"  [red]请输入 {MIN_THREADS} 到 {MAX_THREADS} 之间的整数。[/red]")
        except ValueError:
            console.print("  [red]请输入一个整数。[/red]")

def main():
    console.print(Panel.fit(
        "[bold cyan]C.A.S.S.I.E. 音频包下载工具[/bold cyan]",
        box=box.DOUBLE, border_style="cyan",
    ))
    console.print()

    info = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    info.add_column("项目", style="cyan")
    info.add_column("值")
    info.add_row("文件", ASSET_URL)
    info.add_row("保存位置", str(Path.cwd()))
    console.print(info)
    console.print()

    zip_name = ASSET_URL.split("/")[-1]
    zip_path = Path.cwd() / zip_name
    state_path = zip_path.with_suffix(zip_path.suffix + ".state")
    total = None
    skip_download = False

    if zip_path.exists() and not state_path.exists():
        console.print(f"[yellow]检测到已存在文件:[/yellow] {zip_path}")
        with console.status("[bold cyan]正在校验已有文件...[/bold cyan]", spinner="dots"):
            problems = verify_file(zip_path, None, expected_sha())
        if not problems:
            console.print("  [green]已有文件完整，跳过下载。[/green]")
            skip_download = True
        else:
            console.print("  [red]已有文件校验未通过：[/red]")
            for p in problems:
                console.print("    • " + p)
            console.print("  [yellow]将删除并重新下载（已下载的区间位图不存在）。[/yellow]")
            try:
                zip_path.unlink()
            except OSError as e:
                console.print(f"[red]无法删除旧文件: {e}[/red]")
                return

    if not skip_download:
        threads = ask_threads()
        console.print()

        console.rule("[bold cyan]探测可用镜像[/bold cyan]")
        console.print("[dim]先看清哪些镜像活着、支不支持断点续传、哪个快，再决定从哪下。[/dim]")
        console.print()
        results = probe_mirrors(build_mirror_list())
        show_probe_table(results)

        usable = [r for r in results if r["ok"]]
        if not usable:
            console.print("[yellow]没有任何镜像通过探测，直接尝试官方地址。[/yellow]")
            console.print()
            total, ranged = probe_size(new_session(), ASSET_URL)
            try:
                if ranged and total:
                    ok = download_parallel([{"name": "官方直连(GitHub)", "url": ASSET_URL,
                                             "ok": True}], zip_path, total, threads)
                else:
                    ok = download_single(ASSET_URL, zip_path, total)
            except requests.RequestException as e:
                console.print(f"\n[red]下载失败:[/red] {e}")
                return
            if not ok:
                console.print(Panel.fit(
                    "[bold red]下载失败[/bold red]\n\n"
                    "建议：\n"
                    "  1. 检查网络连接后重试（已完成的部分会自动续传）\n"
                    "  2. 换一个镜像：设置环境变量后重跑\n"
                    "     [cyan]set CASSIE_MIRROR=https://ghfast.top/[/cyan]\n"
                    "  3. 手动下载：\n"
                    f"     [link]{ASSET_URL}[/link]",
                    border_style="red", box=box.ROUNDED,
                ))
                return
        else:
            best = usable[0]
            console.print(
                f"  实测最快: [green]{best['name']}[/green]"
                f"（{human_speed(best['speed'])}）；"
                f"共 {len(usable)} 个镜像会同时参与，按实时速度分配区间")
            console.print()
            console.rule("[bold cyan]开始下载[/bold cyan]")
            total = best["size"]
            try:
                ok = download_parallel(usable, zip_path, total, threads)
            except KeyboardInterrupt:
                console.print("\n[yellow]已中断。已完成的部分会保留，重跑可续传。[/yellow]")
                raise
            if not ok:
                console.print()
                console.print("[yellow]可以再次运行本程序继续下载。[/yellow]")
                return

    console.print()
    sha = expected_sha()
    with console.status("[bold cyan]正在校验文件完整性...[/bold cyan]", spinner="dots"):
        problems = verify_file(zip_path, total, sha)

    if problems:
        console.print()
        console.print(Panel.fit(
            "[bold red]文件校验未通过[/bold red]\n\n"
            + "\n".join("  • " + p for p in problems) + "\n\n"
            "这说明下载到的内容不完整或不对。\n"
            "[bold]不要解压它[/bold]：解压程序只会告诉你「压缩包损坏」。\n\n"
            f"可以直接重新运行本程序，会从断点继续；\n"
            f"或者删掉 [cyan]{zip_path.name}[/cyan] 与它的 [cyan].state[/cyan] 文件重下。",
            border_style="red", box=box.ROUNDED,
        ))
        return

    console.print("  [green]完整性校验通过"
                  + ("（大小 + zip 结构" + (" + sha256" if sha else "") + "）"
                     if zip_path.suffix.lower() == ".zip" else "（大小）")
                  + "[/green]")

    console.print()
    actual = zip_path.stat().st_size
    console.print(Panel.fit(
        f"[bold green]{'文件已就绪' if skip_download else '下载完成'}[/bold green]\n\n"
        f"文件: [cyan]{zip_path}[/cyan]\n"
        f"大小: [cyan]{human_size(actual)}[/cyan]"
        + ("\n[dim]（本次直接复用了已存在的文件，没有重新下载）[/dim]"
           if skip_download else ""),
        border_style="green", box=box.ROUNDED,
    ))
    console.print()

    console.rule("[bold cyan]解压选项[/bold cyan]")
    if not Confirm.ask("[bold]是否自动解压？[/bold]", default=True):
        console.print()
        console.print("[yellow]已跳过解压。压缩包保留在:[/yellow]")
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
        console.print("[dim]可删除后重新运行；不要直接改扩展名。[/dim]")
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
        border_style="green", box=box.DOUBLE,
    ))
    console.print()
    console.rule("[bold cyan]程序结束[/bold cyan]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]已中断。[/yellow]")
        sys.exit(1)

