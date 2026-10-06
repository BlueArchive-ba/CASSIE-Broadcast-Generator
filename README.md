# 如果你是第一次接触 Python（或者这种项目），请先阅读本目录之外的
# `CASSIE历代版本/0.3 及以上使用教程/CASSIE v0.3广播生成器使用教程.html`，双击打开即可。

# C.A.S.S.I.E. 广播生成器

赞助方：DeepSeek。

# 非常感谢 情雨QingYu 的支持！！！
## B站：https://space.bilibili.com/3537124538189987
## bug反馈/粉丝群：852101808
## 感谢您对本项目的支持！！！
## 此项目不兼容 Python 3.13 或更高版本！！！

## 项目简介

C.A.S.S.I.E. 是一个本地运行的广播生成工具，用于把 `cassie/words/` 中的 WAV 单词素材组合成完整广播。项目提供浏览器界面，支持实时播放、WAV 导出、指令解析、数字朗读、铃声、多声道、预设和广播空间效果。

项目不依赖在线语音服务。广播内容由本地音频素材决定，适合离线创作、测试和自定义游戏广播。

## 运行环境

- Windows、macOS 或 Linux
- **Python 3.10.15 及以上**；**3.13 及以上不受支持**
  （诊断工具会按 `3.10.15` 判定，低于此版本会被判为版本过低）
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

`rich` 是诊断工具自身的依赖，需要先装，在终端运行：
```bash
pip install rich
```
在运行 diagnostic.py 前需要运行音频素材下载器，这需要你最好有一个可以快速访问国外网站（GitHub）的网络环境。
下载器位于仓库的 `CASSIE语音生成/` 目录（内含 `cassie_download.py` 与对应 Python 版本的运行环境），
运行后素材会安装到本目录的 `cassie/`。

> **素材不随仓库和发布包分发**，必须单独下载，否则程序无法生成任何广播。
> 缺素材时启动会在终端打印醒目提示，网页上也会显示同样的提示条并给出期望目录。
> 不想用下载器也可以从
> [发布页](https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases) 获取。

除 ffmpeg 和 rich 外，优先运行诊断工具。诊断工具会逐项检查缺失的第三方库，并询问是否使用当前 Python 自动安装：

```bash
python diagnostic.py
```

如果不使用自动安装，也可以手动执行：

```bash
python -m pip install bottle cheroot pygame pydub numpy colorednoise
```

ffmpeg 不由诊断工具自动安装。请从 ffmpeg 官方渠道安装，并确保 `ffmpeg` 已加入系统 PATH。



启动：

```bash
python cassie_play.py
```

然后访问 <http://localhost:8080/cassie_play>。



## 项目结构

```text
项目根目录（CASSIE V 1.0.0）/
├── cassie_play.py       # Web 服务、API 路由、解析、实时播放和导出（全部后端逻辑）
├── cassie_api.py        # Python 客户端（进程内 / 远程两种模式）
├── diagnostic.py        # 环境与素材诊断
├── cassie_play.html     # 主页面结构
├── docs/
│   ├── help.html        # 普通用户帮助页
│   ├── developer.html   # 开发者技术文档
│   └── api.md           # HTTP API 与 Python 客户端参考
├── examples/
│   └── api_usage.py     # API 用法示例
├── tools/
│   ├── test.py          # 素材差异检查（列出 words/sounds 里新增但未入索引的文件）
│   ├── test_2.py        # 更新素材索引（添加单词/铃声后运行）
│   └── word_search/     # 单词查找页面
├── presets.json         # 用户预设
├── settings.json        # 高级设置（保存后自动生成，关掉程序也不会丢）
├── word_list.json       # 单词素材索引
├── sound_list.json      # 铃声素材索引
├── cassie/              # 需要下载（见上文「运行环境」）
│   ├── words/           # 单词
│   └── sounds/          # 普通铃声与背景铃声
└── static/
    ├── glass.css        # 全站设计系统：黑底白字令牌、蓝红点缀、平面表面（.panel / .glass）、控件
    ├── style.css        # 主页面版式（含导出/播放进度条）
    ├── advanced.css     # 高级设置面板版式
    ├── docs.css         # 帮助页与开发者文档共用版式
    ├── wordsearch.css   # 单词查找页版式
    ├── i18n.js          # 中英切换引擎：语言判定、词表注册、DOM 刷新、切换胶囊
    ├── i18n-strings.js  # 主页面中英词表
    ├── i18n-docs.js     # 帮助页 + 开发者文档共用中英词表
    ├── i18n-wordsearch.js  # 单词查找页中英词表
    └── app.js           # 主页面交互逻辑
```



## API

网页界面能做的事都可以通过接口完成：查询运行状况、读取素材库、校验文本、
解析时间线、合成 WAV、播放、停止、读写参数与预设。

启动服务后：

```bash
curl http://127.0.0.1:8080/api/v1/health
curl -X POST "http://127.0.0.1:8080/api/v1/synthesize?download=1" \
     -H "Content-Type: application/json" \
     -d '{"text":"attention , all personnel .","reverb_decay_time":9,"reverb_wet":0.6}' \
     -o broadcast.wav
```

