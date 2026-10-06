# C.A.S.S.I.E. 广播生成器

给游戏 **SCP: Secret Laboratory** 用的离线广播生成工具。把预先录好的单词音频
（WAV）按文本拼接成完整广播——**不是语音合成**，所有声音都来自本地素材。

目标是与游戏原版广播 **100% 一致**，所以素材和拼接规则都以还原为准。

---

## 仓库结构

```text
.
├── CASSIE历代版本/
│   ├── 0.3 及以上使用教程/     # 图文使用教程（含素材图）
│   ├── CASSIE V 0.2/          # 历史版本
│   ├── CASSIE V 0.3/          # 历史版本
│   └── CASSIE V 1.0.0/        # 当前版本 ← 一般从这里开始
├── CASSIE语音生成/
│   ├── cassie_download.py     # 音频素材下载器（素材不随仓库分发）
│   ├── 须知！！！.txt
│   └── python 3.10/ 3.6.5/    # 对应 Python 版本的运行环境与打包
├── bench2.py                  # 以下为走廊混响（FDN）实现期的研究脚本，
├── bench_reverb.py            # 用来量化纯 Python 逐样本循环与 numpy 分块
├── iso9613_air.py             # 的差异、空气吸收、单极点滤波器数值稳定性、
├── onepole_stability.py       # 以及 RT60 与反馈增益的换算关系。
└── verify_gain.py             # 不属于运行时代码，保留以备复现结论。
```

**当前版本在 [`CASSIE历代版本/CASSIE V 1.0.0/`](CASSIE历代版本/CASSIE%20V%201.0.0/)**，
它的 [`README.md`](CASSIE历代版本/CASSIE%20V%201.0.0/README.md) 是完整的安装、
使用、API 与实现说明。**请先读那一份。**

---

## 快速开始

```bash
cd "CASSIE历代版本/CASSIE V 1.0.0"

pip install rich                 # 诊断工具自身依赖
python diagnostic.py             # 检查依赖、ffmpeg 与素材，可自动安装缺失库
python cassie_play.py            # 启动
```

然后打开 <http://localhost:8080/cassie_play>。

### 音频素材

**素材不在仓库里**（体积大，且属于游戏原素材）。请运行下载器获取：

```bash
cd CASSIE语音生成
python cassie_download.py
```

下载器需要能正常访问 GitHub。素材会安装到版本目录下的 `cassie/`
（`words/` 单词、`sounds/` 铃声、`alarms/` 警报）。

---

## 环境要求

- Windows / macOS / Linux
- **Python 3.10.15 及以上**，**3.13 及以上不支持**
- `bottle`、`cheroot`、`pygame`、`pydub`、`numpy`、`colorednoise`、`rich`
- `ffmpeg`（pydub 处理音频用，需加入 PATH）

---

## 功能概览

- 浏览器界面：实时播放、WAV 导出、拼写检查、预设管理、单词查找
- 广播指令：`[gap]`、`[speed]`、`[channel]`、`[channl]`、`[error]`、
  `[stutter]`、`[preset:名字]`，以及 `mtf` / `[cd]` / `[warhead]` 等快捷广播
- 数字朗读、多声道、背景铃声与特殊铃声
- **走廊混响**：8 条互质延迟线的反馈延迟网络（FDN），可调预延迟、走廊尺度、
  RT60、高频吸收、扩散度、湿声比例
- **耗时控制**：七档质量档次 + 逐词/整句两种处理模式（详见版本目录的 README）
- **完整 HTTP API**（`/api/v1`）与 Python 客户端 `cassie_api.py`，
  网页能做的事都能用代码完成
- 中英双语界面，服务端返回的文案也跟随语言
- 合成与播放的**真实进度条**

---

## 文档

| 文档 | 内容 |
|---|---|
| [版本 README](CASSIE历代版本/CASSIE%20V%201.0.0/README.md) | 安装、用法、空间效果、进度与预设 |
| [docs/help.html](CASSIE历代版本/CASSIE%20V%201.0.0/docs/help.html) | 面向普通用户的帮助（也可在服务里打开 `/help`） |
| [docs/developer.html](CASSIE历代版本/CASSIE%20V%201.0.0/docs/developer.html) | 架构、音频实现、自定义指南（`/developer`） |
| [docs/api.md](CASSIE历代版本/CASSIE%20V%201.0.0/docs/api.md) | HTTP API、参数表、进度事件、手动验证清单 |
| [0.3 及以上使用教程](CASSIE历代版本/0.3%20及以上使用教程/CASSIE%20v0.3广播生成器使用教程.html) | 图文入门教程 |

---

## 说明

- 本项目为交流学习用途。音频素材版权归 **Northwood Studios**（SCP:SL）所有，
  因此不随仓库分发。
- 仓库**不包含自动化测试**；改动后的验证方式见 `docs/api.md` 的「手动验证」一节。
