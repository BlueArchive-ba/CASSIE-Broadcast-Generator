# C.A.S.S.I.E. HTTP API

广播生成器开放了一组 HTTP 接口，网页界面能做的事都能通过接口完成：
查询运行状况、读取素材库、校验文本、解析时间线、合成 WAV、播放、停止、读写参数与预设。

配套的 Python 客户端见 [`cassie_api.py`](../cassie_api.py)，支持**进程内**与**远程 HTTP** 两种模式，
方法名与参数完全一致。

- 基础地址：`http://<主机>:8080/api/v1`
- 接口清单：`GET /api/v1` 会返回自描述的端点列表与参数默认值
- 编码：请求与响应均为 UTF-8 JSON

## 响应格式

成功：

```json
{
  "ok": true,
  "api_version": "v1",
  "data": { "...": "..." }
}
```

失败：

```json
{
  "ok": false,
  "api_version": "v1",
  "error": { "code": "empty_text", "message": "内容不能为空" }
}
```

唯一例外是 `POST /api/v1/synthesize` 带 `download=1` 时直接返回 `audio/wav` 字节流。

## 鉴权

默认不校验。如果设置了环境变量 `CASSIE_API_KEY`，则 **`/api/v1/*` 下的全部接口**
要求携带：

- 请求头 `X-API-Key: <token>`，或
- 查询参数 `?api_key=<token>`

```powershell
$env:CASSIE_API_KEY = 'my-secret'
python cassie_play.py
```

缺少或错误的 Key 返回 `401` / `unauthorized`。

> **保护范围仅限 `/api/v1/*`。**
> 网页端自用的路由（`/play`、`/export_progress`、`/export`、`/check_spelling*`、
> `/get_presets`、`/save_preset`、`/delete_preset`、`/import_presets`、
> `/get_advanced_settings`、`/save_advanced_settings`、`/static/*` 与各页面）
> **不做 API Key 校验**（`/save_advanced_settings` 是唯一例外，它也会校验）。
> 这些接口是给本机浏览器用的，**不要把它们当作可安全暴露到公网的服务**。
> 需要远程访问时请自行在反向代理上加访问控制，或只暴露 `/api/v1/*`。

---

## 语言

后端返回的消息（`error.message`、播放日志、质量档次文案）支持中文与英文，
默认 **中文**。指定方式二选一：

- 查询参数 `?lang=zh` / `?lang=en`
- 请求头 `X-Cassie-Lang: zh` / `X-Cassie-Lang: en`

优先级为「查询参数 → 请求头 → 中文」；无法识别的取值（含 `zh-CN`、`en-US`
这类带地区的写法会先归一化）一律回落到中文。默认不传参数时行为与历史版本完全一致。

```bash
# 英文错误消息
curl -X POST "http://127.0.0.1:8080/api/v1/validate?lang=en" \
     -H "Content-Type: application/json" -d '{"text":""}'

# 英文播放日志（SSE 流里的文本也会跟着切换）
curl -X POST "http://127.0.0.1:8080/api/v1/play?lang=en" \
     -H "Content-Type: application/json" -d '{"text":"attention , all personnel ."}'
```

网页界面上的中英切换按钮就是通过这两个字段把语言传给后端的。
Python 客户端可以直接在 URL 上带参数：`CassieClient.remote('http://127.0.0.1:8080')`
之后调用 `cassie.health(lang='en')` 之类，或自行在请求头里加 `X-Cassie-Lang`。

---

## 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1` | 接口清单、参数默认值 |
| GET | `/api/v1/health` | 运行状况自检 |
| GET | `/api/v1/words` | 全部可用单词 |
| GET | `/api/v1/sounds` | 全部可用铃声文件名 |
| POST | `/api/v1/validate` | 拼写检查 |
| POST | `/api/v1/plan` | 只解析不合成，返回时间线 |
| POST | `/api/v1/synthesize` | 合成 WAV |
| POST | `/api/v1/play` | 播放广播（异步） |
| POST | `/api/v1/stop` | 停止播放 |
| GET | `/api/v1/status` | 播放状态 |
| GET | `/api/v1/settings` | 读取服务端默认参数 |
| POST/PUT | `/api/v1/settings` | 修改服务端默认参数 |
| GET | `/api/v1/presets` | 全部预设 |
| POST | `/api/v1/presets` | 新增/覆盖预设 |
| GET | `/api/v1/presets/<name>` | 读取单个预设 |
| DELETE | `/api/v1/presets/<name>` | 删除预设 |
| POST | `/api/v1/presets/<name>/play` | 播放预设 |

