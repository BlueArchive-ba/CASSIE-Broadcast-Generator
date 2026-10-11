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
    'quality': 'spatial_quality',
    'spatial_quality': 'spatial_quality',
    'speed_up': 'spatial_quality',
    'reduce_cost': 'spatial_quality',
    'mode': 'spatial_mode',
    'spatial_mode': 'spatial_mode',
    'processing_mode': 'spatial_mode',
}

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
    pass
    
class CassieAPIError(CassieError):
    
    def __init__(self, message: str, code: str = 'error', status: int = 0,
                 payload: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.payload = payload or {}

class CassieUnavailableError(CassieError):
    pass
    
def _translate_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    
    translated: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        translated[PARAMETER_ALIASES.get(key, key)] = value
    return translated

class CassieClient:
    
    def __init__(self, base_url: Optional[str] = None, *, terminal=None,
                 timeout: float = 120.0, api_key: Optional[str] = None):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else os.environ.get('CASSIE_API_KEY')
        self._terminal = terminal
        self._local = terminal is not None

    @classmethod
    def local(cls, **kwargs) -> 'CassieClient':
        
        try:
            import cassie_play
        except ImportError as error:
            raise CassieUnavailableError(
                '无法导入 cassie_play，请确认项目根目录在 sys.path 中：{}'.format(error))
        terminal = getattr(cassie_play, '_api_terminal', None)
        if terminal is None:
            terminal = getattr(cassie_play, 'cassie', None)
            if terminal is None:
                terminal = cassie_play.CASSIETerminal()
                cassie_play.cassie = terminal
            cassie_play._api_terminal = terminal
        return cls(terminal=terminal, **kwargs)

    @classmethod
    def remote(cls, base_url: str = DEFAULT_BASE_URL, **kwargs) -> 'CassieClient':
        
        return cls(base_url, **kwargs)

    def __enter__(self) -> 'CassieClient':
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        
        if self._local and self._terminal is not None:
            try:
                self._terminal.stop_playback()
            except Exception:
                pass

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

    def health(self) -> Dict[str, Any]:
        
        if self._local:
            return self._terminal.health()
        return self._request('GET', '/health')

    def api_documentation(self) -> Dict[str, Any]:
        
        if self._local:
            return self._terminal.api_documentation()
        return self._request('GET', '/')

    def status(self) -> Dict[str, Any]:
        
        if self._local:
            return {
                'playing': bool(self._terminal.is_playing),
                'stop_requested': bool(self._terminal.stop_requested),
                'play_lock_held': bool(self._terminal.play_lock.locked()),
            }
        return self._request('GET', '/status')

    def words(self) -> List[str]:
        
        if self._local:
            return self._terminal.list_words()
        return self._request('GET', '/words')['words']

    def sounds(self) -> List[str]:
        
        if self._local:
            return self._terminal.list_sounds()
        return self._request('GET', '/sounds')['sounds']

    def validate(self, text: str) -> Dict[str, Any]:
        
        if self._local:
            return self._terminal.validate_text(text)
        return self._request('POST', '/validate', {'text': text})

    def plan(self, text: str, **params) -> Dict[str, Any]:
        
        overrides = _translate_params(params)
        if self._local:
            return self._terminal.plan_broadcast(text, overrides)
        return self._request('POST', '/plan', {'text': text, **overrides})

    def settings(self) -> Dict[str, Any]:
        
        if self._local:
            return self._terminal.snapshot_settings()
        return self._request('GET', '/settings')['settings']

    def update_settings(self, reset: bool = False, **params) -> Dict[str, Any]:
        
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

    def presets(self) -> Dict[str, str]:
        
        if self._local:
            return dict(getattr(self._terminal, 'presets', {}) or {})
        return self._request('GET', '/presets')['presets']

    def preset(self, name: str) -> str:
        
        if self._local:
            presets = getattr(self._terminal, 'presets', {}) or {}
            if name not in presets:
                raise CassieAPIError('预设不存在: {}'.format(name), code='not_found', status=404)
            return presets[name]
        return self._request('GET', '/presets/' + urllib.parse.quote(name))['content']

    def save_preset(self, name: str, content: str) -> Dict[str, Any]:
        
        if self._local:
            self._terminal.presets[name] = content
            self._terminal.save_presets()
            return {'name': name, 'content': content, 'count': len(self._terminal.presets)}
        return self._request('POST', '/presets', {'name': name, 'content': content})

    def delete_preset(self, name: str) -> Dict[str, Any]:
        
        if self._local:
            presets = getattr(self._terminal, 'presets', {}) or {}
            if name not in presets:
                raise CassieAPIError('预设不存在: {}'.format(name), code='not_found', status=404)
            del presets[name]
            self._terminal.save_presets()
            return {'deleted': name, 'count': len(presets)}
        return self._request('DELETE', '/presets/' + urllib.parse.quote(name))

    def play_preset(self, name: str) -> Dict[str, Any]:
        
        if self._local:
            text = self.preset(name)
            self.play(text)
            return {'playing': True, 'name': name, 'text': text}
        return self._request('POST', '/presets/{}/play'.format(urllib.parse.quote(name)))

    def synthesize(self, text: str, output_path: Optional[str] = None, *,
                   filename: Optional[str] = None, **params) -> Dict[str, Any]:
        
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
        
        overrides = _translate_params(params)
        if self._local:
            started, message = self._terminal.start_playback(text, overrides)
            if not started:
                raise CassieAPIError(message, code='playback_rejected', status=409)
            return {'playing': True, 'text': text}
        return self._request('POST', '/play', {'text': text, **overrides})

    def stop(self) -> Dict[str, Any]:
        
        if self._local:
            self._terminal.stop_playback()
            return {'playing': False, 'stop_requested': True}
        return self._request('POST', '/stop')

    def wait_until_done(self, timeout: float = 600.0, poll: float = 0.25) -> bool:
        
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if not self.status()['playing']:
                return True
            _time.sleep(poll)
        return False

    def say(self, text: str, **params) -> Dict[str, Any]:
        
        return self.synthesize(text, **params)

    def save(self, text: str, path: str, **params) -> Dict[str, Any]:
        
        return self.synthesize(text, path, **params)

    def describe(self, text: str, **params) -> Dict[str, Any]:
        
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
        
        with wave.open(path, 'rb') as handle:
            return handle.getnframes() / float(handle.getframerate())

def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()

def synthesize_batch(items: Iterable[Dict[str, Any]], *, mode: str = 'local',
                     base_url: str = DEFAULT_BASE_URL, output_dir: str = '.',
                     **client_kwargs) -> List[Dict[str, Any]]:
    
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
