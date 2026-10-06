"""创建三个 GitHub Release，并上传对应的 zip 作为附件。

说明：仓库里 CASSIE语音生成/ 下的三个 zip 是随包分发的运行版本，
内容与仓库源码同源（但可能略旧），按用户要求直接用作发布附件。

tags: v0.2 / v0.3 / v1.0.0
"""
import os
import subprocess
import sys

REPO = 'BlueArchive-ba/CASSIE-Broadcast-Generator'
ROOT = os.path.dirname(os.path.abspath(__file__))
ZIP_DIR = os.path.join(ROOT, 'CASSIE语音生成')

RELEASES = [
    {
        'tag': 'v0.2',
        'title': 'CASSIE V 0.2',
        'zip': os.path.join(ZIP_DIR, 'python 3.6.5', 'CASSIE V 0.2.zip'),
        'notes': """第一个公开版本。

## 内容
- 数字朗读、广播铃声、特殊铃声、多声道播放、WAV 导出
- 广播空间效果与高级设置
- 预设管理、系统声音监听
- 初步的广播指令（`mtf`、`[warhead:...]` 等）

## 使用
1. 解压后运行 `python diagnostic.py` 检查环境
2. 运行 `python cassie_play.py`，浏览器打开 <http://localhost:8080/cassie_play>

**音频素材不包含在本包内**，请下载仓库的 `CASSIE语音生成/cassie_download.py` 获取。
""",
    },
    {
        'tag': 'v0.3',
        'title': 'CASSIE V 0.3',
        'zip': os.path.join(ZIP_DIR, 'python 3.10', 'CASSIE V 0.3.zip'),
        'notes': """界面与指令体系重构版本。

## 相比 0.2 的变化
- 新增特殊铃声、浏览器共享系统声音的实时音量监听
- 新增开发者技术文档
- 完成 WAV 直接导出与 `[channl]` 指令
- 修复语速 > 0 时单词间无间隔、`[gap]` 失效的问题
- 更新广播空间效果
- 重构项目文件夹、代码与样式

## 使用
1. 解压后运行 `python diagnostic.py` 检查环境
2. 运行 `python cassie_play.py`，浏览器打开 <http://localhost:8080/cassie_play>

**音频素材不包含在本包内**，请下载仓库的 `CASSIE语音生成/cassie_download.py` 获取。

> 注：本包含 Python 3.10 运行环境说明；0.2 对应 Python 3.6.5。
""",
    },
    {
        'tag': 'v1.0.0',
        'title': 'CASSIE V 1.0.0',
        'zip': os.path.join(ZIP_DIR, 'python 3.10', 'CASSIE V 1.0.0.zip'),
        'notes': """当前版本。后端单文件、前端拆分，并开放完整 HTTP API。

## 主要变化
- 删除 `[alert]` 指令；修复 `[cd]` 指令的 bug
- 前端从 `cassie_play.py` 拆分到 `static/app.js`，后端保持单文件
- **新增完整 HTTP API（`/api/v1`）**与 Python 客户端 `cassie_api.py`，
  网页能做的事都能用代码完成
- 走廊混响新增**七档耗时控制**与**逐词 / 整句**两种处理模式
- 新增合成与播放的**真实进度条**
- 新增 `[preset:名字]`，预设之间可以互相引用
- 高级设置落盘到 `settings.json`，关掉程序不再丢失
- 修复开启空间效果播放一次后进程退出的问题（空音频哨兵事件）
- 修复 pydub 文件句柄泄漏导致的 `ResourceWarning` 刷屏

## 环境要求
- **Python 3.10.15 及以上**，**3.13 及以上不支持**
- `bottle` `cheroot` `pygame` `pydub` `numpy` `colorednoise` `rich`，以及 `ffmpeg`

## 使用
1. 解压后运行 `python diagnostic.py`（可自动安装缺失依赖）
2. 运行 `python cassie_play.py`，浏览器打开 <http://localhost:8080/cassie_play>

**音频素材不包含在本包内**，请下载仓库的 `CASSIE语音生成/cassie_download.py` 获取。

## 完整文档
见仓库内 `CASSIE历代版本/CASSIE V 1.0.0/`：
[README](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/blob/main/CASSIE%E5%8E%86%E4%BB%A3%E7%89%88%E6%9C%AC/CASSIE%20V%201.0.0/README.md) ·
[API 文档](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/blob/main/CASSIE%E5%8E%86%E4%BB%A3%E7%89%88%E6%9C%AC/CASSIE%20V%201.0.0/docs/api.md) ·
[使用帮助](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/blob/main/CASSIE%E5%8E%86%E4%BB%A3%E7%89%88%E6%9C%AC/CASSIE%20V%201.0.0/docs/help.html)
""",
    },
]


def run(args, label):
    result = subprocess.run(args, capture_output=True, text=True,
                            encoding='utf-8', errors='ignore')
    ok = result.returncode == 0
    print('  {} {}'.format('OK  ' if ok else 'FAIL', label))
    output = (result.stdout or '').strip() or (result.stderr or '').strip()
    if output:
        for line in output.splitlines()[:6]:
            print('        ' + line)
    return ok


for item in RELEASES:
    print('=== {} ==='.format(item['title']))
    if not os.path.exists(item['zip']):
        print('  !! 找不到 zip: {}'.format(item['zip']))
        continue

    notes_path = os.path.join(os.environ.get('TEMP', '/tmp'),
                              'release_{}.md'.format(item['tag']))
    with open(notes_path, 'w', encoding='utf-8') as handle:
        handle.write(item['notes'])

    # 已存在就先删掉，保证可重复执行
    subprocess.run(['gh', 'release', 'delete', item['tag'], '--repo', REPO,
                    '--yes', '--cleanup-tag'],
                   capture_output=True, text=True)

    run(['gh', 'release', 'create', item['tag'],
         '--repo', REPO,
         '--title', item['title'],
         '--notes-file', notes_path,
         item['zip']],
        '{}.zip  ({:,} B)'.format(os.path.basename(item['zip']),
                                  os.path.getsize(item['zip'])))
    print()