以下两个是网页端自用的辅助接口（**不受 API Key 保护**，见上文「鉴权」），
**返回 SSE 流**，不属于 `/api/v1` 的 JSON 信封格式：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/export_progress` | 导出并推送真实进度（SSE），完成后需再请求 `/export` 取文件 |
| POST | `/play` | 播放并推送进度与逐词日志（SSE） |

两者的 SSE 事件形状见下文「[进度事件](#进度事件)」。

---

### GET /api/v1/health

```json
{
  "ok": true,
  "data": {
    "api_version": "v1",
    "project_version": "1.0.0",
    "status": "ok",
    "language": "zh",
    "pid": 12345,
    "started_at": "2026-10-06T18:11:10",
    "features": {
      "spoken_label": true,
      "spoken_parts": true,
      "number_words": true,
      "spatial_quality_tiers": true,
      "sentence_mode": true,
      "mono_reverb": true,
      "settings_persistence": true,
      "load_audio": true,
      "serve_local_file_no_cache": true
    },
    "spatial_quality_levels": 7,
    "python": "3.11.9",
    "platform": "win32",
    "playing": false,
    "stop_requested": false,
    "play_lock_held": false,
    "preset_count": 3,
    "audio_device_count": 9,
    "mixer_initialized": true,
    "library": {
      "words_dir": "…/cassie/words",
      "sounds_dir": "…/cassie/sounds",
      "word_files": 988,
      "sound_files": 38,
      "known_words": 1010,
      "special_bell_start_exists": true,
      "special_bell_end_exists": true,
      "ffmpeg_available": true
    }
  }
}
```

`features` 是**进程实际支持的功能指纹**：用反射判断方法是否存在，
而不是手工维护的清单。改了后端但忘了重启服务时，它和 `started_at`
是判断"跑的到底是哪一份代码"最直接的依据。
`spatial_quality_levels` 给出当前档次数量，前端据此渲染滑块上限。

### POST /api/v1/validate

请求 `{"text": "attention zzzz"}` → 响应 `data`：

```json
{ "text": "attention zzzz", "not_found": ["zzzz"], "ok": false }
```

### POST /api/v1/plan

只走解析与时间线计算，不渲染音频，适合先确认指令展开结果。

```json
{ "text": "mtf epsilon 11 .", "pitch": 1.0 }
```

`data`：

```json
{
  "text": "mtf epsilon 11 .",
  "errors": [],
  "word_count": 6,
  "event_count": 6,
  "duration_ms": 3464,
  "content_ms": 3464,
  "tail_ms": 0,
  "channels_used": [0],
  "events": [
    { "index": 0, "channel": 0, "label": "mobile",
      "start_ms": 0, "end_ms": 487, "duration_ms": 487, "slot_ms": 487 }
  ],
  "settings": { "pitch": 1.0, "speed": -10, "...": "本次生效的完整参数" },
  "elapsed_ms": 210
}
```

`mtf` 会展开成三个词（mobile / task / force），所以 `"mtf epsilon 11 ."` 是 6 个词、
6 个事件；上面的数值是显式传 `speed: -10` 时的结果。**不传 `speed` 时总时长会明显更长**
（约 8679ms），原因见上文「关于 `speed` 的默认值」。

时间线字段的含义：

| 字段 | 说明 |
|---|---|
| `start_ms` / `end_ms` | 单词在时间线上的位置，**只由文本、语速和音高决定**，与空间效果无关 |
| `slot_ms` | `end_ms - start_ms`，这个单词占用的时间槽 |
| `duration_ms`（事件内） | 事件音频的实际长度。开启混响后它会比 `slot_ms` 长（多出拖尾） |
| `content_ms` | 所有单词时间槽结束的时刻，即"正文说完了" |
| `tail_ms` | 末尾额外留出的拖尾时间（关闭空间效果时为 0） |
| `duration_ms`（顶层） | `content_ms + tail_ms`，整段广播的总时长 |

**开启空间效果不会改变单词的位置和间隔**，只在末尾多出一段拖尾：混响尾巴会自然
叠到下一个单词上，而不是把后面的单词往后推。早期版本按"加过效果的音频长度"排期，
导致语速设置失效、单词间隔变得极大，现已修正。改动时间线相关代码时请对比
`duration_ms`／`content_ms` 在开关空间效果前后是否一致。

`content_ms` / `tail_ms` 在两种处理模式下含义相同、数值也相同，可以放心拿来估算进度。

### POST /api/v1/synthesize

合成广播。默认返回 JSON（音频以 base64 内嵌），`download=1` 时直接返回 WAV 文件。

```json
{
  "text": "attention , all personnel .",
  "filename": "broadcast.wav",
  "download": 1
}
```

| 字段 | 说明 |
|---|---|
| `text` | 必填，广播文本（支持全部指令） |
| `filename` | 可选，下载时的文件名（只取 basename，防目录穿越） |
| `download` | `1` / `true` 时返回 WAV 字节流 |
| `base64` | 保留字段。JSON 形式**总是**内嵌 base64 音频，传 `false` 不会关闭 |
| 其余键 | 见下文「可调参数」，只影响这一次调用 |

带 `download=1` 的响应头会带 `X-Cassie-Sha256` 与 `X-Cassie-Elapsed-Ms`。

JSON 形式：

```json
{
  "ok": true,
  "data": {
    "metadata": {
      "text": "attention , all personnel .",
      "filename": "broadcast.wav",
      "size_bytes": 182144,
      "elapsed_ms": 640,
      "sha256": "…",
      "settings": { "...": "..." }
    },
    "audio_base64": "UklGR…"
  }
}
```

### POST /api/v1/play

异步播放，立即返回 `202`。

```json
{ "text": "mtf epsilon 11", "speed": -6 }
```

正在播放时返回 `409` / `playback_rejected`。用 `GET /api/v1/status` 轮询，
或 `POST /api/v1/stop` 停止。

### GET/POST /api/v1/settings

`POST` 修改的是**服务端默认参数**，会影响后续所有调用以及网页界面。
只作用于单次调用的参数请写在 `plan` / `synthesize` / `play` 的请求体里。

```json
{ "reverb_decay_time": 8.0, "reverb_wet": 0.5, "broadcast_effect_enabled": true }
```

全部复位：

```json
{ "reset": true }
```

未识别的字段会被拒绝：

```json
{ "ok": false, "error": { "code": "unknown_fields", "message": "…", "unknown_fields": ["foo"] } }
```

---

## 可调参数

请求体里的任意键只要出现在下表，就会被当作本次调用的参数覆盖项。

| 参数 | 默认 | 说明 |
|---|---|---|
| `pitch` | `1.0` | 音高倍率 0.1 ~ 10 |
| `speed` | 见下 | 正数加大单词间隔，负数按比例裁剪首尾静音 |
| `enable_number_reading` | `false` | 数字按英语短语朗读 |
| `include_bell` | `false` | 叠加背景铃声 |
| `enable_special_bell` | `false` | 开始/结束特殊铃声 |
| `broadcast_effect_enabled` | `false` | 空间效果总开关 |
| `low_cut_freq` / `high_cut_freq` | `0` | 低切/高切 Hz，0 为不切 |
| `mid_boost_gain` | `2.0` | 中频增益 dB |
| `overdrive_gain` + `clip_threshold` | `0` | 过载与削波 |
| `compressor_threshold` / `compressor_ratio` | `-12.0` / `6.0` | 压缩 |
| `reverb_enabled` | `true` | 启用走廊混响 |
| `reverb_pre_delay` | `18.0` | 预延迟 ms |
| `reverb_room_size` | `1.0` | 走廊尺度 0.2 ~ 3.0 |
| `reverb_decay_time` | `5.5` | RT60 秒，走廊建议 3 ~ 8 |
| `reverb_damping` | `4000.0` | 高频吸收，取值 500 ~ 4000（区间内线性映射） |
| `reverb_diffusion` | `0.72` | 扩散度 0 ~ 1 |
| `reverb_tail_brightness` | `0.55` | **目前未生效**：保留字段以兼容旧设置，改动它不改变输出 |
| `reverb_wet` | `0.35` | 混响湿声比例 0 ~ 1 |
| `treble_stretch` | `800.0` | 高音延长 ms |
| `treble_tail_gain` | `-28.0` | 高频尾音增益 dB |
| `noise_volume` / `noise_type` | `-35.0` / `pink` | 底噪 |
| `bell_lead_time` / `bell_extra_duration` | `3` / `3.0` | 铃声时序 |
| `special_bell_start` / `special_bell_end` | `bell_start.wav` / `bell_end.wav` | 特殊铃声文件 |
| `spatial_quality` | `0` | 空间效果质量档次 `0` ~ `6`，越高越快（见下） |
| `spatial_mode` | `word` | 空间效果处理模式：`word`（逐词）或 `sentence`（整句） |
| `stutter_duration` | `0.14` | 卡顿片段时长（秒）。同时用于 `[error:n]` 随机卡顿与显式 `[stutter:n]` 的片段长度 |

### 关于 `speed` 的默认值

`SYNTHESIS_PARAM_DEFAULTS` 里声明的是 `-10`，但**进程启动时的实际初值是 `20`**
（`CASSIETerminal.__init__` 里按测试数值设定）。区别在客户端**不传** `speed` 时体现：

- 不传 `speed` → 用 20，单词之间留出较长间隔；
- 显式传 `speed: -10` → 按比例裁剪首尾静音，明显更紧凑；
- `POST /api/v1/settings {"reset": true}` 会把它设回 `-10`，
  因此"复位"会**改变**不带 `speed` 调用的听感。

需要可复现的时长时请显式传 `speed`，不要依赖默认值。

### 空间效果的耗时控制

空间效果是整个合成流程里最重的一步。两个参数可以从不同角度降低耗时：

**`spatial_quality`（减少耗时）** —— 通过牺牲一点空间效果质量换速度，七档：

| 档 | 名称 | 块长 | 拖尾系数 | 拖尾长度 | 单次耗时 | 相对 |
|---|---|---|---|---|---|---|
| 0 | 原始 | 64 | 0.35 | 1942 ms | 82 ms | 1.00x |
| 1 | 轻度 | 128 | 0.28 | 1557 ms | 51 ms | 0.62x |
| 2 | 中度 | 256 | 0.18 | 1007 ms | 32 ms | 0.39x |
| 3 | 最大加速 | 941 | 0.10 | 567 ms | 22 ms | 0.27x |
| 4 | 激进 | 941 | 0.06 | 347 ms | 16 ms | 0.20x |
| 5 | 极限 | 941 | 0.03 | 182 ms | 15 ms | 0.18x |
| 6 | 单声道混响 | 941 | 0.03 | 182 ms | 11 ms | 0.13x |

块长只影响内部迭代次数，不改变声音；拖尾系数决定混响尾巴跑多久，
是真正会改变听感的一项（收短后尾部会自动淡出，不会有硬切的咔哒声）。
第 6 档在极限档基础上把立体声混响合成单声道，**干声仍是立体声**，
只是拖尾左右相同、失去宽度，换来近一倍的额外加速。

> 耗时已经触底：单词本体（约 945ms）本身就是必须处理的样本，
> 块长拉满后主循环只剩固定开销，约 12ms/声道 是硬下限。
> 再往下压拖尾只会降质、不会再快，所以没有第 7 档。

**`spatial_mode`（处理模式）** —— 改变后处理的组织方式：

- `word`（默认）：每个单词各自加一次混响，拖尾逐词叠加。最贴近原版听感，
  但**每个词都要跑满一整条拖尾**，所以耗时随词数线性增长。
- `sentence`：先把整句话按声道拼成干声，再整体做一次后处理。拖尾只算一次，
  长广播明显更快；代价是逐词的音高/效果差异会被统一。

两种模式的时间线（`start_ms` / `content_ms`）**完全一致**，只有音频组织方式不同。

实测（15 词的广播，RT60=5.5s）：

| 模式 | 档 | 耗时 | 相对基准 |
|---|---|---|---|
| word | 0 | 2841 ms | 1.00x |
| word | 3 | 1618 ms | 0.57x |
| sentence | 0 | 1805 ms | 0.64x |
| sentence | 3 | 1234 ms | 0.43x |

只换整句约 **2.1x**，只提最高档约 **2.5x**，两者同时约 **2.8x**。

### 设置持久化

网页端保存和 `POST /api/v1/settings`（不带请求体参数以外的临时覆盖）都会把当前
参数写入项目目录下的 `settings.json`，下次启动自动恢复，关掉程序不会丢。

**按次覆盖不落盘**：请求体里带的参数只对那一次调用生效，不会写进文件、
也不会改变服务端默认值。

```bash
# 改默认值并持久化
curl -X POST http://localhost:8080/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"spatial_quality": 3, "spatial_mode": "sentence"}'