Python 调用支持两种模式，方法名与参数完全一致：

```python
import sys
sys.path.insert(0, r'C:\path\to\CASSIE V 1.0.0')
from cassie_api import CassieClient

# 进程内：不需要启服务
with CassieClient.local() as cassie:
    cassie.save('attention , all personnel .', 'out.wav',
                room_size=2.0, decay_time=7.0, wet=0.5)

# 远程：连到已经跑起来的服务
with CassieClient.remote('http://127.0.0.1:8080') as cassie:
    cassie.play('mtf epsilon 11')
    cassie.wait_until_done()
    open('x.wav', 'wb').write(cassie.synthesize_bytes('warhead 90 start'))
```

完整接口清单、参数表与错误码见 [`docs/api.md`](docs/api.md)，
可运行示例见 `python examples/api_usage.py`。

设置了环境变量 `CASSIE_API_KEY` 时，`/api/v1/*` 下的全部接口都需要
请求头 `X-API-Key` 或查询参数 `api_key`。
网页端自用的路由（`/play`、`/export_progress`、`/export`、预设与设置等）
**不受 Key 保护**，只适合本机使用；详见 [`docs/api.md`](docs/api.md)。

接口返回的文案支持中英两种语言，用查询参数 `?lang=zh|en` 或请求头
`X-Cassie-Lang` 指定，不传时是中文。详见 [`docs/api.md`](docs/api.md)。

## 界面语言

界面右上角有一个中英切换胶囊，主页面、帮助页、技术文档、单词查找页共用同一个开关，
选择会记在浏览器里（`localStorage` 的 `cassie.lang`），下次打开保持。

- 切换是**整站级**的：按钮、标签、终端状态、高级设置里的全部参数说明、
  弹窗、预设列表、设备列表都会跟着变。
- 由后端生成的文案（API 错误消息、播放日志、质量档次说明）也会切换——
  前端把当前语言随每个请求发给后端，两边文案不会各说各话。
- 输出终端里**已经打印过**的历史日志不会回溯翻译：那是本次会话的运行记录，
  改语言时把历史重写掉反而会让人对不上当时到底发生了什么。
- 想用链接直接指定语言，在地址后加 `?lang=en`（或 `?lang=zh`）即可，
  例如 `http://localhost:8080/cassie_play?lang=en`。

## 走廊混响

高级设置里的“广播空间效果”包含一套走廊混响，用反馈延迟网络（FDN）实现：
8 条互质延迟线 + Hadamard 反馈矩阵，每条线在反馈回路内串一个一阶低通。

- **预延迟**：直达声与第一次反射之间的间隔。
- **走廊尺度**：反射间距的缩放系数。
- **混响时长（RT60）**：拖尾衰减 60 dB 所需的时间，走廊建议 3 ~ 8 秒。
- **高频吸收**：4 kHz 相对低频的衰减时间比。真实走廊里高频被空气与墙面吸收得更快，
  所以这个值小于 1 时高频拖尾更短；`4000` 及以上表示高频与低频一样长，
  `500` 表示高频只有低频的约 40%（可实现的最快吸收）。低频的 RT60 始终等于设定值。
- **扩散度**：反馈矩阵向单位矩阵插值的程度，越低越像离散回声。
- **尾音亮度（目前未生效）**：文档与界面上曾作为"提升拖尾中高频占比"的参数提供，
  但当前实现里 FDN 并未读取它——改动该值不会改变输出。保留是为了兼容已保存的
  `settings.json` 与 API 请求体，**不要依赖它**。真正决定高频衰减的是"高频吸收"。
- **混响湿声**：混响在总输出中的占比。

混响作用在**整段广播**上而不是逐个单词。单词的位置与间隔只由文本、语速和音高决定，
**开启空间效果不会改变语速与单词间隔**，只在末尾多出一段拖尾：混响尾巴自然叠到下一个
单词上，而不是把后面的单词往后推。参数改动后冲激响应相关的缓存会自动失效。

### 处理开销

空间效果是最重的一步，高级设置里有两组开关可以降耗时：

**减少耗时（七档）**：通过调大内部块长、收短拖尾来换速度。块长只影响内部
迭代次数、不改变声音；收短拖尾会改变听感，尾部会自动淡出以免硬切。第 0 档
等于历史行为。

| 档 | 名称 | 拖尾长度 | 单次耗时 | 相对 |
|---|---|---|---|---|
| 0 | 原始 | 1942 ms | 82 ms | 1.00x |
| 1 | 轻度 | 1557 ms | 51 ms | 0.62x |
| 2 | 中度 | 1007 ms | 32 ms | 0.39x |
| 3 | 最大加速 | 567 ms | 22 ms | 0.27x |
| 4 | 激进 | 347 ms | 16 ms | 0.20x |
| 5 | 极限 | 182 ms | 15 ms | 0.18x |
| 6 | 单声道混响 | 182 ms | 11 ms | 0.13x |

