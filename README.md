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
│   └── 须知！！！.txt
```

**当前版本在 [`CASSIE历代版本/CASSIE V 1.0.0/`](CASSIE历代版本/CASSIE%20V%201.0.0/)**，
它的 [`README.md`](CASSIE历代版本/CASSIE%20V%201.0.0/README.md) 是完整的安装、
使用、API 与实现说明。**请先读那一份。**

---

## 快速开始

> ### ⚠️ 先下载音频素材
>
> 本仓库和 [发布包](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases)
> **都不包含音频素材**，必须单独下载，否则程序无法生成任何广播。
>
> ```bash
> cd CASSIE语音生成
> python cassie_download.py      # 需要能访问 GitHub
> ```
>
> 素材会安装到版本目录下的 `cassie/`。
> 忘了这一步也不要紧：程序启动时会在终端打印醒目提示，网页上也会显示提示条并给出期望目录，
> `python diagnostic.py` 同样会提醒。

```bash
cd "CASSIE历代版本/CASSIE V 1.0.0"

pip install rich                 # 诊断工具自身依赖
python diagnostic.py             # 检查依赖、ffmpeg 与素材，可自动安装缺失库
python cassie_play.py            # 启动
```

然后打开 <http://localhost:8080/cassie_play>。

### 音频素材在哪

素材不随仓库分发（体积大，且属于游戏原素材）。获取方式：

1. **推荐**：运行 `CASSIE语音生成/cassie_download.py`，自动下载并解压到正确位置
2. 手动从 [发布页](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases) 下载

程序会**主动检查**素材是否就位，三种情况下都会明确告诉你：

| 时机 | 表现 |
|---|---|
| 启动服务 | 终端打印红框提示，含期望目录与下载命令 |
| 打开网页 | 页面上方显示提示条，并给出完整路径 |
| 运行诊断 | `diagnostic.py` 输出专门的提示块 |

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
| [版本对比](CASSIE历代版本/VERSIONS.md) | **三个版本的代码级差异**，附「该选哪一版」 |
| [版本 README](CASSIE历代版本/CASSIE%20V%201.0.0/README.md) | 安装、用法、空间效果、进度与预设 |
| [docs/help.html](CASSIE历代版本/CASSIE%20V%201.0.0/docs/help.html) | 面向普通用户的帮助（也可在服务里打开 `/help`） |
| [docs/developer.html](CASSIE历代版本/CASSIE%20V%201.0.0/docs/developer.html) | 架构、音频实现、自定义指南（`/developer`） |
| [docs/api.md](CASSIE历代版本/CASSIE%20V%201.0.0/docs/api.md) | HTTP API、参数表、进度事件、手动验证清单 |
| [0.3 及以上使用教程](CASSIE历代版本/0.3%20及以上使用教程/CASSIE%20v0.3广播生成器使用教程.html) | 图文入门教程 |

---

## 历史版本

三个版本都在 [Releases](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases)
提供打包好的 zip：

| 版本 | 特点 | 音频素材 |
|---|---|---|
| [V 1.0.0](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases/tag/v1.0.0) | 反馈网络混响、15 个 HTTP API、进度条、中英双语 | 需单独下载 |
| [V 0.3](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases/tag/v0.3) | 补全指令与文档，空间效果仍为多抽头延迟 | 需单独下载 |
| [V 0.2](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases/tag/v0.2) | 最早版本，只需 Python 3.6.5 | 需单独下载 |

功能差异见 [版本对比](CASSIE历代版本/VERSIONS.md)；
代码差异用 GitHub 自带的 Compare 查看：

- [V 0.2 → V 0.3](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/compare/v0.2...v0.3)
- [V 0.3 → V 1.0.0](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/compare/v0.3...v1.0.0)
- [V 0.2 → V 1.0.0（全部）](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/compare/v0.2...v1.0.0)

**三个版本都不含音频素材**，都必须先跑 `CASSIE语音生成/cassie_download.py`，
或从 [素材仓库](https://github.com/BlueArchive-ba/CASSIE) 下载。

---

## 说明

- 本项目为交流学习用途。音频素材版权归 **Northwood Studios**（SCP:SL）所有，
  因此不随仓库分发。
- 仓库**不包含自动化测试**；改动后的验证方式见 `docs/api.md` 的「手动验证」一节。