# 只对这一次合成生效，不落盘
curl -X POST http://localhost:8080/api/v1/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text": "attention .", "spatial_mode": "sentence"}'
```

---

### 关于 `reverb_damping`

它表示「4 kHz 相对低频的衰减时间比」的期望值，只在 **500 ~ 4000** 之间有区分度：

- `4000` 及以上 → 不额外吸收高频（比值 1.0），高频和低频一样长
- `2000` → 高频约为低频的 0.66 倍
- `500` → 高频约为低频的 0.40 倍（可实现的最快吸收）

区间内是线性映射，超出部分被夹到端点。低频的 RT60 始终严格等于
`reverb_decay_time`，不受该参数影响。

### 关于空间效果的总开关

混响与逐词效果链共用一个总开关 `broadcast_effect_enabled`。
它为 `false` 时 `reverb_enabled` 也不会生效，时间线是纯干声排布；
设为 `true` 后整段广播会带上走廊拖尾，末尾时间线相应延长一段拖尾长度
（每个单词的音频会往后延，但单词的起始位置不变，所以总时长只增加末尾那一段）。

---

## Python 调用

### 进程内（推荐）

不需要启服务，直接调用同一套逻辑，速度快、可离线。

```python
import sys
sys.path.insert(0, r'C:\path\to\CASSIE V 1.0.0')

