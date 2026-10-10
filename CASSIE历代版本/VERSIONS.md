# 版本对比

三个版本的**代码层面**差异。所有数字与结论都来自对 `cassie_play.py` 的实际分析，
不是从更新日志抄的。

> **三个版本都需要单独下载音频素材**，方式见下面的
> [《所有版本通用：音频素材》](#所有版本通用音频素材)。

---

## 总览

| | V 0.2 | V 0.3 | V 1.0.0 |
|---|---|---|---|
| `cassie_play.py` 行数 | 2440 | 3011 | **3701** |
| 网页路由 | 13 | 15 | 16 |
| `CASSIETerminal` 方法数 | 19 | 28 | **82** |
| 高级设置项 | 22 | 23 | **31** |
| 混响算法 | 多抽头延迟 | 多抽头延迟 | **FDN 反馈延迟网络** |
| HTTP API | — | — | **15 个接口** |
| 主界面形态 | Python 字符串内联 | Python 字符串内联 | **独立 `cassie_play.html` + `static/`** |
| 入口 | `index.py` | `index.py` | **`cassie_play.py`** |
| 中英双语 | — | — | **有** |
| Python 要求 | 3.6.5 | 3.10 | **3.10.15+** |

**关于「主界面形态」**：0.2 / 0.3 的主页面 HTML 与脚本是**写在 Python 里的字符串**，
所以 `cassie_play.py` 与 `index.py` 里能搜到 `<!DOCTYPE` 与 `<script`
（页面由服务端拼接后返回）。1.0.0 把它们抽成真实文件，
`cassie_play.py` 里不再出现 HTML。
「入口」一栏指的是启动命令：0.2/0.3 跑 `index.py`，1.0.0 直接跑 `cassie_play.py`。

---

## V 0.2 — 起点

**代码形态**：单文件 `cassie_play.py`（2440 行）+ `index.py` 内联前端。

**已具备**：

- 单词拼接播放与 WAV 导出
- 数字朗读、多声道、广播铃声与特殊铃声
- 广播指令：`mtf`、`[cd:]`、`[warhead:]`、`[backup:]`、`[hostile_enter:]`、
  `[stutter:]`、`[speed:]`、`[speed_all:]`、`[error:]`、`[gap:]`、`[channel:]`
- 预设管理（`presets.json`）
- 广播空间效果与高级设置面板

**混响实现**：多抽头延迟线。

```python
delay_ms = int(self.reverb_delay + i * (self.reverb_decay / (num_taps * 1.2)))
gain_factor = math.exp(-i * 0.4) * self.reverb_wet
```

每根抽头的增益按 `exp(-i × 0.4)` 固定衰减，高低频**同等衰减**——本质是一串
间隔递增的离散回声，不是真正的反馈网络。可调项只有
`reverb_delay` / `reverb_decay` / `reverb_wet` / `reverb_lowpass`。

---

## V 0.3 — 界面与指令扩展

**代码增量**：+571 行，新增 10 个方法、2 个路由、2 个设置项。

**新增**：

- 新增路由 `/developer`（开发者技术文档）与 `/word-search`（单词查找页）
- 新增 `[alert]` 指令、`[channel:]` 与 `[gap:]` 的说明补齐到帮助文档
- 方法层面引入 `parse_broadcast_text()` / `_export_from_queue_unlocked()` /
  `_play_audio_segment()` / `wait_for_channels()` / `stop_all_audio()`，
  把「解析」与「播放/导出」拆开
- 新增设置项 `bell_lock`、`treble_tail_gain`（高音尾音增益）
- 移除 `reverb_high_gain`

**仍然没有**：FDN、HTTP API、双语、进度反馈。

---

## V 1.0.0 — 混响重写 + 开放 API

**代码增量**：+690 行，新增 **56 个方法**、11 个设置项，新增 15 个 API 路由。

这是变化最大的一版，可以分成五块。

### 1. 混响换成 FDN 反馈延迟网络

从多抽头延迟改为真正的反馈网络：

- **8 条互质延迟线** `(941, 1093, 1229, 1361, 1483, 1609, 1721, 1879)`
  毫秒——互质是为了避免各线周期重合产生梳状染色
- **归一化 Hadamard 反馈矩阵**（`_build_hadamard()`），用矩阵混合代替简单叠加
- **反馈回路内的一阶低通阻尼**（`FDN_DAMPING_POLE = 0.8`）：
  高频每个反射周期少拿一点能量、衰减更快，低频 RT60 严格等于设定值
- 新增可调项：`reverb_room_size`（走廊尺度）、`reverb_decay_time`（RT60）、
  `reverb_damping`（4 kHz 相对低频的衰减时间比）、`reverb_diffusion`（扩散度）、
  `reverb_tail_brightness`、`reverb_pre_delay`
- **移除了** `reverb_delay` / `reverb_decay` / `reverb_lowpass`

**另一个关键变化：混响不再逐个单词施加。** 0.2/0.3 是每个词各自加一遍混响，
拖尾会把单词的时间槽撑长；1.0.0 改由 `apply_reverb_to_events()` 在时间线
组装完成后统一施加，所以**开不开空间效果都不改变语速与单词间隔**。

### 2. 七档耗时控制与两种处理模式

`SPATIAL_QUALITY_LEVELS` 七档（0~6），把「块长」与「拖尾长度」打包：

| 档 | 名称 | 拖尾长度 | 单次耗时 | 相对 |
|---|---|---|---|---|
| 0 | 原始 | 1942 ms | 82 ms | 1.00x |
| 1 | 轻度 | 1557 ms | 51 ms | 0.62x |
| 2 | 中度 | 1007 ms | 32 ms | 0.39x |
| 3 | 最大加速 | 567 ms | 22 ms | 0.27x |
| 4 | 激进 | 347 ms | 16 ms | 0.20x |
| 5 | 极限 | 182 ms | 15 ms | 0.18x |
| 6 | 单声道混响 | 182 ms | 11 ms | 0.13x |

第 6 档额外开启 `mono_reverb`：立体声混响合成单声道（干声仍立体声），
换来近一倍加速。

`spatial_mode` 提供 `word`（逐词）与 `sentence`（整句）两种组织方式，
15 词广播实测：只换整句约 2.1x、只提最高档约 2.5x、两者同时约 2.8x。

### 3. 完整 HTTP API

新增 `/api/v1` 前缀下的 15 个接口，外加 Python 客户端 `cassie_api.py`
（支持进程内与远程两种模式）：

```
GET  /api/v1                    自描述接口清单
GET  /api/v1/health             运行状况（含 started_at 与功能指纹）
GET  /api/v1/words|sounds       素材列表
POST /api/v1/validate           拼写检查
POST /api/v1/plan               只解析不合成
POST /api/v1/synthesize         合成 WAV
POST /api/v1/play|stop          播放控制
GET  /api/v1/status             播放状态
GET/POST /api/v1/settings       读写默认参数
GET/POST/DELETE /api/v1/presets 预设增删改查
```

统一 JSON 信封 `{ok, api_version, data|error}`；支持 `CASSIE_API_KEY` 鉴权、
`?lang=zh|en` 语言协商。**这是 0.2/0.3 完全没有的能力。**

### 4. 进度反馈

- `/export_progress`（SSE）：导出时边算边推真实进度
- 播放路径也推送预处理与播放进度
- 四个阶段按耗时加权：解析 0~8%、应用空间效果 8~72%、写盘 72~80%、播放 80~100%
- 前端进度条**按时间补间**，因此关掉空间效果（整条合成仅约 47 ms）时也能看到它走完

### 5. 前端拆分与双语

- 前端从内联脚本拆成 `cassie_play.html` + `static/app.js` + 五张样式表
  （`glass` / `style` / `advanced` / `docs` / `wordsearch`）
- 新增中英双语：`static/i18n*.js` 四张词表；服务端返回的文案也跟随语言
- 新增 `docs/api.md`（HTTP API 参考）

### 其他变化

| 项 | 说明 |
|---|---|
| `[preset:名字]` | 预设之间可互相引用，带循环引用检测（`MAX_PRESET_DEPTH = 16`） |
| `[channl:+x] … [channl:stop]` | 区块级声道偏移，最多三位小数 |
| `[alert]` 移除 | 0.2/0.3 有，1.0.0 删除 |
| 设置持久化 | `settings.json`，关掉程序不丢；按次覆盖不落盘 |
| 音频句柄封装 | `load_audio()` / `export_audio()` 显式关闭，修掉 `ResourceWarning` 刷屏 |
| 静态资源 | `serve_local_file()` 发 `Cache-Control: no-cache`，不再被浏览器启发式缓存 |
| 日志逐词输出 | `spoken_words` / `SAMPLE_LABELS` / `NUMBER_WORDS`，日志念出"实际听到的内容" |

---

## 所有版本通用：音频素材

**三个版本都不含音频素材，都必须单独下载。** 缺素材时程序无法生成任何广播。

推荐用下载器，它会自动下载并解压到正确位置：

```bash
cd CASSIE语音生成
python cassie_download.py
```

下载器从素材仓库 [BlueArchive-ba/CASSIE](https://github.com/BlueArchive-ba/CASSIE)
的 `v1.3.0` 发布下载 `cassie.zip`（约 424 MB），支持多线程与断点续传，
并在网络受限时自动改用镜像。

> 下载器本身是 V 1.0.0 时期随「音频素材与代码分离」一同加入的，
> 但 **V 0.2 / V 0.3 同样需要它**——它们的音频也不在包里。

素材会安装到版本目录下的 `cassie/`：

```
cassie/
├── words/    单词、数字、字母音、故障音
├── sounds/   铃声与背景铃声
└── alarms/   警报音频
```

**程序会主动检查素材是否就位**（1.0.0 具备）：

| 时机 | 表现 |
|---|---|
| 启动服务 | 终端打印红框提示，含期望目录与下载命令 |
| 打开网页 | 页面上方显示提示条并给出完整路径 |
| 运行诊断 | `diagnostic.py` 输出专门的提示块 |

0.2 / 0.3 没有这套提示，缺素材时只会在终端报「未找到」——
所以**先跑下载器**再启动。

---

## 该选哪一版

- **用最新功能** → V 1.0.0（API、双语、进度条、七档混响、FDN 音质）
- **要低配环境** → V 0.2 只需 Python 3.6.5，但没有指令扩展与任何 API
- **只要基础功能** → V 0.3 是 0.2 的补全版，仍无 API 与双语

三个版本的**素材格式与指令语法高度兼容**，预设文件可以直接搬用。