第 6 档在极限档基础上把立体声混响合成单声道（干声仍是立体声，只是拖尾
左右相同、失去宽度），换来近一倍的额外加速。再往下已经没有空间——单词本体
本身就是必须处理的样本，约 12ms/声道 是算法硬下限。

**处理模式**：

- **逐词处理**（默认）：每个单词各自加一次混响，拖尾逐词叠加，最贴近原版听感；
  但每个词都要跑满一条拖尾，耗时随词数线性增长。
- **整句处理**：先把整句话按声道拼好，再整体做一次后处理。拖尾只算一次，
  长广播明显更快；代价是逐词的音高/效果差异会被统一。

两种模式的时间线完全一致，只有音频组织方式不同。15 词广播实测：只换整句约
**2.1x**，只提最高档约 **2.5x**，两者同时约 **2.8x**。

高级设置会保存到项目目录下的 `settings.json`，关掉程序再打开也会保留。
按次覆盖（API 请求体里临时带参数）不会写入该文件。

## 合成进度

播放和导出时，状态栏上方会有一条进度条，显示的是**服务端上报的真实进度**
而不是前端自己跑的动画。四个阶段在总进度里的区间是：

| 阶段 | 区间 | 说明 |
|---|---|---|
| 解析文本 | 0 ~ 8% | 解析指令、展开预设 |
| 应用空间效果 | 8 ~ 72% | **逐词加后处理，耗时大头** |
| 混音写盘 | 72 ~ 80% | 仅导出时出现 |
| 播放中 | 80 ~ 100% | 按真实播放时间推进 |

进度条是**常驻**的：没在合成时右侧写「就绪」，不会消失也不会占位跳动。

两条实现上的注意事项，遇到"进度条不动"时先看这里：

- **宽度是按时间补间的**，进度事件只负责设定目标值。关掉空间效果时整条合成
  只要几十毫秒，服务端会在同一瞬间推完所有事件；如果按"收到事件才改宽度"来做，
  浏览器只会渲染出最终结果，看起来就是完全不动。
- **预处理阶段（8~72%）是前端按预估时长先走的**。逐词加效果在
  `interpret_broadcast_text()` 里同步跑完，那期间生成器没法往外推事件，所以后端
  先发一条预估事件，等真实事件到达后再校正。因此这一段的百分比是估算值，
  最终值准确。

导出走 `POST /export_progress`（SSE，边算边推进度），完成后再走 `/export` 取文件；
播放走 `POST /play`，预处理和播放进度都在同一条 SSE 流里。接口细节见
[`docs/api.md`](docs/api.md)。

## 预设互相引用

预设内容里可以写 `[preset:名字]` 嵌入另一个预设，支持嵌套：

```text
[preset:intro] [preset:outro]
```

- 名字两侧空格可省；指令标签大小写不敏感（`[PRESET:x]` 等价）。
- 出现循环引用（A 引用 B、B 又引用 A）会被拦下并报错，不会死循环。
- 引用的预设不存在、名字为空、或内容为空，都会报错；预设内某个引用坏了
  不影响其余内容照常念出。

## 改前端后看到旧页面？

页面与静态资源都发 `Cache-Control: no-cache, must-revalidate`，浏览器每次都会
回来校验，正常情况下直接刷新就是最新的。如果你确实遇到旧页面（例如控制台报某个
按钮 `addEventListener` 为 null），按一次 `Ctrl+F5` 强制刷新即可——那说明浏览器
里还是加缓存头之前存下的旧副本。

改了后端则**必须重启 `python cassie_play.py`**，否则跑的还是旧进程。
`http://localhost:8080/api/v1/health` 返回的 `started_at` 与 `features`
可以用来确认当前跑的到底是哪一份代码。

## 音频素材

`cassie/words/` 中的文件名就是可输入的单词名，例如 `security.wav`。单个字母使用 `_a.wav` 形式，北约音标会映射到字母音频。`ic_start.wav` 和 `ic_stop.wav` 可作为特殊开始和结束铃声。

`cassie/sounds/` 中的 `bg_数字.wav` 是按广播时长匹配的背景铃声，普通特殊铃声包括 `bell_start.wav` 和 `bell_end.wav`。

添加新单词后可运行 `python tools/test_2.py` 更新素材列表；添加新铃声也会同步更新 `sound_list.json`。

## 关于版本

### V 1.0.0
- 删除了 `[alert]` 指令
- 修复了有关 `[cd]` 指令的 bug
- 将 cassie 语音音频分离了项目
- 前端从 `cassie_play.py` 拆分到 `static/app.js`，后端保持单文件
- 新增完整 HTTP API（`/api/v1`）与 Python 客户端 `cassie_api.py`
- 新增走廊混响的七档耗时控制与逐词/整句两种处理模式
- 新增合成与播放的真实进度条
- 新增 `[preset:名字]` 预设互相引用
- 高级设置落盘到 `settings.json`，关掉程序不再丢失
- 修复开启空间效果播放一次后进程退出的问题（空音频哨兵事件）
- 修复 pydub 文件句柄泄漏导致的 `ResourceWarning` 刷屏

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