from cassie_api import CassieClient

with CassieClient.local() as cassie:
    print(cassie.health()['library']['word_files'])
    cassie.save('attention , all personnel .', 'out.wav',
                room_size=2.0, decay_time=7.0, wet=0.5)
```

进程内模式默认会真正播放声音。只想离线合成时，在导入之前设置：

```python
import os
os.environ['SDL_AUDIODRIVER'] = 'dummy'
```

### 远程

```python
from cassie_api import CassieClient, CassieAPIError

with CassieClient.remote('http://127.0.0.1:8080') as cassie:
    cassie.play('mtf epsilon 11')
    cassie.wait_until_done()
    data = cassie.synthesize_bytes('warhead 90 start', pitch=0.95)
    open('warhead.wav', 'wb').write(data)
```

### 参数名

客户端接受简化名与 API 原始名，两者等价：
`room_size` = `reverb_room_size`，`decay_time` / `rt60` = `reverb_decay_time`，
`wet` = `reverb_wet`，`damping` = `reverb_damping`，`bell` = `include_bell` 等。
完整对照见 `cassie_api.PARAMETER_ALIASES`，说明见 `cassie_api.PARAMETERS`。

### 主要方法

| 方法 | 说明 |
|---|---|
| `health()` | 运行状况 |
| `words()` / `sounds()` | 素材列表 |
| `validate(text)` | 拼写检查 |
| `plan(text, **params)` | 时间线（不合成） |
| `describe(text, **params)` | 人类可读的时间线摘要 |
| `synthesize(text, path=None, **params)` | 合成到文件，返回元数据 |
| `synthesize_bytes(text, **params)` | 合成并返回 bytes |
| `save(text, path, **params)` | 合成到指定路径 |
| `play(text, **params)` / `stop()` | 播放控制 |
| `wait_until_done(timeout)` | 等播放结束 |
| `status()` | 播放状态 |
| `settings()` / `update_settings(**params)` | 读写默认参数 |
| `presets()` / `preset(n)` / `save_preset()` / `delete_preset()` / `play_preset(n)` | 预设 |
| `duration_of(path)` | 读 WAV 时长 |

批量合成：`cassie_api.synthesize_batch(items, mode='local', output_dir='out')`

---

## curl 示例

```bash
# 运行状况
curl http://127.0.0.1:8080/api/v1/health

