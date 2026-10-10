# C.A.S.S.I.E. 广播生成器
# 如果你是第一次接触Python（或者这种项目），请先阅读 CASSIE v0.3广播生成器使用教程.html 。双击打开即可

赞助方：DeepSeek（）。

# 非常感谢 情雨QingYu 的支持！！！
## B站：https://space.bilibili.com/3537124538189987
## bug反馈/粉丝群：852101808
## 感谢您对本项目的支持！！！
## 此项目不兼容 Pyhton 3.13 或更高版本！！！

## 项目简介

C.A.S.S.I.E. 是一个本地运行的广播生成工具，用于把 `cassie/words/` 中的 WAV 单词素材组合成完整广播。项目提供浏览器界面，支持实时播放、WAV 导出、指令解析、数字朗读、铃声、多声道、预设和广播空间效果。

项目不依赖在线语音服务。广播内容由本地音频素材决定，适合离线创作、测试和自定义游戏广播。

## 运行环境

- Windows、macOS 或 Linux
- Python 3.6.15 及以上，建议使用 Python 3.10+ 
- `bottle`
- `cheroot`
- `pygame`
- `pydub`
- `numpy`
- `colorednoise`
- `ffmpeg`（用于 pydub 的音频处理）
- `rich`
- 可播放 WAV 的音频输出设备

安装依赖：

除 ffmpeg 和 rich 外，优先运行诊断工具。诊断工具会逐项检查缺失的第三方库，并询问是否使用当前 Python 自动安装：

```bash
python diagnostic.py
```

如果不使用自动安装，也可以手动执行：

```bash
python -m pip install bottle cheroot pygame pydub numpy colorednoise
```

ffmpeg 不由诊断工具自动安装。请从 ffmpeg 官方渠道安装，并确保 `ffmpeg` 已加入系统 PATH。
rich 的安装是第一步，在终端运行：
```bash
pip install rich
```

在运行了 diagnostic.py 以后需要再运行 cassie_download.py ，这需要你最好有一个可以快速访问国外网站（GitHub）的网络环境

启动：

```bash
python cassie_play.py
```

然后访问 <http://localhost:8080/cassie_play>。



## 项目结构

```text
项目根目录/
├── cassie_play.py       # Web 服务、解析、实时播放和导出
├── diagnostic.py        # 环境与素材诊断
├── docs/
│   ├── help.html        # 普通用户帮助页
│   └── developer.html   # 开发者技术文档
├── tools/
│   ├── test.py          # 素材差异检查
│   ├── test_2.py        # 更新素材索引
│   └── word_search/     # 单词查找页面
├── presets.json         # 用户预设
├── word_list.json       # 单词素材索引
├── sound_list.json      # 铃声素材索引
├── cassie/              # 需要下载
│   ├── words/           # 单词、数字、故障音和特殊音频
│   └── sounds/          # 普通铃声与背景铃声
├── static/style.css     # 主页面样式
```

## 音频素材

`cassie/words/` 中的文件名就是可输入的单词名，例如 `security.wav`。单个字母使用 `_a.wav` 形式，北约音标会映射到字母音频。`ic_start.wav` 和 `ic_stop.wav` 可作为特殊开始和结束铃声。

`cassie/sounds/` 中的 `bg_数字.wav` 是按广播时长匹配的背景铃声，普通特殊铃声包括 `bell_start.wav` 和 `bell_end.wav`。

添加新单词后可运行 `python tools/test_2.py` 更新素材列表；添加新铃声也会同步更新 `sound_list.json`。

## 关于版本

### V 1.0.0
- 删除了 [alert] 指令
- 修复了有关 [cd] 指令的bug
- 将cassie语音音频分离了项目

### V 0.3

- 新增了新的特殊铃声。
- 新增了浏览器共享系统声音的实时音量监听。
- 新增了开发者文档
- 完成了 WAV 直接导出。
- 完成了 [channl] 指令。
- 修复了语速大于0时单词之间没有间隔的问题。
- 修复了 [gap] 指令失效的问题。
- 更新了广播空间效果。
- 更新了 须知 与 帮助 文件的内容。
- 重构了项目文件夹。
- 重构了项目代码。
- 重构了项目样式。

### V 0.2

- 新增了数字朗读、广播铃声、特殊铃声、多声道播放和 WAV 导出。
- 新增了 Warhead、channl(未完成) 等广播指令。
- 新增了广播空间效果和高级设置。
- 新增了预设管理、系统声音监听和开发者技术文档。
- 修复了播放与导出冲突、铃声竞态、数字音质和播放结束清理问题。
- 新增了以下音频文件：
```text
  100s.wav
  110s.wav
  120s.wav
  30s.wav
  40s.wav
  50s.wav
  60s.wav
  70s.wav
  80s.wav
  90s.wav
  big door open1.wav
  dead man.wav
  defense module updated.wav
  elevator door open.wav
  final flash of existence orchestral version scp secret laboratory ost.wav
  helicopter_1.wav
  ic_start.wav
  ic_stop.wav
  lethal force authorized.wav
  menu Intense.wav
  point.wav
  the chaos insurgency announce.wav
  warhead cancelled.wav
  warhead resume.wav
  warhead start.wav
  xmas bouncyballs.wav
  xmas epsilon11.wav
  xmas hasentered.wav
  xmas jinglebells.wav
  xmas scpsubjects.wav
```

### V 0.1

- 第一个版本。
