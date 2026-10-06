"""C.A.S.S.I.E. 广播生成器 Python 客户端。

同一套接口支持两种调用方式：

    进程内（推荐，无需启服务、无需网络）
        from cassie_api import CassieClient
        with CassieClient.local() as cassie:
            meta = cassie.synthesize('attention , all personnel .',
                                     'out.wav', room_size=2.0, decay_time=7.0)

    远程（连到已经跑起来的 cassie_play.py）
        with CassieClient.remote('http://127.0.0.1:8080') as cassie:
            print(cassie.health()['status'])
            cassie.play('mtf epsilon 11')

两种模式的方法名、参数名、返回值完全一致，切换只需要换构造方式。

参数命名：方法接受三组关键字参数

    * 结构参数（text / output_path / name ...）——位置或关键字传入
    * 合成参数（pitch / speed / room_size / decay_time ...）——见 PARAMETERS
    * 传输参数（timeout / api_key ...）——由客户端构造时决定

合成参数使用下划线简化名（room_size），同时也接受 API 原始名
（reverb_room_size），两者等价。
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import wave
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    'CassieClient', 'CassieError', 'CassieAPIError', 'CassieUnavailableError',
    'PARAMETERS',
]

DEFAULT_BASE_URL = 'http://127.0.0.1:8080'
API_PREFIX = '/api/v1'

# 简化名 -> 服务端字段名。没有列在这里的键按原样透传。
PARAMETER_ALIASES: Dict[str, str] = {
    'speed': 'speed',
    'pitch': 'pitch',
    'rate': 'speed',
    'number_reading': 'enable_number_reading',
    'read_numbers': 'enable_number_reading',
    'bell': 'include_bell',
    'background_bell': 'include_bell',
    'special_bell': 'enable_special_bell',
    'low_cut': 'low_cut_freq',
    'high_cut': 'high_cut_freq',
    'mid_boost': 'mid_boost_gain',
    'overdrive': 'overdrive_gain',
    'clip': 'clip_threshold',
    'compressor_threshold': 'compressor_threshold',
    'compressor_ratio': 'compressor_ratio',
    'effects': 'broadcast_effect_enabled',
    'spatial_effect': 'broadcast_effect_enabled',
    'reverb': 'reverb_enabled',
    'pre_delay': 'reverb_pre_delay',
    'room_size': 'reverb_room_size',
    'hall_size': 'reverb_room_size',
    'decay_time': 'reverb_decay_time',
    'rt60': 'reverb_decay_time',
    'reverb_time': 'reverb_decay_time',
    'damping': 'reverb_damping',
    'hf_absorption': 'reverb_damping',
    'diffusion': 'reverb_diffusion',
    'tail_brightness': 'reverb_tail_brightness',
    'brightness': 'reverb_tail_brightness',
    'wet': 'reverb_wet',
    'reverb_wet': 'reverb_wet',
    'treble_stretch': 'treble_stretch',
    'tail_gain': 'treble_tail_gain',
    'noise_volume': 'noise_volume',
    'noise_type': 'noise_type',
    'stutter_duration': 'stutter_duration',
    'bell_lead_time': 'bell_lead_time',
    'bell_extra_duration': 'bell_extra_duration',
    'special_bell_start': 'special_bell_start',
    'special_bell_end': 'special_bell_end',
    # 空间效果的开销控制
    'quality': 'spatial_quality',
    'spatial_quality': 'spatial_quality',
    'speed_up': 'spatial_quality',
    'reduce_cost': 'spatial_quality',
    'mode': 'spatial_mode',
    'spatial_mode': 'spatial_mode',
    'processing_mode': 'spatial_mode',
}

# 便于外部自省与文档生成：简化名 -> 说明
PARAMETERS: Dict[str, str] = {
    'pitch': '音高倍率，0.1 ~ 10，1.0 为原音',
    'speed': '语速修正。正数加大单词间隔，负数按比例裁剪首尾静音',
    'number_reading': '数字按英语短语朗读（False 时逐位读）',
    'bell': '叠加广播背景铃声',
    'special_bell': '播放开始/结束特殊铃声',
    'effects': '总开关：启用广播空间效果链',
    'low_cut': '低切频率 Hz，0 表示不切',
    'high_cut': '高切频率 Hz，0 表示不切',
    'mid_boost': '中频增益 dB',
    'overdrive': '过载增益 dB（需配合 clip）',
    'clip': '削波阈值，0 表示关闭',
    'compressor_threshold': '压缩阈值 dB',
    'compressor_ratio': '压缩比',
    'reverb': '启用走廊混响',
    'pre_delay': '混响预延迟 ms',
    'room_size': '走廊尺度，0.2 ~ 3.0',
    'decay_time': '混响时长 RT60，秒，走廊建议 3 ~ 8',
    'damping': '高频吸收（4 kHz 与低频的衰减比），4000 表示不额外吸收',
    'diffusion': '扩散度 0 ~ 1，越低越像离散回声',
    'tail_brightness': '尾音亮度 0 ~ 1，越大高频回荡越明显',
    'wet': '混响湿声比例 0 ~ 1',
    'treble_stretch': '高音延长 ms',
    'tail_gain': '高频尾音增益 dB',
    'noise_volume': '底噪音量 dB',
    'noise_type': '底噪类型：pink 或 white',
    'stutter_duration': '卡顿片段时长（秒）',
    'quality': '空间效果质量档次 0 ~ 3，越高越快、拖尾越短（0 = 不削减）',
    'spatial_quality': '同 quality（服务端原字段名）',
    'mode': '空间效果处理模式："word" 逐词 / "sentence" 整句',
    'spatial_mode': '同 mode（服务端原字段名）',
}


class CassieError(Exception):
    """客户端异常基类。"""


class CassieAPIError(CassieError):
    """服务端返回了 ok=false，或 HTTP 状态异常。"""

    def __init__(self, message: str, code: str = 'error', status: int = 0,
                 payload: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.payload = payload or {}


class CassieUnavailableError(CassieError):
    """连不上服务端，或进程内模式缺失依赖。"""


def _translate_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """把简化参数名翻译成服务端字段名，同时接受原始字段名。"""
    translated: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        translated[PARAMETER_ALIASES.get(key, key)] = value
    return translated


class CassieClient:
    """C.A.S.S.I.E. 客户端，进程内或远程二选一。"""

    def __init__(self, base_url: Optional[str] = None, *, terminal=None,
                 timeout: float = 120.0, api_key: Optional[str] = None):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else os.environ.get('CASSIE_API_KEY')
        self._terminal = terminal
        self._local = terminal is not None

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------

    @classmethod
    def local(cls, **kwargs) -> 'CassieClient':
        """进程内模式：直接驱动本机的 cassie_play 逻辑。

        需要把项目根目录加入 sys.path（pip 安装或自行 insert）。
        首次调用会初始化 pygame 混音器，因此默认是有声播放；
        只想离线合成时，在导入 cassie_play 之前设置
        os.environ['SDL_AUDIODRIVER'] = 'dummy' 即可静音。
        """
        try:
            import cassie_play
        except ImportError as error:
            raise CassieUnavailableError(
                '无法导入 cassie_play，请确认项目根目录在 sys.path 中：{}'.format(error))
        terminal = getattr(cassie_play, '_api_terminal', None)
        if terminal is None:
            # 复用 HTTP 路由持有的实例，保证进程内客户端与服务端状态一致
            terminal = getattr(cassie_play, 'cassie', None)
            if terminal is None:
                terminal = cassie_play.CASSIETerminal()
                cassie_play.cassie = terminal
            cassie_play._api_terminal = terminal
        return cls(terminal=terminal, **kwargs)

    @classmethod
    def remote(cls, base_url: str = DEFAULT_BASE_URL, **kwargs) -> 'CassieClient':
        """远程模式：通过 HTTP 调用已经运行的 cassie_play 服务。"""
        return cls(base_url, **kwargs)

    def __enter__(self) -> 'CassieClient':
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        """释放资源。远程模式无副作用；进程内模式会停掉正在播放的广播。"""
        if self._local and self._terminal is not None:
            try:
                self._terminal.stop_playback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # HTTP 传输
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, payload: Optional[dict] = None,
                 *, raw: bool = False, query: Optional[dict] = None):
        url = self.base_url + API_PREFIX + path
        if query:
            url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        data = None
        headers = {'Accept': 'application/json'}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json; charset=UTF-8'
        if self.api_key:
            headers['X-API-Key'] = self.api_key

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                content_type = response.headers.get('Content-Type', '')
                if raw:
                    return body, dict(response.headers)
        except urllib.error.HTTPError as error:
            body = error.read()
            try:
                parsed = json.loads(body.decode('utf-8'))
                info = parsed.get('error') or {}
                raise CassieAPIError(info.get('message') or str(error),
                                     code=info.get('code', 'http_error'),
                                     status=error.code, payload=parsed) from None
            except (ValueError, UnicodeDecodeError):
                raise CassieAPIError('HTTP {}: {}'.format(error.code, body[:200]),
                                     code='http_error', status=error.code) from None
        except urllib.error.URLError as error:
            raise CassieUnavailableError(
                '无法连接 {}（{}）。服务端是否已启动？'.format(self.base_url, error.reason)) from None

        try:
            parsed = json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise CassieAPIError('服务端返回的不是合法 JSON：{}'.format(body[:200]),
                                 code='invalid_response') from None
        if isinstance(parsed, dict) and parsed.get('ok') is False:
            info = parsed.get('error') or {}
            raise CassieAPIError(info.get('message', '请求失败'),
                                 code=info.get('code', 'error'), payload=parsed)
        if isinstance(parsed, dict) and 'data' in parsed:
            return parsed['data']
        return parsed

    # ------------------------------------------------------------------
    # 只读接口
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """运行状况：播放状态、素材库统计、环境信息。"""
        if self._local:
            return self._terminal.health()
        return self._request('GET', '/health')

    def api_documentation(self) -> Dict[str, Any]:
        """服务端自描述的接口清单与参数默认值。"""
        if self._local:
            return self._terminal.api_documentation()
        return self._request('GET', '/')

    def status(self) -> Dict[str, Any]:
        """播放状态。"""
        if self._local:
            return {
                'playing': bool(self._terminal.is_playing),
                'stop_requested': bool(self._terminal.stop_requested),
                'play_lock_held': bool(self._terminal.play_lock.locked()),
            }
        return self._request('GET', '/status')

    def words(self) -> List[str]:
        """所有可用单词。"""
        if self._local:
            return self._terminal.list_words()
        return self._request('GET', '/words')['words']

    def sounds(self) -> List[str]:
        """所有可用铃声文件名。"""
        if self._local:
            return self._terminal.list_sounds()
        return self._request('GET', '/sounds')['sounds']

    def validate(self, text: str) -> Dict[str, Any]:
        """拼写检查：返回文本里缺少音频的单词。"""
        if self._local:
            return self._terminal.validate_text(text)
        return self._request('POST', '/validate', {'text': text})

    def plan(self, text: str, **params) -> Dict[str, Any]:
        """只解析不合成，返回时间线与错误列表。"""
        overrides = _translate_params(params)
        if self._local:
            return self._terminal.plan_broadcast(text, overrides)
        return self._request('POST', '/plan', {'text': text, **overrides})

    def settings(self) -> Dict[str, Any]:
        """读取服务端当前默认参数。"""
        if self._local:
            return self._terminal.snapshot_settings()
        return self._request('GET', '/settings')['settings']

    def update_settings(self, reset: bool = False, **params) -> Dict[str, Any]:
        """修改服务端默认参数（会影响后续所有调用与网页端）。"""
        payload = _translate_params(params)
        if reset:
            payload['reset'] = True
        if self._local:
            with self._terminal.settings_lock:
                if reset:
                    import cassie_play
                    applied = dict(cassie_play.SYNTHESIS_PARAM_DEFAULTS)
                else:
                    applied = dict(payload)
                for key, value in applied.items():
                    setattr(self._terminal, key, value)
                self._terminal._reverb_cache.clear()
            return {'applied': applied, 'settings': self._terminal.snapshot_settings()}
        return self._request('POST', '/settings', payload)

    # ------------------------------------------------------------------
    # 预设
    # ------------------------------------------------------------------

    def presets(self) -> Dict[str, str]:
        """全部预设（名称 -> 广播文本）。"""
        if self._local:
            return dict(getattr(self._terminal, 'presets', {}) or {})
        return self._request('GET', '/presets')['presets']

    def preset(self, name: str) -> str:
        """读取单个预设内容。"""
        if self._local:
            presets = getattr(self._terminal, 'presets', {}) or {}
            if name not in presets:
                raise CassieAPIError('预设不存在: {}'.format(name), code='not_found', status=404)
            return presets[name]
        return self._request('GET', '/presets/' + urllib.parse.quote(name))['content']

    def save_preset(self, name: str, content: str) -> Dict[str, Any]:
        """新增或覆盖预设。"""
        if self._local:
            self._terminal.presets[name] = content
            self._terminal.save_presets()
            return {'name': name, 'content': content, 'count': len(self._terminal.presets)}
        return self._request('POST', '/presets', {'name': name, 'content': content})

    def delete_preset(self, name: str) -> Dict[str, Any]:
        """删除预设。"""
        if self._local:
            presets = getattr(self._terminal, 'presets', {}) or {}
            if name not in presets:
                raise CassieAPIError('预设不存在: {}'.format(name), code='not_found', status=404)
            del presets[name]
            self._terminal.save_presets()
            return {'deleted': name, 'count': len(presets)}
        return self._request('DELETE', '/presets/' + urllib.parse.quote(name))

    def play_preset(self, name: str) -> Dict[str, Any]:
        """播放预设内容。"""
        if self._local:
            text = self.preset(name)
            self.play(text)
            return {'playing': True, 'name': name, 'text': text}
        return self._request('POST', '/presets/{}/play'.format(urllib.parse.quote(name)))

    # ------------------------------------------------------------------
    # 合成与播放
    # ------------------------------------------------------------------

    def synthesize(self, text: str, output_path: Optional[str] = None, *,
                   filename: Optional[str] = None, **params) -> Dict[str, Any]:
        """合成广播为 WAV 文件，返回元数据（含输出路径与 sha256）。

        output_path 为空时写入临时文件，路径在返回值的 path 字段里。
        """
        overrides = _translate_params(params)

        if self._local:
            ok, result, metadata = self._terminal.synthesize(
                text, output_path=output_path, overrides=overrides, filename=filename)
            if not ok:
                raise CassieAPIError(result, code='synthesize_failed')
            metadata['path'] = result
            with open(result, 'rb') as handle:
                metadata['sha256'] = _sha256(handle.read())
            metadata['download_url'] = None
            return metadata

        payload = {'text': text, **overrides}
        if filename:
            payload['filename'] = filename
        if output_path:
            body, headers = self._request(
                'POST', '/synthesize', payload, raw=True, query={'download': 1})
            with open(output_path, 'wb') as handle:
                handle.write(body)
            return {
                'path': os.path.abspath(output_path),
                'filename': os.path.basename(output_path),
                'size_bytes': len(body),
                'sha256': headers.get('X-Cassie-Sha256', _sha256(body)),
                'elapsed_ms': int(headers.get('X-Cassie-Elapsed-Ms') or 0),
            }

        payload['base64'] = True
        data = self._request('POST', '/synthesize', payload)
        audio = base64.b64decode(data['audio_base64'])
        handle = tempfile.NamedTemporaryFile(suffix='.wav', delete=False,
                                             prefix='cassie_')
        handle.write(audio)
        handle.close()
        metadata = dict(data.get('metadata') or {})
        metadata['path'] = handle.name
        metadata['size_bytes'] = len(audio)
        metadata['sha256'] = metadata.get('sha256') or _sha256(audio)
        return metadata

    def synthesize_bytes(self, text: str, **params) -> bytes:
        """合成并直接返回 WAV 字节，不落盘。"""
        overrides = _translate_params(params)
        if self._local:
            metadata = self.synthesize(text, **params)
            try:
                with open(metadata['path'], 'rb') as handle:
                    return handle.read()
            finally:
                try:
                    os.unlink(metadata['path'])
                except OSError:
                    pass
        body, _ = self._request('POST', '/synthesize',
                                {'text': text, **overrides}, raw=True,
                                query={'download': 1})
        return body

    def play(self, text: str, **params) -> Dict[str, Any]:
        """播放广播（立即返回，后台线程执行）。"""
        overrides = _translate_params(params)
        if self._local:
            started, message = self._terminal.start_playback(text, overrides)
            if not started:
                raise CassieAPIError(message, code='playback_rejected', status=409)
            return {'playing': True, 'text': text}
        return self._request('POST', '/play', {'text': text, **overrides})

    def stop(self) -> Dict[str, Any]:
        """停止播放并静音。"""
        if self._local:
            self._terminal.stop_playback()
            return {'playing': False, 'stop_requested': True}
        return self._request('POST', '/stop')

    def wait_until_done(self, timeout: float = 600.0, poll: float = 0.25) -> bool:
        """等待当前播放结束，返回是否在超时前结束。"""
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if not self.status()['playing']:
                return True
            _time.sleep(poll)
        return False

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def say(self, text: str, **params) -> Dict[str, Any]:
        """合成到临时文件并返回元数据。语义糖，等价于 synthesize(text, **params)。"""
        return self.synthesize(text, **params)

    def save(self, text: str, path: str, **params) -> Dict[str, Any]:
        """合成并保存到指定路径。"""
        return self.synthesize(text, path, **params)

    def describe(self, text: str, **params) -> Dict[str, Any]:
        """可读的时间线摘要，便于确认指令展开结果。"""
        plan = self.plan(text, **params)
        lines = [
            '文本: {}'.format(plan['text']),
            '时长: {:.2f}s  事件: {}  单词: {}'.format(
                plan['duration_ms'] / 1000.0, plan['event_count'], plan['word_count']),
            '声道: {}'.format(plan['channels_used']),
        ]
        if plan['errors']:
            lines.append('错误: ' + '; '.join(plan['errors']))
        for event in plan['events']:
            lines.append('  [{:>3}] ch{} {:>7.0f}ms +{:>5}ms  {}'.format(
                event['index'], event['channel'], event['start_ms'],
                event['duration_ms'], event['label']))
        return {'summary': '\n'.join(lines), 'plan': plan}

    @staticmethod
    def duration_of(path: str) -> float:
        """读取 WAV 文件时长（秒）。"""
        with wave.open(path, 'rb') as handle:
            return handle.getnframes() / float(handle.getframerate())


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def synthesize_batch(items: Iterable[Dict[str, Any]], *, mode: str = 'local',
                     base_url: str = DEFAULT_BASE_URL, output_dir: str = '.',
                     **client_kwargs) -> List[Dict[str, Any]]:
    """批量合成。items 里每项形如 {'text': ..., 'filename': ..., 参数...}。

    返回与输入等长的结果列表；单项失败时该项为 {'ok': False, 'error': ...}。
    """
    client = CassieClient.local(**client_kwargs) if mode == 'local' \
        else CassieClient.remote(base_url, **client_kwargs)
    results: List[Dict[str, Any]] = []
    try:
        for index, item in enumerate(items):
            item = dict(item)
            text = item.pop('text')
            filename = item.pop('filename', 'cassie_{:03d}.wav'.format(index))
            target = os.path.join(output_dir, os.path.basename(filename))
            try:
                metadata = client.synthesize(text, target, filename=filename, **item)
                results.append({'ok': True, **metadata})
            except CassieError as error:
                results.append({'ok': False, 'text': text, 'error': str(error)})
    finally:
        client.close()
    return results