# 解析时间线
curl -X POST http://127.0.0.1:8080/api/v1/plan \
     -H "Content-Type: application/json" \
     -d '{"text":"mtf epsilon 11 ."}'

# 合成并下载（走廊混响拉长到 9 秒、湿声 0.6）
curl -X POST "http://127.0.0.1:8080/api/v1/synthesize?download=1" \
     -H "Content-Type: application/json" \
     -d '{"text":"attention , all personnel .","reverb_decay_time":9,"reverb_wet":0.6}' \
     -o broadcast.wav

# 播放
curl -X POST http://127.0.0.1:8080/api/v1/play \
     -H "Content-Type: application/json" -d '{"text":"mtf epsilon 11"}'

# 停止
curl -X POST http://127.0.0.1:8080/api/v1/stop
```

---

## 进度事件

网页端的进度条读的是服务端真实进度。接口分两类：

- **导出**：`POST /export_progress` 只推进度，合成完发 `done`，前端再走
  `POST /export` 拿 WAV 本体（避免把几十 MB 音频塞进 SSE）。
- **播放**：`POST /play` 在同一条流里先推预处理进度，再推播放进度，
  中间夹着逐词日志。

两者都是 `text/event-stream`，每条 `data: {…}` 是一个 JSON 对象：

| `type` | 含义 | 主要字段 |
|---|---|---|
| `progress` | 进度更新 | `stage`、`done`、`total`、`percent` |
| `progress`（预估） | 预处理阶段的估算值 | 额外带 `estimated: true`、`estimate_ms` |
| `progress`（播放） | 播放阶段起点 | 额外带 `is_playback: true`、`duration_ms`、`started_at`、`elapsed_ms` |
| `done` | 仅导出：合成结束 | `success`、`filename` |
| `end` | 仅播放：播放结束 | — |
| `info` / `error` | 逐词日志与错误 | `text` |

`stage` 取值与百分比区间：

| 阶段 | 区间 | 说明 |
|---|---|---|
| `parse` | 0 ~ 8% | 解析指令、展开预设 |
| `reverb` | 8 ~ 72% | 逐词加空间效果，耗时大头 |
| `export` | 72 ~ 80% | 仅导出：混音写盘 |
| `play` | 80 ~ 100% | 仅播放：按真实播放时间推进 |

**百分比是跨阶段单调递增的**，不会每换一个阶段退回 0。没有这层映射的话，
关掉空间效果时（`reverb` 阶段被跳过）百分比会一直停在 0%，进度条看起来完全不动。

**`reverb` 阶段的百分比可能是估算值。** 逐词加效果在
`interpret_broadcast_text()` 内部同步跑完，那期间生成器无法 `yield`，事件只能在
它结束后一次性到达。因此服务端会先发一条带 `estimated: true` 的预估事件
（`estimate_ms` 按词数与档次估算），前端据此先推进，真实事件到达后覆盖它。

```bash
# 观察导出进度事件流
curl -N -X POST http://localhost:8080/export_progress \
  -H "Content-Type: application/json" \
  -d '{"text":"attention , all personnel ."}'
```

实测：空间效果开启时事件跨度约 2 秒逐条到达；关闭时全部在约 47 ms 内到达
（所以前端必须做时间补间，不能只靠事件驱动宽度）。

## 并发与状态

- 播放与合成共用一把 `play_lock`。**播放中发起合成会返回 `409`**（这一向是可靠的）；
  反方向则不可靠：合成持锁期间调 `POST /api/v1/play` 仍会返回 `202`，
  但播放线程随后取锁失败、**什么都不会播**。要点是：`202` 只表示请求已被接受，
  要确认真的在播，请再查 `GET /api/v1/status` 的 `playing` 字段。
- 请求体里的参数只影响该次调用；`settings` 接口改的是服务端默认值。
  两者通过设置快照隔离，退出时一律还原，因此并发请求不会互相污染参数。
- **例外是网页端自用的 `POST /play`**：它直接写入 `enable_bell`、
  `enable_special_bell`、`enable_number_reading`、`verbose_mode`、`pitch`、`speed`
  这些运行时全局值且不还原，会体现在后续的 `GET /api/v1/settings` 上。
  需要严格隔离时请用 `/api/v1/play`。
- 混响冲激响应按参数缓存，参数变化时自动失效。
- 播放是异步的，接口立即返回；用 `status` 或 `stop` 控制。

## 手动验证

项目**不再附带自动化测试**，改动后请用下面的命令自查。

### 接口冒烟

服务启动后（`python cassie_play.py`），依次执行：

```bash
# 1. 服务活着，且确认跑的是最新代码（看 started_at / features）
curl http://127.0.0.1:8080/api/v1/health

# 2. 拼写检查：期望 not_found 为空
curl -X POST http://127.0.0.1:8080/api/v1/validate \
     -H "Content-Type: application/json" -d '{"text":"attention , all personnel ."}'

# 3. 时间线：期望 errors 为空、duration_ms 大于 0
curl -X POST http://127.0.0.1:8080/api/v1/plan \
     -H "Content-Type: application/json" -d '{"text":"mtf epsilon 11 .","speed":-10}'

# 4. 合成并落盘：用播放器确认能正常发声
curl -X POST "http://127.0.0.1:8080/api/v1/synthesize?download=1" \
     -H "Content-Type: application/json" \
     -d '{"text":"attention , all personnel .","reverb_decay_time":7,"reverb_wet":0.5}' \
     -o smoke.wav
```

### 进程内自检

不需要启服务，也听不到声音时最方便：

```python
import os
os.environ['SDL_AUDIODRIVER'] = 'dummy'      # 必须在导入前设置
import sys
sys.path.insert(0, r'C:\path\to\CASSIE V 1.0.0')

import cassie_play

terminal = cassie_play.CASSIETerminal()
print('素材:', terminal.library_status())
print('参数:', terminal.snapshot_settings())

# 时间线：不合成，只解析
text = 'mtf epsilon 11 .'
with terminal.settings_snapshot(terminal.merged_settings({'speed': -10})):
    plan = terminal.interpret_broadcast_text(text)
print('错误:', plan['errors'])
print('时长:', plan['duration_ms'], 'ms')

# 合成到文件。export_from_queue 返回 (是否成功, 路径) 两个值，
# 注意带上 speed：不传会用运行时初值 20（见上文「关于 speed 的默认值」）
ok, path = terminal.export_from_queue(text, 'smoke.wav', speed=-10)
print('合成:', ok, path)
```

用 Python 客户端更省事（自动处理参数名与返回值）：

```python
from cassie_api import CassieClient

with CassieClient.local() as cassie:          # 进程内，不需要启服务
    meta = cassie.synthesize('mtf epsilon 11 .', 'smoke.wav', speed=-10)
    print(meta['size_bytes'], '字节')

    # 想看时间线而不合成：describe 返回 {'summary': 文本, 'plan': 原始计划}
    print(cassie.describe('mtf epsilon 11 .', speed=-10)['summary'])
```

### 前端改动

**没有自动化手段**，只能手动过一遍：打开页面 → 播放、导出、切换中英、开关空间效果、
拖动「减少耗时」与「处理模式」并保存退出面板。控制台（`F12`）不应出现红色报错——
`app.js` 是一整段脚本，顶部任何一处 `ReferenceError` 都会让后面所有绑定失效，
表现成「页面能显示、点什么都没反应」。

### 无硬件播放

```bash
SDL_AUDIODRIVER=dummy python cassie_play.py
```

Windows PowerShell：`$env:SDL_AUDIODRIVER='dummy'`。

### 已知需要重点确认的地方

这几处曾反复出问题，改动相关代码时手工确认一次：

| 位置 | 现象 | 怎么确认 |
|---|---|---|
| 空音频「收尾哨兵」事件 | 进程以 `0xC0000005` 直接退出 | 开启空间效果后播放一次，程序应正常回到空闲 |
| `app.js` 绑定链 | 页面能显示但按钮全无反应 | 打开控制台，确认无 `ReferenceError` |
| 进度条 | 「有进度条但不动」 | 关掉空间效果导出一次，进度条仍应在约 0.5 秒内从 0% 走到 100% |
| 静态资源缓存 | 改了前端却看到旧页面 | 资源带 `?v=` 版本号且响应为 `Cache-Control: no-cache` |

## 实现要点

- 接口全部复用网页端同一套代码路径（`interpret_broadcast_text` →
  `_export_from_queue_unlocked` / `play_broadcast_stream`），没有第二份实现。
- 请求体里的参数通过 `CASSIETerminal.settings_snapshot()` 生效：
  进入时备份全局参数、覆盖为本次的值、退出时无条件还原，
  整个过程由 `settings_lock` 串行化，因此并发请求不会互相污染，
  也不会把网页端的设置改掉。（网页端自用的 `POST /play` 不走快照，见上节。）
- 混响冲激相关的参数按 `采样率 + 声道 + 混响参数` 缓存，参数一变自动落空。
- 播放是后台线程，与合成共用一把 `play_lock`：取不到锁时播放线程会直接结束，
  而 `POST /api/v1/play` 仍已返回 `202`。
