from bottle import route, run, request, static_file, response, abort, hook
import mimetypes
import base64
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import wave
import contextlib
import math
import random
import pygame
from pydub import AudioSegment
from pydub.silence import detect_leading_silence
import numpy as np
import colorednoise as cn

# 默认静音 pydub 内部的句柄提示；显式配置 -W 时保持原样以便排查。
if not sys.warnoptions:
    import warnings
    warnings.filterwarnings('ignore', category=ResourceWarning)


PROJECT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
AUDIO_BASE_PATH = os.path.join(PROJECT_BASE_PATH, "cassie", "words")
SOUND_BASE_PATH = os.path.join(PROJECT_BASE_PATH, "cassie", "sounds")
AUDIO_EXTENSION = ".wav"
PRESET_FILE = os.path.join(PROJECT_BASE_PATH, "presets.json")
SETTINGS_FILE = os.path.join(PROJECT_BASE_PATH, "settings.json")

API_VERSION = 'v1'
API_PREFIX = '/api/v1'
PROJECT_VERSION = '1.0.0'

# 拖尾系数达到这个值就不需要淡出（正好是历史行为，尾部本身已经衰减到听不见）
CASSIE_TAIL_FADE_REFERENCE = 0.35

# 音频素材与发布包都不随仓库分发，缺素材时把用户引到这里
RELEASES_URL = 'https://github.com/BlueArchive-ba/CASSIE-Broadcast-Generator/releases'
ASSETS_DOWNLOAD_URL = RELEASES_URL

# [preset:名字] 展开的最大层数，兜底防止环引用把内存吃满
MAX_PRESET_DEPTH = 16

# 合成进度回调的线程局部暂存（并发请求不会互相串台）
_PENDING_PROGRESS = threading.local()

# 整句处理时用来把「正文边界 / 含拖尾总时长」传回 interpret_broadcast_text。
# 走线程局部而不是给事件列表挂属性（list 不允许自定义属性），
# 也不会被并发请求互相覆盖。
_PENDING_TIMELINE = threading.local()


SUPPORTED_LANGUAGES = ('zh', 'en')
DEFAULT_LANGUAGE = 'zh'


def normalize_language(value):
    """把取值归一化成 'zh' / 'en'，认不出来时返回 None。

    zh-CN、en_US 这类带地区或分隔符的写法只取主语言标签。
    """
    if value is None:
        return None
    text = str(value).strip().lower().replace('_', '-')
    if not text:
        return None
    primary = text.split('-')[0]
    return primary if primary in SUPPORTED_LANGUAGES else None


MESSAGES = {
    'zh': {
        'content_empty': '内容不能为空',
        'json_object_required': '请求体必须是 JSON 对象',
        'text_must_be_string': 'text 必须是字符串',
        'plan_failed': '解析失败: {error}',
        'read_result_failed': '读取合成结果失败: {error}',
        'unknown_fields': '不支持的参数: {fields}',
        'no_fields': '没有需要修改的参数',
        'spatial_mode_invalid': 'spatial_mode 只能是 {modes}',
        'missing_name': '预设名称不能为空',
        'missing_content': '缺少预设内容 content',
        'preset_not_found': '预设不存在: {name}',
        'api_key_invalid': 'API Key 无效',
        'settings_save_failed': '设置已生效但写入失败: {message}',
        'play_busy': '正在播放中，请稍后再试',
        'play_or_export_busy': '正在播放或导出中，请稍后再试',
        'play_error': '播放错误: {error}',
        'play_done': '播放完成',
        'nothing_to_export': '没有音频可导出',
        'no_export_audio': '没有可导出的音频',
        'wav_write_failed': '写入 WAV 文件失败: {error}',
        'sentence_label': '整句',
        'api_description': 'C.A.S.S.I.E. 广播生成器 HTTP API',
        'cd_missing_params': 'CD 指令参数不足：[cd:start,end,separator]',
        'cd_start_end_not_int': 'CD 指令的起止值必须是整数',
        'cd_start_end_equal': 'CD 指令的起止值不能相同',
        'mtf_invalid_params': 'MTF 指令参数无效：[mtf:word1,number1,word2,number2,scp_count]',
        'backup_missing_unit': 'backup 指令缺少单位名称',
        'warhead_invalid_type': 'warhead 指令类型必须是 start、resume 或 cancelled',
        'warhead_countdown_positive': 'warhead 指令的倒计时必须是正整数',
        'hostile_invalid_params': 'hostile_enter 指令参数无效',
        'channl_offset_invalid': 'channl 指令需要一个秒数偏移，最多支持三位小数',
        'channl_missing_stop': 'channl 指令缺少 [channl:stop]',
        'channl_no_free_channel': 'channl 指令没有可用的独立声道',
        'preset_name_missing': 'preset 指令缺少预设名：[preset:名字]',
        'preset_not_found': 'preset 指令引用了不存在的预设：{0}',
        'preset_cycle': 'preset 指令出现循环引用：{0}',
        'preset_empty': 'preset 指令引用的预设没有内容：{0}',
        'not_found': '[未找到] {item}',
        'bell_missing': '[铃声缺失] {item}',
        'bell_playing': '[播放铃声] {item}',
        'verbose_pause': '[停顿] {seconds}秒',
        'verbose_word': '[{index}/{total}] {word} (音高 {pitch})',
        'verbose_number': '[{index}/{total}] {word} (数字)',
        'verbose_stutter': '[{index}/{total}] {word} (卡顿{count}次, 音高 {pitch}){suffix}',
        'verbose_stutter_full': ', 完整播放',
        'verbose_stutter_only': ', 仅卡顿',
        'spatial_level_0_name': '原始',
        'spatial_level_0_summary': '不削减，与历史版本完全一致',
        'spatial_level_1_name': '轻度',
        'spatial_level_1_summary': '块长翻倍、拖尾略收短；几乎听不出差别',
        'spatial_level_2_name': '中度',
        'spatial_level_2_summary': '块长再翻倍、拖尾明显收短；拖尾变得短促',
        'spatial_level_3_name': '最大加速',
        'spatial_level_3_summary': '块长拉满、拖尾最短；只保留紧贴单词的回声',
        'spatial_level_4_name': '激进',
        'spatial_level_4_summary': '拖尾再收一半；混响变成一层薄薄的尾音',
        'spatial_level_5_name': '极限',
        'spatial_level_5_summary': '拖尾约 1/3 秒；只能听出"刚说完还有一点回响"',
        'spatial_level_6_name': '单声道混响',
        'spatial_level_6_summary': '极限档基础上把立体声混响合成单声道，再快近一倍；'
                                   '干声仍是立体声，只是拖尾左右相同、失去宽度',
        'spatial_mode_word': '逐词',
        'spatial_mode_sentence': '整句',
        'spatial_mode_word_summary': '逐词：每个单词各自加一次混响，拖尾逐词叠加，最贴近原版听感。'
                                     '耗时随词数线性增长。',
        'spatial_mode_sentence_summary': '整句：先把整句话拼好，再整体做一次后处理。拖尾只算一次，'
                                         '长广播明显更快；代价是逐词的音高/效果差异会被统一。',
        'startup_banner': 'C.A.S.S.I.E. {version}  启动于 {started_at}',
        'startup_quality_levels': '  空间效果质量档次: {count} 档',
        'startup_fingerprint': '  功能指纹: {status}{hint}',
        'startup_all_ready': '全部就绪',
        'startup_missing': '缺少 {items}',
        'startup_outdated_hint': '  ← 请确认运行的是最新代码',
        'startup_health_hint': '  /api/v1/health 可查看同样的信息（改了后端务必重启本进程）',
        'startup_open_browser': '请在浏览器中访问 http://localhost:{port}/cassie_play',
        'assets_missing_title': '!! 没有找到音频素材，现在还不能生成任何广播。',
        'assets_missing_where': '   期望目录: {path}',
        'assets_missing_how': '   请运行 CASSIE语音生成/cassie_download.py 下载素材，',
        'assets_missing_how2': '   或从发布页获取: {url}',
        'assets_missing_after': '   下载完成后重启本程序。',
    },
    'en': {
        'content_empty': 'Content cannot be empty',
        'json_object_required': 'Request body must be a JSON object',
        'text_must_be_string': 'text must be a string',
        'plan_failed': 'Failed to parse: {error}',
        'read_result_failed': 'Failed to read the synthesized result: {error}',
        'unknown_fields': 'Unsupported parameters: {fields}',
        'no_fields': 'No parameters to update',
        'spatial_mode_invalid': 'spatial_mode must be one of: {modes}',
        'missing_name': 'Preset name cannot be empty',
        'missing_content': 'Missing preset content',
        'preset_not_found': 'Preset not found: {name}',
        'api_key_invalid': 'Invalid API key',
        'settings_save_failed': 'Settings applied, but writing them failed: {message}',
        'play_busy': 'Already playing, please try again later',
        'play_or_export_busy': 'Already playing or exporting, please try again later',
        'play_error': 'Playback error: {error}',
        'play_done': 'Playback finished',
        'nothing_to_export': 'No audio to export',
        'no_export_audio': 'No audio available to export',
        'wav_write_failed': 'Failed to write the WAV file: {error}',
        'sentence_label': 'sentence',
        'api_description': 'C.A.S.S.I.E. broadcast generator HTTP API',
        'cd_missing_params': '[cd] command is missing parameters: [cd:start,end,separator]',
        'cd_start_end_not_int': '[cd] start and end must be integers',
        'cd_start_end_equal': '[cd] start and end must not be equal',
        'mtf_invalid_params': '[mtf] invalid parameters: [mtf:word1,number1,word2,number2,scp_count]',
        'backup_missing_unit': '[backup] command is missing the unit name',
        'warhead_invalid_type': '[warhead] type must be start, resume or cancelled',
        'warhead_countdown_positive': '[warhead] the countdown must be a positive integer',
        'hostile_invalid_params': '[hostile_enter] invalid parameters',
        'channl_offset_invalid': '[channl] needs a second offset with at most 3 decimal places',
        'channl_missing_stop': '[channl] command is missing [channl:stop]',
        'channl_no_free_channel': '[channl] command has no free dedicated channel',
        'preset_name_missing': '[preset] command is missing a preset name: [preset:name]',
        'preset_not_found': '[preset] references a preset that does not exist: {0}',
        'preset_cycle': '[preset] circular reference: {0}',
        'preset_empty': '[preset] references a preset with no content: {0}',
        'not_found': '[not found] {item}',
        'bell_missing': '[missing bell] {item}',
        'bell_playing': '[playing bell] {item}',
        'verbose_pause': '[pause] {seconds}s',
        'verbose_word': '[{index}/{total}] {word} (pitch {pitch})',
        'verbose_number': '[{index}/{total}] {word} (number)',
        'verbose_stutter': '[{index}/{total}] {word} (stutter x{count}, pitch {pitch}){suffix}',
        'verbose_stutter_full': ', full playback',
        'verbose_stutter_only': ', stutter only',
        'spatial_level_0_name': 'Original',
        'spatial_level_0_summary': 'No reduction, identical to earlier versions',
        'spatial_level_1_name': 'Light',
        'spatial_level_1_summary': 'Block size doubled, tail slightly shortened; barely audible',
        'spatial_level_2_name': 'Moderate',
        'spatial_level_2_summary': 'Block size doubled again, tail clearly shortened; the tail becomes brief',
        'spatial_level_3_name': 'Maximum speed',
        'spatial_level_3_summary': 'Block size maxed out, shortest tail; only echoes hugging the words remain',
        'spatial_level_4_name': 'Aggressive',
        'spatial_level_4_summary': 'Tail halved again, reverb becomes a thin layer of tail',
        'spatial_level_5_name': 'Extreme',
        'spatial_level_5_summary': 'Tail around 1/3 second; only a hint of ring-out after each word',
        'spatial_level_6_name': 'Mono reverb',
        'spatial_level_6_summary': 'Builds on Extreme by collapsing the stereo reverb to mono, '
                                   'nearly doubling the speed again; the dry signal stays stereo, '
                                   'only the tail loses its width',
        'spatial_mode_word': 'Per word',
        'spatial_mode_sentence': 'Per sentence',
        'spatial_mode_word_summary': 'Per word: each word gets its own reverb pass and the tails '
                                     'stack word by word, closest to the original sound. Cost grows '
                                     'linearly with the word count.',
        'spatial_mode_sentence_summary': 'Per sentence: the whole sentence is assembled first and '
                                         'post-processed once. The tail is computed only once, which '
                                         'is much faster on long broadcasts; the trade-off is that '
                                         'per-word pitch and effect differences are unified.',
        'startup_banner': 'C.A.S.S.I.E. {version}  started at {started_at}',
        'startup_quality_levels': '  Spatial effect quality tiers: {count}',
        'startup_fingerprint': '  Feature fingerprint: {status}{hint}',
        'startup_all_ready': 'all ready',
        'startup_missing': 'missing {items}',
        'startup_outdated_hint': '  <- please make sure the latest code is running',
        'startup_health_hint': '  /api/v1/health shows the same information '
                               '(always restart this process after backend changes)',
        'startup_open_browser': 'Open http://localhost:{port}/cassie_play in your browser',
        'assets_missing_title': '!! Audio assets not found — no broadcast can be generated yet.',
        'assets_missing_where': '   Expected directory: {path}',
        'assets_missing_how': '   Run CASSIE语音生成/cassie_download.py to fetch the assets,',
        'assets_missing_how2': '   or get them from the releases page: {url}',
        'assets_missing_after': '   Restart this program once the download finishes.',
    },
}


_REQUEST_LANG = threading.local()

_PROCESS_LANGUAGE = normalize_language(os.environ.get('CASSIE_LANG')) or DEFAULT_LANGUAGE


def current_language():
    """当前生效的语言：请求内用请求语言，请求外回落进程语言（默认 zh）。"""
    language = getattr(_REQUEST_LANG, 'value', None)
    return language if language in SUPPORTED_LANGUAGES else _PROCESS_LANGUAGE


def set_language(value):
    """写入当前线程的语言，取值不合法时回落默认语言。"""
    _REQUEST_LANG.value = normalize_language(value) or DEFAULT_LANGUAGE


def language_from_request():
    """按 查询参数 lang → 请求头 X-Cassie-Lang → 默认语言 的顺序判定语言。

    显式传了 lang 但取值不认识（例如 fr）时直接回落默认语言，不再看请求头。
    """
    for value in (request.query.get('lang'), request.headers.get('X-Cassie-Lang')):
        if value is None or not str(value).strip():
            continue
        return normalize_language(value) or DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


@hook('before_request')
def _write_request_language():
    """每个请求开始时写入语言，所有路由（含 /play、/export、/api/v1/*）自动覆盖。"""
    set_language(language_from_request())


def language_join(items, zh_separator=' 或 ', en_separator=' or '):
    """按当前语言选择连接词，用来把枚举值拼进提示文案。"""
    separator = zh_separator if current_language() == DEFAULT_LANGUAGE else en_separator
    return separator.join(items)


def tr(key, **kwargs):
    """取当前请求语言的文案。

    缺失时先回落中文，再回落 key 本身；插值统一走 .format(**kwargs)。
    """
    template = (MESSAGES.get(current_language()) or {}).get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LANGUAGE].get(key)
    if template is None:
        return key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


# API 与前端面板共用的可调参数：(键, 默认值)
SYNTHESIS_PARAM_DEFAULTS = {
    'pitch': 1.0,
    'speed': -10,
    'enable_number_reading': False,
    'include_bell': False,
    'enable_special_bell': False,
    'low_cut_freq': 0.0,
    'high_cut_freq': 0.0,
    'mid_boost_gain': 2.0,
    'overdrive_gain': 0.0,
    'clip_threshold': 0.0,
    'compressor_threshold': -12.0,
    'compressor_ratio': 6.0,
    'reverb_enabled': True,
    'reverb_pre_delay': 18.0,
    'reverb_room_size': 1.0,
    'reverb_decay_time': 5.5,
    'reverb_damping': 4000.0,
    'reverb_diffusion': 0.72,
    'reverb_tail_brightness': 0.55,
    'reverb_wet': 0.35,
    'treble_stretch': 800.0,
    'treble_tail_gain': -28.0,
    'noise_volume': -35.0,
    'noise_type': 'pink',
    'stutter_duration': 0.14,
    'bell_lead_time': 3,
    'bell_extra_duration': 3.0,
    'special_bell_start': 'bell_start.wav',
    'special_bell_end': 'bell_end.wav',
    'broadcast_effect_enabled': False,
    'spatial_quality': 0,
    'spatial_mode': 'word',
}

# 允许通过 API 改动、且会被设置快照覆盖的字段
API_MUTABLE_FIELDS = (
    'pitch', 'speed', 'enable_number_reading', 'include_bell', 'enable_special_bell',
    'low_cut_freq', 'high_cut_freq', 'mid_boost_gain', 'overdrive_gain', 'clip_threshold',
    'compressor_threshold', 'compressor_ratio', 'reverb_enabled', 'reverb_pre_delay',
    'reverb_room_size', 'reverb_decay_time', 'reverb_damping', 'reverb_diffusion',
    'reverb_tail_brightness', 'reverb_wet', 'treble_stretch', 'treble_tail_gain',
    'noise_volume', 'noise_type', 'stutter_duration', 'bell_lead_time',
    'bell_extra_duration', 'special_bell_start', 'special_bell_end',
    'broadcast_effect_enabled',
    'spatial_quality', 'spatial_mode',
)

pygame.mixer.init()
pygame.mixer.set_num_channels(9)

nato_map = {
    'alpha': 'a', 'bravo': 'b', 'charlie': 'c', 'delta': 'd',
    'echo': 'e', 'foxtrot': 'f', 'golf': 'g', 'hotel': 'h',
    'india': 'i', 'juliett': 'j', 'kilo': 'k', 'lima': 'l',
    'mike': 'm', 'november': 'n', 'oscar': 'o', 'papa': 'p',
    'quebec': 'q', 'romeo': 'r', 'sierra': 's', 'tango': 't',
    'uniform': 'u', 'victor': 'v', 'whiskey': 'w', 'xray': 'x',
    'yankee': 'y', 'zulu': 'z'
}


port = 8080  # 默认端口号

class CASSIETerminal:
    def __init__(self):
        self.is_playing = False
        self.enable_bell = False
        self.enable_special_bell = False
        self.special_bell_start = 'bell_start.wav'
        self.special_bell_end = 'bell_end.wav'
        self.enable_number_reading = False
        self.verbose_mode = False
        self.stop_requested = False
        self.stutter_duration = 0.14
        self.word_channel = 0
        self.bell_channel = 8
        self.current_input = ""
        self.preset_file = PRESET_FILE
        self.settings_file = SETTINGS_FILE
        self.word_set = self.load_word_set()
        self.load_presets()
        self.pitch = 1.0
        self.speed = 20
        self.bell_lock = threading.Lock()
        self.play_lock = threading.Lock()
        # API 每次调用都会临时覆盖参数，用这把锁保证还原过程不被打断
        self.settings_lock = threading.RLock()
        self.bell_lead_time = 3
        self.bell_extra_duration = 3.0

        # 测试数值
        self.broadcast_effect_enabled = False
        self.include_bell = False
        self.low_cut_freq = 0
        self.high_cut_freq = 0
        self.mid_boost_gain = 2.0
        self.overdrive_gain = 0.0
        self.clip_threshold = 0.0
        self.compressor_threshold = -12.0
        self.compressor_ratio = 6.0
        self.compressor_attack = 2.0
        self.compressor_release = 50.0
        self.reverb_enabled = True
        self.reverb_pre_delay = 18.0          # ms，直达声与首次反射之间
        self.reverb_room_size = 1.0           # 反射间距缩放系数
        self.reverb_decay_time = 5.5          # RT60，单位秒。走廊建议 3~8
        self.reverb_damping = 4000.0          # 高频吸收：4 kHz 相对低频的衰减时间比，500~4000
        self.reverb_diffusion = 0.72          # 反馈矩阵扩散强度
        self.reverb_tail_brightness = 0.55    # 尾音中高频占比
        self.reverb_wet = 0.35                # 混响在总输出中的占比
        self.reverb_early_reflections = True  # 是否叠加离散早期反射
        self.spatial_quality = 0
        self.spatial_mode = 'word'
        self._reverb_cache = {}
        self.noise_volume = -35.0
        self.noise_type = 'pink'
        self.treble_stretch = 800.0
        self.treble_tail_gain = -28.0
        self.hiss_enabled = True
        self.hiss_start_freq = 2000.0
        self.hiss_duration = 4000.0
        self.hiss_decay_rate = 0.92
        self.hiss_blur_filter = 3000.0
        self.hiss_mix_ratio = 0.30

        self.stored_settings = self.apply_stored_settings()
        # 进程启动时刻，配合 /health 的 features 判断跑的是不是最新代码
        self.started_at = datetime.datetime.now().isoformat(timespec='seconds')

    def load_word_set(self):
        word_set = set()
        if os.path.exists(AUDIO_BASE_PATH):
            for f in os.listdir(AUDIO_BASE_PATH):
                if f.endswith(AUDIO_EXTENSION):
                    word_set.add(f[:-len(AUDIO_EXTENSION)])
        for nato_word in nato_map.keys():
            word_set.add(nato_word)
        for letter in 'abcdefghijklmnopqrstuvwxyz':
            word_set.add('_' + letter)
        for i in range(1, 10):
            if os.path.exists(os.path.join(AUDIO_BASE_PATH, f'g{i}{AUDIO_EXTENSION}')):
                word_set.add(f'g{i}')
        return word_set

    def load_presets(self):
        if os.path.exists(self.preset_file):
            try:
                with open(self.preset_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.presets = json.loads(content)
                    else:
                        self.presets = {}
            except:
                self.presets = {}
        else:
            self.presets = {}

    def save_presets(self):
        with open(self.preset_file, 'w', encoding='utf-8') as f:
            json.dump(self.presets, f, ensure_ascii=False, indent=2)

    # 高级设置落盘到 settings.json，只保存允许外部调整的字段。

    def load_settings(self):
        """读取上次保存的高级设置，缺失或损坏时静默使用默认值。"""
        if not os.path.exists(self.settings_file):
            return {}
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                return {}
            stored = json.loads(content)
        except Exception:
            return {}
        if not isinstance(stored, dict):
            return {}
        return {key: value for key, value in stored.items()
                if key in API_MUTABLE_FIELDS}

    def save_settings(self):
        """把当前可调参数写入 settings.json。"""
        payload = {key: getattr(self, key, SYNTHESIS_PARAM_DEFAULTS.get(key))
                   for key in API_MUTABLE_FIELDS}
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True, ''
        except Exception as error:
            return False, str(error)

    def apply_stored_settings(self):
        """启动时套用已保存的设置，并返回生效的字段。"""
        stored = self.load_settings()
        for key, value in stored.items():
            if key in ('spatial_quality',):
                value = self.quality_profile(value)['level']
            elif key == 'spatial_mode':
                value = value if value in self.SPATIAL_MODES else 'word'
            setattr(self, key, value)
        self._reverb_cache.clear()
        return stored

    def get_audio_duration(self, filepath):
        if not os.path.exists(filepath):
            return 0
        try:

            with contextlib.closing(wave.open(filepath, 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        except:
            return 0.5

    def get_special_bell_path(self, filename, fallback):
        candidates = [
            os.path.join(SOUND_BASE_PATH, filename),
            os.path.join(AUDIO_BASE_PATH, filename)
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return os.path.join(SOUND_BASE_PATH, fallback)

    def stop_all_audio(self):
        for channel in range(pygame.mixer.get_num_channels()):
            pygame.mixer.Channel(channel).stop()

    def wait_for_channels(self, channels=None, timeout=600):
        channels = list(range(pygame.mixer.get_num_channels())) if channels is None else channels
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(pygame.mixer.Channel(channel).get_busy() for channel in channels):
                return True
            time.sleep(0.01)
        return False


    def generate_noise(self, duration_ms, sample_rate=44100, channels=1, sample_width=2, noise_type='pink'):

        num_samples = int(duration_ms * sample_rate / 1000)
        if noise_type == 'pink':
            noise = cn.powerlaw_psd_gaussian(1, num_samples)
        else:
            noise = cn.powerlaw_psd_gaussian(0, num_samples)
        max_val = 2 ** (sample_width * 8 - 1) - 1
        noise = noise / np.max(np.abs(noise)) * max_val * 0.3
        noise = noise.astype(np.int16)
        if channels > 1:
            noise = np.tile(noise, channels)
        return AudioSegment(
            noise.tobytes(),
            frame_rate=sample_rate,
            sample_width=sample_width,
            channels=channels
        )

    def generate_treble_tail(self, audio):
        """从音频高频成分中提取主频，生成平滑衰减的高频尾音。"""
        duration_ms = max(0.0, float(self.treble_stretch))
        if duration_ms <= 0 or len(audio) < 20:
            return AudioSegment.empty()

        try:
            high_band = audio.high_pass_filter(1500)
            samples = np.asarray(high_band.get_array_of_samples(), dtype=np.float64)
            if high_band.channels > 1:
                samples = samples.reshape((-1, high_band.channels)).mean(axis=1)
            if samples.size < 32:
                return AudioSegment.empty()

            window_size = min(samples.size, max(256, int(high_band.frame_rate * 0.12)))
            analysis = samples[-window_size:]
            analysis *= np.hanning(analysis.size)
            spectrum = np.abs(np.fft.rfft(analysis))
            frequencies = np.fft.rfftfreq(analysis.size, 1.0 / high_band.frame_rate)
            upper_frequency = min(12000.0, high_band.frame_rate / 2.0 - 100.0)
            valid = (frequencies >= 1500.0) & (frequencies <= upper_frequency)
            if not np.any(valid):
                return AudioSegment.empty()
            peak_index = np.where(valid)[0][np.argmax(spectrum[valid])]
            frequency = frequencies[peak_index]
            rms = float(np.sqrt(np.mean(analysis ** 2)))
            if rms < 1.0:
                return AudioSegment.empty()

            sample_count = max(1, int(duration_ms * high_band.frame_rate / 1000.0))
            time_axis = np.arange(sample_count, dtype=np.float64) / high_band.frame_rate
            envelope = np.exp(-3.0 * time_axis / max(duration_ms / 1000.0, 0.001))
            fade_in = min(sample_count, int(high_band.frame_rate * 0.008))
            if fade_in > 1:
                envelope[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
            amplitude = min(32767.0, rms * (10.0 ** (self.treble_tail_gain / 20.0)))
            tail = np.sin(2.0 * np.pi * frequency * time_axis) * envelope * amplitude
            tail = np.clip(tail, -32768, 32767).astype(np.int16)
            if audio.channels > 1:
                tail = np.tile(tail[:, None], (1, audio.channels)).reshape(-1)
            return AudioSegment(tail.tobytes(), frame_rate=audio.frame_rate,
                                sample_width=2, channels=audio.channels)
        except Exception:
            return AudioSegment.empty()


    FDN_DELAY_LINES = (941, 1093, 1229, 1361, 1483, 1609, 1721, 1879)
    FDN_BLOCK = 64
    FDN_MIN_HF_RATIO = 0.4
    # 反馈回路内阻尼低通的极点。上限 0.8：再接近 1 的话
    # pole^(-段长) 会超出 float64 的有效位数，低频反而被压掉。
    FDN_DAMPING_POLE = 0.8
    FDN_DAMPING_CHUNK = 64
    REVERB_SEND_GAIN = 0.45

    SPATIAL_QUALITY_LEVELS = (
        {
            'level': 0,
            'name': '原始',
            'summary': '不削减，与历史版本完全一致',
            'block': 64,
            'tail_factor': 0.35,
            'min_tail_sec': 0.06,
            'mono_reverb': False,
        },
        {
            'level': 1,
            'name': '轻度',
            'summary': '块长翻倍、拖尾略收短；几乎听不出差别',
            'block': 128,
            'tail_factor': 0.28,
            'min_tail_sec': 0.06,
            'mono_reverb': False,
        },
        {
            'level': 2,
            'name': '中度',
            'summary': '块长再翻倍、拖尾明显收短；拖尾变得短促',
            'block': 256,
            'tail_factor': 0.18,
            'min_tail_sec': 0.05,
            'mono_reverb': False,
        },
        {
            'level': 3,
            'name': '最大加速',
            'summary': '块长拉满、拖尾最短；只保留紧贴单词的回声',
            'block': 941,
            'tail_factor': 0.10,
            'min_tail_sec': 0.04,
            'mono_reverb': False,
        },
        {
            'level': 4,
            'name': '激进',
            'summary': '拖尾再收一半；混响变成一层薄薄的尾音',
            'block': 941,
            'tail_factor': 0.060,
            'min_tail_sec': 0.03,
            'mono_reverb': False,
        },
        {
            'level': 5,
            'name': '极限',
            'summary': '拖尾约 1/3 秒；只能听出"刚说完还有一点回响"',
            'block': 941,
            'tail_factor': 0.030,
            'min_tail_sec': 0.02,
            'mono_reverb': False,
        },
        {
            'level': 6,
            'name': '单声道混响',
            'summary': '极限档基础上把立体声混响合成单声道，再快近一倍；'
                       '干声仍是立体声，只是拖尾左右相同、失去宽度',
            'block': 941,
            'tail_factor': 0.030,
            'min_tail_sec': 0.02,
            'mono_reverb': True,
        },
    )

    SPATIAL_MODES = ('word', 'sentence')

    @classmethod
    def quality_profile(cls, level):
        """取某个空间效果质量档次的参数，非法值回落到第 0 档。"""
        try:
            index = int(level)
        except (TypeError, ValueError):
            index = 0
        index = min(max(index, 0), len(cls.SPATIAL_QUALITY_LEVELS) - 1)
        return cls.SPATIAL_QUALITY_LEVELS[index]

    def spatial_profile(self):
        """当前生效的质量档次。"""
        return self.quality_profile(getattr(self, 'spatial_quality', 0))

    @staticmethod
    def _build_hadamard(size):
        """生成 size 阶归一化 Hadamard 矩阵，用作反馈矩阵。

        反馈矩阵必须是正交矩阵，否则网络会发散；Hadamard 矩阵各项为 ±1，
        任意两条延迟线之间的反射等强度，正好给出走廊里无方向感的密集反射。
        """
        matrix = np.ones((1, 1), dtype=np.float64)
        while matrix.shape[0] < size:
            matrix = np.block([[matrix, matrix], [matrix, -matrix]])
        return matrix / math.sqrt(matrix.shape[0])

    @staticmethod
    def _fft_convolve(signal, impulse):
        """基于 FFT 的一维卷积，输出长度固定为 len(signal) + len(impulse) - 1。"""
        total = len(signal) + len(impulse) - 1
        size = 1 << max(1, int(total - 1).bit_length())
        spectrum = np.fft.rfft(signal, size) * np.fft.rfft(impulse, size)
        return np.fft.irfft(spectrum, size)[:total]

    def _prepare_fdn(self, frame_rate, channel):
        """准备一组 FDN 参数（延迟线、反馈增益、阻尼极点、扩散矩阵）。

        左右声道使用略微不同的延迟线长度，制造自然的立体声去相关。
        结果只与参数有关、与音频内容无关，因此按参数缓存。
        """
        delay_lines = np.asarray(self.FDN_DELAY_LINES, dtype=np.float64)
        count = len(delay_lines)
        if channel > 0:
            delay_lines = delay_lines * (1.0 + 0.019 * (channel % 2) + 0.011 * (channel // 2))

        room_size = float(np.clip(self.reverb_room_size, 0.2, 3.0))
        decay = float(np.clip(self.reverb_decay_time, 0.1, 30.0))
        damping = float(np.clip(self.reverb_damping, 200.0, 18000.0))
        diffusion = float(np.clip(self.reverb_diffusion, 0.0, 1.0))

        delays = np.maximum(16, np.round(delay_lines * room_size)).astype(np.int64)
        max_delay = int(delays.max())

        feedback = np.clip(10.0 ** (-3.0 * delays / (decay * frame_rate)), 0.0, 0.9995)

        damping_mix, damping_pole = self._solve_damping(self.damping_ratio(damping))

        matrix = self._build_hadamard(count)
        matrix = diffusion * matrix + (1.0 - diffusion) * np.eye(count)

        # 质量档次决定块长：块长只影响主循环迭代次数，不改变声音。
        # 上限受两条约束：不超过最短延迟线（否则环形缓冲区读写会互相覆盖，
        # 这也是原来 FDN_BLOCK=64 的由来），以及不超过阻尼分段的精度上限。
        profile = self.spatial_profile()
        block_cap = int(delays.min())
        block = max(8, min(int(profile['block']), block_cap))

        return {
            'frame_rate': int(frame_rate),
            'channel': int(channel),
            'count': count,
            'delays': delays,
            'max_delay': max_delay,
            'feedback': feedback,
            'damping_mix': damping_mix,
            'damping_pole': damping_pole,
            'matrix': matrix,
            'block': block,
            'decay': decay,
            'room_size': room_size,
            'quality_level': int(profile['level']),
        }

    def _fdn_key(self, frame_rate, channel):
        # 质量档次必须进缓存键：它改变 block，换档后必须重新准备参数
        return (int(frame_rate), int(channel),
                int(self.spatial_profile()['level']),
                round(float(np.clip(self.reverb_room_size, 0.2, 3.0)), 3),
                round(float(np.clip(self.reverb_decay_time, 0.1, 30.0)), 2),
                round(float(np.clip(self.reverb_damping, 200.0, 18000.0)), 1),
                round(float(np.clip(self.reverb_diffusion, 0.0, 1.0)), 2))

    def _fdn_parameters(self, frame_rate, channel):
        """带缓存的 FDN 参数。"""
        key = self._fdn_key(frame_rate, channel)
        cached = self._reverb_cache.get(key)
        if cached is None:
            cached = self._prepare_fdn(frame_rate, channel)
            if len(self._reverb_cache) > 24:
                self._reverb_cache.clear()
            self._reverb_cache[key] = cached
        return cached

    def _run_fdn(self, source, params, *, inject_burst=False, tail_samples=None,
                 collect_energy=False):
        """把 source 送进 FDN，返回 (湿声, 能量轨迹)。

        source 有 N 个采样，N 个采样之后不再注入输入，但网络继续跑
        tail_samples 个采样把拖尾放完。这正是「拖尾不占时间线」的关键：
        输出长度由尾长决定，而不是由冲激响应总长决定。
        """
        delays = params['delays']
        count = params['count']
        max_delay = params['max_delay']
        feedback = params['feedback']
        damping_mix = params['damping_mix']
        pole = params['damping_pole']
        matrix = params['matrix']
        block = params['block']

        source = np.asarray(source, dtype=np.float64).reshape(-1)
        source_length = source.size
        if tail_samples is None:
            tail_samples = int(params['decay'] * params['frame_rate'] * 1.05) + max_delay
        total = source_length + max(0, int(tail_samples))
        if total <= 0:
            return np.zeros(0), []

        buffer = np.zeros((max_delay, count), dtype=np.float64)
        wet = np.zeros(total, dtype=np.float64)
        line_columns = np.arange(count)

        burst = None
        if inject_burst:
            burst = np.random.RandomState(0x43415353).randn(count, block).astype(np.float64)
            burst /= math.sqrt(float(np.mean(burst ** 2)))

        position = 0
        read_offsets = max_delay - delays
        damp_state = np.zeros(count, dtype=np.float64)
        energy_trace = [] if collect_energy else None
        while position < total:
            span = min(block, total - position)
            rows = (read_offsets[:, None] + position + np.arange(span)[None, :]) % max_delay
            read = buffer[rows, line_columns[:, None]]

            wet[position:position + span] = read.sum(axis=0)
            mixed = matrix @ read

            if inject_burst and position < block:
                take = min(span, block - position)
                mixed[:, :take] += burst[:, :take]
            elif source_length and position < source_length:
                take = min(span, source_length - position)
                mixed[:, :take] += source[position:position + take][None, :]

            if damping_mix > 1e-6:
                for begin in range(0, span, self.FDN_DAMPING_CHUNK):
                    end = min(begin + self.FDN_DAMPING_CHUNK, span)
                    steps = np.arange(end - begin)
                    curve = pole ** steps
                    segment = mixed[:, begin:end]
                    total_curve = np.cumsum(segment * (curve ** -1)[None, :], axis=1)
                    lowpass = (1.0 - pole) * curve[None, :] * total_curve
                    lowpass = lowpass + (pole ** (steps + 1))[None, :] * damp_state[:, None]
                    damp_state = lowpass[:, -1].copy()
                    mixed[:, begin:end] = ((1.0 - damping_mix) * segment
                                           + damping_mix * lowpass)

            write_positions = (position + np.arange(span)[None, :]) % max_delay
            buffer[write_positions, line_columns[:, None]] = mixed * feedback[:, None]
            if collect_energy:
                energy_trace.append((float(np.sum(buffer ** 2)), block))
            position += span

        if not np.all(np.isfinite(wet)):
            wet = np.zeros(0, dtype=np.float64)
        if collect_energy:
            return wet, energy_trace
        return wet, []

    @staticmethod
    def damping_ratio(damping_hz):
        """把「高频吸收」参数（Hz）映射成 4 kHz 相对低频的衰减时间比。

        4000 Hz 及以上表示不额外吸收高频（比值 1.0），越小表示高频衰减越快。
        下限 FDN_MIN_HF_RATIO 是当前阻尼结构能达到的最大吸收，
        再往下要求就超出可调范围了。
        映射是线性的，因此滑杆在整个可用区间内手感均匀。
        """
        try:
            value = float(damping_hz)
        except (TypeError, ValueError):
            value = 4000.0
        position = (4000.0 - min(max(value, 500.0), 4000.0)) / (4000.0 - 500.0)
        return 1.0 + position * (CASSIETerminal.FDN_MIN_HF_RATIO - 1.0)

    @staticmethod
    def _solve_damping(target_ratio):
        """反解阻尼参数，使 4 kHz 相对低频的每周期增益等于 target_ratio。

        阻尼结构（反馈回路内）：
            lowpass: lp[n] = pole*lp[n-1] + (1-pole)*x[n]
            y[n]    = (1-mix)*x[n] + mix*lp[n]
        直流处 lp 增益为 1，因此直流总增益恒为 1 —— 低频 RT60 等于设定值；
        4 kHz 处 lp 幅度为 L(4k)，总增益为 (1-mix) + mix*L(4k)。
        令它等于 target_ratio 即可解出 mix：

            mix = (1 - target_ratio) / (1 - L(4k))

        pole 取 0.8：4 kHz 处 L ≈ 0.39，200 Hz 处 L ≈ 0.95。
        mix 从 0 调到 1，4 kHz 的每周期增益从约 0.95 降到约 0.39，
        也就是高频 RT60 可调到低频的 0.4 ~ 1.0 倍。
        不用更接近 1 的极点：cumsum 里的 pole^(-k) 会超出 float64 精度，
        反而把低频拖尾一起压短。

        返回 (mix, pole)。
        """
        pole = float(CASSIETerminal.FDN_DAMPING_POLE)
        if target_ratio >= 1.0:
            return 0.0, pole
        omega = 2.0 * math.pi * 4000.0 / 44100.0
        lowpass = (1.0 - pole) / abs(
            1.0 - pole * complex(math.cos(omega), -math.sin(omega)))
        denominator = 1.0 - lowpass
        if denominator <= 1e-6:
            return 0.0, pole
        mix = (1.0 - target_ratio) / denominator
        return min(1.0, max(0.0, mix)), pole

    def _generate_fdn_tail(self, frame_rate, channel, room_size, decay, damping, diffusion,
                           collect_energy=False):
        """跑一遍空输入的网络，得到走廊混响的冲激响应。

        **当前没有任何调用方**：真实混响走 apply_room_reverb()，不经过这里。
        这个函数是给离线测量/排查用的（可以直接看冲激响应与能量衰减）。

        collect_energy=True 时返回 (冲激响应, 能量轨迹)。
        能量轨迹记录每块的网络存储能量，用于直接测量衰减时间
        （输出抽头会因相位干涉而失真，能量则不会）。
        """
        for key, value in (('reverb_room_size', room_size),
                           ('reverb_decay_time', decay),
                           ('reverb_damping', damping),
                           ('reverb_diffusion', diffusion)):
            setattr(self, key, value)
        params = self._prepare_fdn(frame_rate, channel)
        total = int(decay * frame_rate * 1.05) + params['max_delay']
        total = int(np.clip(total, frame_rate // 10, 90 * frame_rate))
        return self._run_fdn(np.zeros(0), params, inject_burst=True,
                             tail_samples=total, collect_energy=True)

    def apply_room_reverb(self, audio, wet=None):
        """把音频送进走廊混响，返回带拖尾的 AudioSegment。

        直接把音频当作 FDN 的输入，而不是先合成一段冲激响应再做卷积。
        这点很关键：卷积法的输出长度是 len(音频) + len(冲激响应)，
        于是每个单词都会被撑到 RT60 那么长，时间线随之被拉长几十秒；
        直接跑 FDN 时输入结束后只需再跑一小段让拖尾衰减到听不见即可。
        """
        if len(audio) == 0 or audio.sample_width != 2:
            return audio
        wet_gain = float(np.clip(self.reverb_wet if wet is None else wet, 0.0, 1.0))
        if wet_gain <= 0:
            return audio
        try:
            frame_rate = int(audio.frame_rate)
            channels = int(audio.channels)
            samples = np.asarray(audio.get_array_of_samples(), dtype=np.float64)
            frames = samples.reshape((-1, channels)) if channels > 1 else samples.reshape((-1, 1))

            profile = self.spatial_profile()
            decay = float(np.clip(self.reverb_decay_time, 0.1, 30.0))
            pre_delay_ms = max(0.0, float(self.reverb_pre_delay))
            tail_samples = (int(decay * float(profile['tail_factor']) * frame_rate)
                            + int(pre_delay_ms * frame_rate / 1000.0))
            tail_samples = max(tail_samples, int(frame_rate * float(profile['min_tail_sec'])))
            # 收短后的拖尾必须淡出，否则会在尾部硬切出咔哒声
            fade_samples = 0
            if profile['tail_factor'] < CASSIE_TAIL_FADE_REFERENCE:
                fade_samples = min(int(frame_rate * 0.05), tail_samples // 3)

            mono_reverb = bool(profile.get('mono_reverb')) and channels > 1

            wet_parts = []
            if mono_reverb:
                mono_source = frames.mean(axis=1)
                params = self._fdn_parameters(frame_rate, 0)
                wet, _ = self._run_fdn(mono_source, params, tail_samples=tail_samples)
                wet_parts = [wet] * channels
            else:
                for index in range(channels):
                    params = self._fdn_parameters(frame_rate, index)
                    wet, _ = self._run_fdn(frames[:, index], params, tail_samples=tail_samples)
                    wet_parts.append(wet)
            if not wet_parts:
                return audio

            if fade_samples > 1:
                faded = []
                for part in wet_parts:
                    if part.size > fade_samples:
                        part = part.copy()
                        part[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples)
                    faded.append(part)
                wet_parts = faded

            wet_length = max(part.size for part in wet_parts)
            length = max(wet_length, frames.shape[0])
            wet_frames = np.zeros((length, channels), dtype=np.float64)
            for index, part in enumerate(wet_parts):
                wet_frames[:part.size, index] = part

            dry_frames = np.zeros((length, channels), dtype=np.float64)
            dry_frames[:frames.shape[0]] = frames

            dry_rms = float(np.sqrt(np.mean(frames ** 2)))
            wet_rms = float(np.sqrt(np.mean(wet_frames ** 2)))
            if wet_rms > 1e-9 and dry_rms > 1e-9:
                wet_frames = wet_frames * (dry_rms / wet_rms) * self.REVERB_SEND_GAIN

            mixed = dry_frames * (1.0 - 0.25 * wet_gain) + wet_frames * wet_gain
            mixed = self._soft_limit(mixed, 32767.0)

            pcm = np.clip(np.round(mixed), -32768, 32767).astype(np.int16)
            return AudioSegment(pcm.reshape(-1).tobytes(), frame_rate=frame_rate,
                                sample_width=2, channels=channels)
        except Exception:
            traceback.print_exc()
            return audio

    @staticmethod
    def _soft_limit(samples, ceiling):
        """三次方软削波：只对逼近满量程的峰值做压缩。

        不能用「拐点 + tanh(x-knee)」这种叠加式压缩：单词音频的波峰因数很高
        （峰值 30000、RMS 只有 1200 左右），把大量低电平样本一起映射到天花板附近
        反而会把整段电平抬高十几倍。这里对 |x| 在拐点以上做三次方过渡，
        并把 |x| 硬性截到 ceiling，绝不放大小信号。
        """
        knee = ceiling * 0.78
        magnitude = np.abs(samples)
        if magnitude.size == 0 or float(np.max(magnitude)) <= knee:
            return samples
        span = ceiling - knee
        clipped = np.where(
            magnitude <= knee,
            magnitude,
            np.where(magnitude >= ceiling,
                     ceiling,
                     ceiling - span * ((ceiling - magnitude) / span) ** 3))
        return np.sign(samples) * clipped

    def apply_broadcast_effect(self, audio):
        if not self.broadcast_effect_enabled:
            return audio
        try:
            if self.low_cut_freq > 0:
                audio = audio.high_pass_filter(self.low_cut_freq)
            if self.high_cut_freq > 0:
                audio = audio.low_pass_filter(self.high_cut_freq)
            if self.mid_boost_gain != 0:
                audio = audio + self.mid_boost_gain
            if self.overdrive_gain > 0 and self.clip_threshold > 0:
                audio = audio + self.overdrive_gain
                samples = audio.get_array_of_samples()
                max_val = 32767
                clip_val = int(max_val * self.clip_threshold)
                for i in range(len(samples)):
                    if samples[i] > clip_val:
                        samples[i] = clip_val
                    elif samples[i] < -clip_val:
                        samples[i] = -clip_val
                audio = audio._spawn(samples)
            try:
                audio = audio.compress_dynamic(
                    threshold=self.compressor_threshold,
                    ratio=self.compressor_ratio,
                    attack=self.compressor_attack,
                    release=self.compressor_release
                )
            except Exception:
                pass
            treble_tail = self.generate_treble_tail(audio)
            if len(treble_tail) > 0:
                audio = audio.append(treble_tail, crossfade=min(8, len(treble_tail)))
            if self.noise_volume < 0:
                noise = self.generate_noise(
                    duration_ms=len(audio),
                    sample_rate=audio.frame_rate,
                    channels=audio.channels,
                    sample_width=audio.sample_width,
                    noise_type=getattr(self, 'noise_type', 'pink')
                )
                noise = noise.apply_gain(self.noise_volume)
                if audio.channels == 2 and noise.channels == 1:
                    noise = noise.set_channels(2)
                audio = audio.overlay(noise, position=0, gain_during_overlay=0)
        except Exception as e:

            traceback.print_exc()
            return audio
        return audio

    

    def _prepare_audio(self, audio, pitch=1.0, speed=0, apply_effects=True):
        """音高/语速处理，并按需叠加效果链。

        apply_effects=False 时只做音高与语速处理，用于测量「单词占用多久」——
        效果链里的高音尾音与噪声都会改变音频长度，拿加过效果的长度去排期
        会让语速设置失效（见 interpret_broadcast_text 里的说明）。
        """
        if pitch != 1.0:
            new_frame_rate = int(audio.frame_rate * pitch)
            audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
            audio = audio.set_frame_rate(audio.frame_rate)

        if speed < 0:
            threshold = -35.0
            start_trim = detect_leading_silence(audio, silence_threshold=threshold)
            end_trim = detect_leading_silence(audio.reverse(), silence_threshold=threshold)
            trim_strength = abs(speed) / 20.0
            start_cut = int(start_trim * trim_strength)
            end_cut = int(end_trim * trim_strength)
            if start_cut > 0 or end_cut > 0:
                audio = audio[start_cut:len(audio)-end_cut]

        if apply_effects and self.broadcast_effect_enabled:
            audio = self.apply_broadcast_effect(audio)

        return audio

    @staticmethod
    def load_audio(path, fmt='wav'):
        """读取音频文件，并保证文件句柄被关闭。

        pydub 的 AudioSegment.from_wav(path) 会把打开的文件对象留在
        AudioSegment 内部，只有等到对象被回收才关闭，于是控制台会出现
        「unclosed file」的 ResourceWarning，长时间运行还会耗掉文件描述符。
        换成先自己打开文件、交给 pydub 读完再关闭即可。
        """
        with open(path, 'rb') as handle:
            if fmt == 'wav':
                return AudioSegment.from_wav(handle)
            return AudioSegment.from_file(handle, fmt)

    @staticmethod
    def export_audio(audio, path, fmt='wav'):
        """写出音频文件，并保证文件句柄被关闭。"""
        exported = audio.export(path, format=fmt)
        try:
            exported.close()
        except Exception:
            pass
        return path

    def _play_audio_segment(self, channel, audio, wait=True):
        # 空音频绝不能交给 pygame：AudioSegment.empty() 的 frame_rate 是 1，
        # 导出的 WAV 极短，SDL_mixer 在已经持有其它长音频时会直接越界访问，
        # 整个进程以 0xC0000005 退出（Python 层捕获不到）。
        # 这类事件只用于时间线记账（例如收尾哨兵），本来就不该发声。
        if audio is None:
            return 0.0
        processed_duration = len(audio) / 1000.0
        if processed_duration <= 0:
            return 0.0

        # pydub 的 export() 返回一个没有关闭的文件对象，必须显式关闭，
        # 否则每次播放都会泄漏一个文件描述符（并触发 ResourceWarning）。
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        export_path = temp_file.name
        temp_file.close()
        try:
            exported = audio.export(export_path, format="wav")
            try:
                exported.close()
            except Exception:
                pass
            with open(export_path, 'rb') as handle:
                payload = handle.read()
        finally:
            if os.path.exists(export_path):
                try:
                    os.unlink(export_path)
                except OSError:
                    pass

        sound = pygame.mixer.Sound(io.BytesIO(payload))
        pygame.mixer.Channel(channel).play(sound)
        if wait:
            time.sleep(processed_duration)
        return processed_duration

    def play_audio_on_channel(self, channel, filepath, start_delay=0, pitch=1.0, speed=0, wait=True):
        if start_delay > 0:
            time.sleep(start_delay)
        if not os.path.exists(filepath):
            return

        audio = self.load_audio(filepath)

        if pitch == 1.0 and speed == 0 and not self.broadcast_effect_enabled:
            sound = pygame.mixer.Sound(filepath)
            pygame.mixer.Channel(channel).play(sound)
            duration = self.get_audio_duration(filepath)
            if wait:
                time.sleep(duration)
            return duration

        return self._play_audio_segment(
            channel, self._prepare_audio(audio, pitch=pitch, speed=speed), wait=wait)

    def play_number_on_channel(self, channel, words, pitch=1.0, speed=0, wait=True):
        audio = AudioSegment.empty()
        for word in words:
            filepath = os.path.join(AUDIO_BASE_PATH, word + AUDIO_EXTENSION)
            if os.path.exists(filepath):
                audio += self.load_audio(filepath)
        if len(audio) == 0:
            return
        return self._play_audio_segment(
            channel, self._prepare_audio(audio, pitch=pitch, speed=speed), wait=wait)

    def play_stutter(self, filepath, stutter_count, pitch=1.0, speed=0, channel=None, full_play=True, wait=True):
        if channel is None:
            channel = self.word_channel

        if not os.path.exists(filepath):
            return


        audio = self.load_audio(filepath)

        if pitch != 1.0:
            new_frame_rate = int(audio.frame_rate * pitch)
            audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
            audio = audio.set_frame_rate(audio.frame_rate)

        if speed < 0:
            threshold = -35.0
            start_trim = detect_leading_silence(audio, silence_threshold=threshold)
            end_trim = detect_leading_silence(audio.reverse(), silence_threshold=threshold)
            trim_strength = abs(speed) / 20.0
            start_cut = int(start_trim * trim_strength)
            end_cut = int(end_trim * trim_strength)
            if start_cut > 0 or end_cut > 0:
                audio = audio[start_cut:len(audio)-end_cut]

        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        export_path = temp_file.name
        temp_file.close()
        self.export_audio(audio, export_path)

        duration = self.get_audio_duration(export_path)
        stutter_duration = min(duration, self.stutter_duration)
        sound = pygame.mixer.Sound(export_path)

        total_duration = stutter_duration * stutter_count + (duration if full_play else 0)

        def play_sequence():
            for _ in range(stutter_count):
                pygame.mixer.Channel(channel).play(sound)
                time.sleep(stutter_duration)
                pygame.mixer.Channel(channel).stop()
            if full_play:
                pygame.mixer.Channel(channel).play(sound)
                time.sleep(duration)

        try:
            if wait:
                play_sequence()
            else:
                thread = threading.Thread(target=play_sequence, daemon=True)
                thread.start()
            return total_duration
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    

    SAMPLE_LABELS = {
        'the_vowel': 'the',
        'the_consonant': 'the',
    }

    NUMBER_WORDS = {
        0: 'zero', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
        6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
        11: 'eleven', 12: 'twelve', 13: 'thirteen', 14: 'fourteen',
        15: 'fifteen', 16: 'sixteen', 17: 'seventeen', 18: 'eighteen',
        19: 'nineteen', 20: 'twenty', 30: 'thirty', 40: 'forty',
        50: 'fifty', 60: 'sixty', 70: 'seventy', 80: 'eighty', 90: 'ninety',
    }

    @classmethod
    def render_sample_name(cls, name):
        """把一个音频文件名还原成"听起来是什么"。"""
        text = str(name)
        if text in cls.SAMPLE_LABELS:
            return cls.SAMPLE_LABELS[text]
        if len(text) == 2 and text[0] == '_' and text[1].isalpha():
            return text[1]
        if text.isdigit():
            number = int(text)
            if number in cls.NUMBER_WORDS:
                return cls.NUMBER_WORDS[number]
        return text

    @classmethod
    def spoken_label(cls, item_type, word):
        """把事件转成"实际上会听到什么"的文字（单行）。"""
        return ' '.join(cls.spoken_parts(item_type, word))

    @classmethod
    def spoken_offsets(cls, event, pieces):
        """算出每个片段相对事件起点的偏移毫秒，用于按播放时序输出日志。

        优先用真实段长（piece_durations_ms）：多个片段是几段音频拼起来的，
        各自长度不同，按真实长度定位才能和听到的对上。
        没有段长信息时（例如整句模式下的合并轨）退回按时间槽等分。
        """
        count = len(pieces)
        if count == 0:
            return []
        if count == 1:
            return [0]

        spans = list(event.get('piece_durations_ms') or [])
        if len(spans) == count:
            total = float(sum(spans)) or 1.0
            slot_ms = max(1, int(event.get('end_ms', event['start_ms'])) - int(event['start_ms']))
            offsets = []
            elapsed = 0.0
            for span in spans:
                offsets.append(int(round(elapsed / total * slot_ms)))
                elapsed += span
            return offsets

        slot_ms = max(1, int(event.get('end_ms', event['start_ms'])) - int(event['start_ms']))
        return [int(slot_ms * index / count) for index in range(count)]

    @classmethod
    def spoken_parts(cls, item_type, word):
        """把事件拆成"逐个念出来的片段"。

        数字是一串音频拼起来的：123 读作
            ['1', 'hundred', 'and', '20', '3'] -> one / hundred / and / twenty / three
        播放日志要按片段逐条输出，才能和听到的逐个对上。
        """
        if item_type == 'number':
            parts = word if isinstance(word, (list, tuple)) else [word]
            return [cls.render_sample_name(part) for part in parts]
        if isinstance(word, (list, tuple)):
            return [cls.render_sample_name(part) for part in word]
        return [cls.render_sample_name(word)]

    def process_number(self, num_str):
        num = float(num_str)
        parts = num_str.split('.')
        integer_part = int(parts[0])
        decimal_part = parts[1] if len(parts) > 1 else None
        result = []
        if integer_part == 0:
            result.append('0')
        elif integer_part > 0:
            if integer_part <= 20:
                result.append(str(integer_part))
            elif integer_part < 100:
                tens = (integer_part // 10) * 10
                units = integer_part % 10
                result.append(str(tens))
                if units > 0:
                    result.append(str(units))
            elif integer_part < 1000:
                hundreds = integer_part // 100
                remainder = integer_part % 100
                result.append(str(hundreds))
                result.append('hundred')
                if remainder > 0:
                    result.append('and')
                    if remainder <= 20:
                        result.append(str(remainder))
                    else:
                        tens = (remainder // 10) * 10
                        units = remainder % 10
                        result.append(str(tens))
                        if units > 0:
                            result.append(str(units))
            elif integer_part < 1000000:
                thousands = integer_part // 1000
                remainder = integer_part % 1000
                result.extend(self.process_number(str(thousands)))
                result.append('thousand')
                if remainder > 0:
                    if remainder < 100:
                        result.append('and')
                    result.extend(self.process_number(str(remainder)))
            elif integer_part < 100000000:
                millions = integer_part // 1000000
                remainder = integer_part % 1000000
                result.extend(self.process_number(str(millions)))
                result.append('million')
                if remainder > 0:
                    if remainder < 100:
                        result.append('and')
                    result.extend(self.process_number(str(remainder)))
            else:
                return None
        if decimal_part:
            result.append('point')
            for digit in decimal_part:
                result.append(digit)
        return result

    def play_bell_audio(self, filepath):
        if not os.path.exists(filepath):
            return 0
        with self.bell_lock:
            channel = pygame.mixer.Channel(self.bell_channel)
            channel.stop()
            sound = pygame.mixer.Sound(filepath)
            channel.play(sound)
        return self.get_audio_duration(filepath)

    def parse_broadcast_text(self, text, enable_number_reading=None):
        if not text or not text.strip():
            return {'queue': [], 'errors': [tr('content_empty')]}

        errors = []

        def replace_command(pattern, builder):
            nonlocal text
            while True:
                match = re.search(pattern, text)
                if not match:
                    return
                replacement = builder(match)
                if replacement is None:
                    text = text.replace(match.group(0), '')
                else:
                    text = text.replace(match.group(0), replacement, 1)

        def resolve_preset_content(name, path):
            """取预设内容，并把内层 [preset:...] 递归展开。

            path 是当前已经走过的预设链，用来检测循环引用。
            返回 (文本, 是否成功)。失败时文本为空。
            """
            name = (name or '').strip()
            presets = getattr(self, 'presets', {}) or {}
            if not name:
                errors.append(tr('preset_name_missing'))
                return '', False
            if name not in presets:
                errors.append(tr('preset_not_found').format(name))
                return '', False
            if name in path:
                errors.append(tr('preset_cycle').format(
                    ' -> '.join(path + [name])))
                return '', False
            if len(path) >= MAX_PRESET_DEPTH:
                errors.append(tr('preset_cycle').format(
                    ' -> '.join(path + [name])))
                return '', False
            content = presets[name]
            if not isinstance(content, str) or not content.strip():
                errors.append(tr('preset_empty').format(name))
                return '', False

            inner = re.compile(r'\[preset:([^\]]*)\]', re.IGNORECASE)
            failed = []

            def substitute(match):
                text, ok = resolve_preset_content(match.group(1), path + [name])
                if not ok:
                    failed.append(match.group(1))
                    return ''
                return text

            expanded = inner.sub(substitute, content)
            if failed:
                return expanded, True
            return expanded, True

        def expand_all_presets():
            nonlocal text
            pattern = re.compile(r'\[preset:([^\]]*)\]', re.IGNORECASE)
            for _ in range(MAX_PRESET_DEPTH):
                match = pattern.search(text)
                if not match:
                    return
                content, ok = resolve_preset_content(match.group(1), [])
                if not ok:
                    text = text[:match.start()] + text[match.end():]
                    continue
                text = text[:match.start()] + content + text[match.end():]
            errors.append(tr('preset_cycle').format('超出最大展开层数'))

        expand_all_presets()

        def build_cd(match):
            parts = [part.strip() for part in match.group(1).split(',')]
            if len(parts) < 2:
                errors.append(tr('cd_missing_params'))
                return ''
            try:
                start = int(parts[0])
                end = int(parts[1])
            except ValueError:
                errors.append(tr('cd_start_end_not_int'))
                return ''
            if start == end:
                errors.append(tr('cd_start_end_equal'))
                return ''

            separator = parts[2] if len(parts) > 2 else ' . '
            sep_with_spaces = ' {} '.format(separator.strip())
            step = -1 if start > end else 1
            numbers = range(start, end + step, step)
            return sep_with_spaces.join(str(number) for number in numbers)

        def build_mtf(match):
            parts = [part.strip() for part in match.groups()]
            if (not parts[0] or not parts[2] or
                    not all(part.isdigit() and int(part) > 0 for part in (parts[1], parts[3], parts[4]))):
                errors.append(tr('mtf_invalid_params'))
                return ''
            subject = 'scp+subject' if int(parts[4]) == 1 else 'scp+subjects'
            return ('mobile+task+force+unit {0} {1} designated {2} {3} '
                    'has+entered+the+facility . all+remaining+personnel . '
                    'awating+recontainment . {4} {5} . ').format(
                        parts[0], parts[1], parts[2], parts[3], parts[4], subject)

        def build_backup(match):
            word = match.group(1).strip()
            if not word:
                errors.append(tr('backup_missing_unit'))
                return ''
            return '{} backup unit has+entered+the+facility . '.format(word)

        def build_warhead(match):
            number = match.group(1).strip()
            mode = match.group(2).strip().lower()
            if mode not in ('start', 'resume', 'cancelled'):
                errors.append(tr('warhead_invalid_type'))
                return ''
            if mode != 'cancelled' and (not number.isdigit() or int(number) < 1):
                errors.append(tr('warhead_countdown_positive'))
                return ''
            return 'warhead+cancelled' if mode == 'cancelled' else 'warhead+{} {}s'.format(mode, number)

        def build_hostile(match):
            number, word1, word2, word3 = [part.strip() for part in match.groups()]
            if not number.isdigit() or int(number) < 1 or not word1 or not word2:
                errors.append(tr('hostile_invalid_params'))
                return ''
            return 'attention , all personnel . detected {} {} at {} . {} . '.format(
                number, word1, word2, word3 or 'lethal force authorized')

        replace_command(r'\[cd:([^\]]+)\]', build_cd)
        replace_command(r'\[mtf:([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)\]', build_mtf)
        replace_command(r'\[backup:([^\]]+)\]', build_backup)
        replace_command(r'\[warhead:([^,]+),([^,]+)\]', build_warhead)
        replace_command(r'\[hostile_enter:([^,]+),([^,]+),([^,]+),([^,]+)\]', build_hostile)
        channl_blocks = {}
        block_marker = re.compile(r'\[channl:([^\]]+)\]', re.IGNORECASE)
        output_parts = []
        source_position = 0
        while True:
            opening = block_marker.search(text, source_position)
            if opening is None:
                output_parts.append(text[source_position:])
                break
            offset_text = opening.group(1).strip()
            if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d{1,3})?|\.\d{1,3})', offset_text):
                errors.append(tr('channl_offset_invalid'))
                output_parts.append(text[source_position:opening.start()])
                source_position = opening.end()
                continue
            offset = float(offset_text)

            depth = 1
            closing = None
            scan_position = opening.end()
            while depth:
                marker = block_marker.search(text, scan_position)
                if marker is None:
                    break
                if marker.group(1).strip().lower() == 'stop':
                    depth -= 1
                    if depth == 0:
                        closing = marker
                        break
                else:
                    depth += 1
                scan_position = marker.end()
            if closing is None:
                errors.append(tr('channl_missing_stop'))
                output_parts.append(text[source_position:opening.start()])
                source_position = opening.end()
                continue

            output_parts.append(text[source_position:opening.start()])
            nested = self.parse_broadcast_text(
                text[opening.end():closing.start()], enable_number_reading=enable_number_reading)
            errors.extend(nested['errors'])
            marker = '__cassie_channl_{}_{}__'.format(uuid.uuid4().hex, len(channl_blocks))
            channl_blocks[marker] = (offset, nested['queue'])
            output_parts.append(marker)
            source_position = closing.end()
        text = ''.join(output_parts)

        error_count = 0
        error_match = re.search(r'\[error:(\d+)\]', text)
        if error_match:
            error_count = int(error_match.group(1))
            text = re.sub(r'\[error:\d+\]', '', text)

        segments = re.sub(r'\s+', ' ', text).strip().lower().split()
        queue = []
        previous_number_mode = self.enable_number_reading
        if enable_number_reading is not None:
            self.enable_number_reading = enable_number_reading
        for index, segment in enumerate(segments):
            if segment in channl_blocks:
                offset, nested_queue = channl_blocks[segment]
                queue.append(('channl', offset, nested_queue))
                continue
            parsed = self.parse_segment(segments, index)
            if parsed:
                queue.extend(parsed)
            else:
                errors.append(tr('not_found', item=segment))
        self.enable_number_reading = previous_number_mode

        if error_count > 0:
            word_indices = [index for index, item in enumerate(queue) if item[0] == 'word']
            available_glitches = [name for name in self.word_set if re.match(r'^g\d+$', name)]
            if word_indices and available_glitches:
                for position in sorted(random.sample(word_indices, min(error_count, len(word_indices))), reverse=True):
                    original = queue[position][1]
                    if random.choice([True, False]):
                        queue.insert(position, ('word', random.choice(available_glitches)))
                    else:
                        queue[position] = ('stutter', original, random.randint(1, 4))

        return {'queue': queue, 'errors': errors}

    def interpret_broadcast_text(self, text, pitch=None, speed=None, enable_number_reading=None,
                                 include_bell=None, enable_special_bell=None):
        pitch = self.pitch if pitch is None else pitch
        speed = self.speed if speed is None else speed
        include_bell = self.enable_bell if include_bell is None else include_bell
        enable_special_bell = self.enable_special_bell if enable_special_bell is None else enable_special_bell
        parsed = self.parse_broadcast_text(text, enable_number_reading=enable_number_reading)
        errors = list(parsed['errors'])
        events = []
        channel_positions = {channel: 0 for channel in range(8)}
        word_count = 0

        def load_words(words):
            audio = AudioSegment.empty()
            for word in words if isinstance(words, (list, tuple)) else [words]:
                filepath = os.path.join(AUDIO_BASE_PATH, word + AUDIO_EXTENSION)
                if os.path.exists(filepath):
                    audio += self.load_audio(filepath)
            return audio if len(audio) else None

        def piece_durations_ms(words):
            """逐个片段的原始音频长度（未做音高/语速处理）。

            播放日志靠它把"念到第几段"映射到时间轴上的位置。
            """
            spans = []
            for word in words if isinstance(words, (list, tuple)) else [words]:
                filepath = os.path.join(AUDIO_BASE_PATH, word + AUDIO_EXTENSION)
                if os.path.exists(filepath):
                    spans.append(len(self.load_audio(filepath)))
            return spans

        def compile_queue(queue, initial_channel, base_ms=0, active_channels=None):
            nonlocal word_count
            current_channel = initial_channel
            current_pitch = pitch
            active_channels = set() if active_channels is None else set(active_channels)

            for item in queue:
                item_type = item[0]
                if item_type == 'channel':
                    current_channel = initial_channel if item[1] == -1 else item[1]
                    continue
                if item_type == 'speed_all':
                    current_pitch = item[1]
                    continue
                if item_type == 'channl':
                    block_start = max(base_ms, channel_positions[current_channel])
                    block_start = max(0, block_start + round(item[1] * 1000))
                    unavailable = {
                        event['channel'] for event in events
                        if event['start_ms'] < block_start < event['end_ms']
                    }
                    candidates = [
                        channel for channel in range(8)
                        if channel != current_channel and channel not in active_channels
                        and channel not in unavailable
                        and channel_positions[channel] <= block_start
                    ]
                    if not candidates:
                        errors.append(tr('channl_no_free_channel'))
                        continue
                    block_channel = candidates[0]
                    compile_queue(item[2], block_channel, block_start,
                                  active_channels | {current_channel, block_channel})
                    continue
                if item_type in ('pause', 'gap'):
                    channel_positions[current_channel] = max(
                        base_ms, channel_positions[current_channel]) + round(item[1] * 1000)
                    continue
                if item_type not in ('word', 'number', 'stutter'):
                    continue

                word_count += 1
                position = max(base_ms, channel_positions[current_channel])
                if speed > 0 and word_count > 1:
                    position += round(speed * 50)

                word = item[1]
                word_pitch = current_pitch
                if item_type == 'word' and len(item) > 2:
                    word_pitch = item[2]
                elif item_type == 'stutter' and len(item) > 3 and item[3] is not None:
                    word_pitch = item[3]
                audio = load_words(word)
                if audio is None:
                    continue

                audio = self._prepare_audio(audio, pitch=word_pitch, speed=speed,
                                            apply_effects=False)
                if item_type == 'stutter':
                    full_audio = audio
                    short_audio = audio[:int(min(len(audio), self.stutter_duration * 1000))]
                    audio = short_audio * item[2]
                    if len(item) < 5 or item[4]:
                        audio += full_audio

                scheduled_length = len(audio)
                if not self.uses_sentence_processing():
                    audio = self.apply_broadcast_effect(audio)
                    if len(audio) == 0:
                        audio = full_audio if item_type == 'stutter' else load_words(word)

                event = {
                    'start_ms': position,
                    'end_ms': position + scheduled_length,
                    'audio_length_ms': len(audio),
                    'channel': current_channel,
                    'audio': audio,
                    'label': self.spoken_label(item_type, word),
                    'spoken_words': self.spoken_parts(item_type, word),
                    'piece_durations_ms': piece_durations_ms(word),
                }
                events.append(event)
                channel_positions[current_channel] = event['end_ms']

        compile_queue(parsed['queue'], self.word_channel)
        content_end = max((event['end_ms'] for event in events), default=0)
        if include_bell and events:
            lead_ms = max(0, round(self.bell_lead_time * 1000))
            for event in events:
                event['start_ms'] += lead_ms
                event['end_ms'] += lead_ms
            content_end += lead_ms
            if enable_special_bell:
                start_file = self.get_special_bell_path(self.special_bell_start, 'bell_start.wav')
                end_file = self.get_special_bell_path(self.special_bell_end, 'bell_end.wav')
                if os.path.exists(start_file):
                    audio = self.load_audio(start_file)
                    events.append({'start_ms': 0, 'end_ms': len(audio), 'channel': self.bell_channel,
                                   'audio': audio, 'label': self.special_bell_start})
                else:
                    errors.append(tr('bell_missing', item=self.special_bell_start))
                if self.bell_extra_duration > 0:
                    content_end += round(self.bell_extra_duration * 1000)
                if os.path.exists(end_file):
                    audio = self.load_audio(end_file)
                    events.append({'start_ms': content_end, 'end_ms': content_end + len(audio),
                                   'channel': self.bell_channel, 'audio': audio,
                                   'label': self.special_bell_end})
                else:
                    errors.append(tr('bell_missing', item=self.special_bell_end))
            else:
                seconds = max(4, int(content_end / 1000) + 2 + int(self.bell_extra_duration))
                bell_file = os.path.join(SOUND_BASE_PATH, 'bg_{}.wav'.format(seconds))
                if os.path.exists(bell_file):
                    audio = self.load_audio(bell_file)
                    events.append({'start_ms': 0, 'end_ms': len(audio), 'channel': self.bell_channel,
                                   'audio': audio, 'label': 'bg_{}'.format(seconds)})
                else:
                    errors.append(tr('bell_missing', item='bg_{}.wav'.format(seconds)))

        events.sort(key=lambda event: event['start_ms'])
        content_ms = max((event['end_ms'] for event in events), default=0)
        _PENDING_TIMELINE.value = None
        events = self.apply_reverb_to_events(events)
        pending = _PENDING_TIMELINE.value
        if pending is not None:
            content_ms = pending['content_ms']
            duration_ms = pending['duration_ms']
        else:
            duration_ms = max((event['start_ms']
                               + event.get('audio_length_ms', len(event['audio']))
                               for event in events), default=0)
        return {'events': events, 'errors': errors, 'word_count': word_count,
                'content_ms': int(content_ms), 'duration_ms': int(max(content_ms, duration_ms))}

    def uses_sentence_processing(self):
        """当前是否走整句处理模式。"""
        return getattr(self, 'spatial_mode', 'word') == 'sentence'

    def spatial_active(self):
        """空间效果链是否启用（总开关 + 混响 + 湿声，三者同时成立才生效）。"""
        return bool(self.broadcast_effect_enabled
                    and self.reverb_enabled
                    and self.reverb_wet > 0)


    PROGRESS_STAGES = ('parse', 'reverb', 'export', 'play')

    # 阶段在总进度里的区间。没有这层映射的话每换阶段百分比会退回 0。
    # reverb 区间最大（耗时几乎都在那里）；play 由前端按播放时间推进。
    PROGRESS_SPANS = {
        'parse': (0, 8),
        'reverb': (8, 72),
        'export': (72, 80),
        'play': (80, 100),
    }

    def _progress_state(self):
        state = getattr(_PENDING_PROGRESS, 'state', None)
        if state is None:
            state = {'callback': None, 'total': 0, 'done': 0, 'stage': 'parse',
                     'percent': 0}
            _PENDING_PROGRESS.state = state
        return state

    def begin_progress(self, total_units, callback):
        """开始一次带进度的合成。callback(stage, done, total, percent)。"""
        state = self._progress_state()
        state['callback'] = callback
        state['total'] = max(0, int(total_units))
        state['done'] = 0
        state['stage'] = 'parse'
        state['percent'] = 0

    def set_progress_stage(self, stage, total_units=None):
        """切换阶段，并可选地重设该阶段的总量（重置计数）。"""
        state = self._progress_state()
        state['stage'] = stage
        if total_units is not None:
            state['total'] = max(0, int(total_units))
            state['done'] = 0
        self._emit_progress()

    def _tick_progress(self):
        state = self._progress_state()
        state['done'] += 1
        self._emit_progress()

    def _set_progress_position(self, done, total):
        """直接设定阶段内的完成量（用于播放这种按时间推进的阶段）。"""
        state = self._progress_state()
        state['done'] = int(done)
        state['total'] = max(1, int(total))
        self._emit_progress()

    def estimate_preprocess_event(self, text):
        """预估预处理（逐词加空间效果）耗时，给前端先跑动画用。

        逐词加效果是同步跑完的，期间没法往 SSE 里推事件；没有预估时长的话
        界面在预处理阶段会一直停着。每词耗时取自实测（见 per_word_ms），
        真实事件到达后会覆盖它。
        """
        span = self.PROGRESS_SPANS['reverb']
        if not self.spatial_active():
            return {'type': 'progress', 'stage': 'reverb', 'done': 0, 'total': 0,
                    'percent': span[0], 'estimate_ms': 0, 'estimated': True}
        words = len([part for part in str(text or '').split() if part])
        level = max(0, int(getattr(self, 'spatial_quality', 0)))
        per_word_ms = (85, 54, 35, 23, 17, 15, 11)
        unit = per_word_ms[min(level, len(per_word_ms) - 1)]
        return {'type': 'progress', 'stage': 'reverb', 'done': 0, 'total': words,
                'percent': span[0], 'estimate_ms': int(max(120, words * unit)),
                'estimated': True}

    def progress_percent(self, stage, done, total):
        """把阶段内的完成度映射成整条流程的百分比，且只增不减。"""
        start, end = self.PROGRESS_SPANS.get(stage, (0, 100))
        if total > 0:
            ratio = min(1.0, max(0.0, float(done) / float(total)))
        else:
            ratio = 0.0
        percent = int(round(start + (end - start) * ratio))
        previous = self._progress_state().get('percent', 0)
        return max(previous, percent, 0)

    def _emit_progress(self, force_percent=None):
        state = self._progress_state()
        callback = state['callback']
        if callback is None:
            return
        total = state['total']
        done = min(state['done'], total) if total else 0
        if force_percent is None:
            percent = self.progress_percent(state['stage'], done, total)
        else:
            percent = max(state.get('percent', 0), force_percent)
        state['percent'] = percent
        try:
            callback(state['stage'], done, total, percent)
        except Exception:
            traceback.print_exc()

    def end_progress(self):
        state = self._progress_state()
        state['callback'] = None
        state['total'] = 0
        state['done'] = 0
        state['stage'] = 'parse'
        state['percent'] = 0

    def _append_tail_marker(self, events, content_end, tail_end):
        """在尾部补一个空事件，只把收尾时间延到拖尾结束（不产生音频）。"""
        if tail_end <= content_end:
            return events
        events.append({
            'start_ms': content_end,
            'end_ms': tail_end,
            'channel': self.bell_channel,
            'audio': AudioSegment.empty(),
            'label': '__tail__',
            'silent': True,
        })
        return events

    @staticmethod
    def timeline_bounds(events):
        """返回 (正文结束, 含拖尾结束)。

        不能简单取 end_ms 的最大值：整句模式下那条音频本身就带着拖尾，
        它的 end_ms 等于整轨长度，会把「正文结束」也算成拖尾结束。
        时间槽（end_ms 由未加效果的时长决定）才是正文边界。
        """
        real = [event for event in events if not event.get('silent')]
        content_end = max((event['end_ms'] for event in real), default=0)
        tail_end = max((event['start_ms'] + event.get('audio_length_ms', len(event['audio']))
                        for event in real), default=0)
        return content_end, max(content_end, tail_end)

    def apply_reverb_to_events(self, events):
        """按处理模式对广播套用走廊混响。

        逐词模式：对每个正文事件单独加混响。每个词都有自己的拖尾，
        拖尾自然叠到下一个词上；开销随词数线性增长（每词都要跑满一条拖尾）。

        整句模式：先把时间线按声道拼成干声，再对每个声道**整体**做一次后处理。
        同样长度的拖尾只算一次，因此耗时基本与词数无关；代价是逐词的
        音高/效果差异会被统一，且不同声道各自独立加混响。

        单词的 start_ms / end_ms 与模式无关，两种模式的时间线完全一致。
        """
        if not self.spatial_active() or not events:
            return events

        if self.uses_sentence_processing():
            return self._apply_sentence_processing(events)

        speakable = [event for event in events
                     if event['channel'] != self.bell_channel and len(event['audio']) > 0]
        if speakable:
            self.set_progress_stage('reverb', len(speakable))

        for event in events:
            # 铃声走独立声道，不加混响，避免和正文叠在一起变浑
            if event['channel'] == self.bell_channel:
                continue
            processed = self.apply_room_reverb(event['audio'])
            if len(processed) > 0:
                event['audio'] = processed
                event['audio_length_ms'] = len(processed)
            self._tick_progress()

        content_end, tail_end = self.timeline_bounds(events)
        return self._append_tail_marker(events, content_end, tail_end)

    def _mix_channel(self, events, channel, frame_rate, total_ms):
        """把某个声道的所有事件叠加成一条干声轨。"""
        track = AudioSegment.silent(duration=total_ms, frame_rate=frame_rate).set_sample_width(2)
        for event in events:
            if event['channel'] != channel or len(event['audio']) == 0:
                continue
            audio = event['audio'].set_frame_rate(frame_rate)
            track = track.overlay(audio, position=int(event['start_ms']))
        return track

    def _apply_sentence_processing(self, events):
        """整句模式：按声道拼干声 → 整轨做一次效果链与混响 → 替换事件列表。

        整句模式把逐词的效果链也一起搬到这里，好处是：
          * 混响只跑一遍（省掉「每词一条拖尾」的重复计算）
          * 高音尾音、底噪、压缩也只在整段上做一次，比逐词叠加更自然
        返回的事件列表只保留实际发声的声道（一般是 1~2 条），
        因此播放与导出都只需要盯着一条长音频。
        """
        frame_rate = int(self._audio_frame_rate(events))
        content_end = max((event['end_ms'] for event in events), default=0)
        if content_end <= 0:
            return events

        speech_channels = sorted({event['channel'] for event in events
                                  if event['channel'] != self.bell_channel})
        bell_events = [event for event in events if event['channel'] == self.bell_channel]

        content_end, _ = self.timeline_bounds(events)

        processed = []
        tail_end = content_end
        for channel in speech_channels:
            track = self._mix_channel(events, channel, frame_rate, content_end)
            if len(track) == 0:
                continue
            track = self.apply_broadcast_effect(track)
            track = self.apply_room_reverb(track)
            if len(track) == 0:
                continue
            processed.append({
                'start_ms': 0,
                'end_ms': len(track),
                'audio_length_ms': len(track),
                'channel': channel,
                'audio': track,
                # 取 spoken_words 而非 label：日志要逐片段显示，
                # 不能出现"整句"这种用户没听到过的字样。
                'words': [piece
                          for event in events
                          if event['channel'] == channel
                          and not event.get('silent')
                          for piece in (event.get('spoken_words')
                                        or [event.get('label', '')])
                          if str(piece).strip()],
                'label': tr('sentence_label'),
            })
            tail_end = max(tail_end, len(track))

        if not processed:
            return events

        result = processed + bell_events
        result.sort(key=lambda event: event['start_ms'])
        _PENDING_TIMELINE.value = {
            'content_ms': int(content_end),
            'duration_ms': int(max(content_end, tail_end)),
        }
        return result

    @staticmethod
    def _audio_frame_rate(events):
        for event in events:
            if len(event['audio']) > 0:
                return event['audio'].frame_rate
        return 44100

    def parse_segment(self, segments, current_index):
        if not segments or current_index >= len(segments):
            return []
        segment = segments[current_index]
        if not segment:
            return []

        if segment.startswith('[channel:'):
            if segment == '[channel:stop]':
                return [('channel', -1)]
            try:
                channel_num = int(segment[9:-1])
                if 1 <= channel_num <= 8:
                    return [('channel', channel_num - 1)]
            except:
                pass
            return []

        if segment.startswith('[speed_all:'):
            try:
                speed_all_value = float(segment[11:-1])
                if 0.1 <= speed_all_value <= 10.0:
                    return [('speed_all', speed_all_value)]
            except:
                pass
            return []

        if segment.startswith('[gap:'):
            try:
                gap_value = float(segment[5:-1])
                if gap_value >= 0:
                    return [('gap', gap_value)]
            except:
                pass
            return []

        if segment.startswith('[error:'):
            try:
                error_count = int(segment[7:-1])
                return [('error', error_count)]
            except:
                pass
            return []


        stutter_match = re.match(r'^\[stutter:(\d+)(?:,(\w+))?\](.+)$', segment)
        if stutter_match:
            stutter_count = int(stutter_match.group(1))
            full_play_str = stutter_match.group(2)
            full_play = True if full_play_str is None else full_play_str.lower() == 'true'
            actual_word = stutter_match.group(3)
            temp_segments = segments[:current_index] + [actual_word] + segments[current_index+1:]
            word_queue = self.parse_segment(temp_segments, current_index)
            if word_queue:
                if len(word_queue[0]) > 2:
                    pitch = word_queue[0][2]
                else:
                    pitch = None
                return [('stutter', word_queue[0][1], stutter_count, pitch, full_play)]
            return []

        speed_match = re.match(r'^\[speed:(\d+\.?\d*)\](.+)$', segment)
        if speed_match:
            speed_value = float(speed_match.group(1))
            actual_word = speed_match.group(2)
            if 0.1 <= speed_value <= 10.0:
                temp_segments = segments[:current_index] + [actual_word] + segments[current_index+1:]
                word_queue = self.parse_segment(temp_segments, current_index)
                if word_queue:
                    return [('word', word_queue[0][1], speed_value)]
            return []

        if segment == '.':
            return [('pause', 1.0)]
        if segment == ',':
            return [('pause', 0.7)]
        if segment == '、':
            return [('pause', 0.6)]

        if segment == 'mtf':
            return [('word', 'mobile'), ('word', 'task'), ('word', 'force')]

        if '+' in segment:
            unified = segment.replace('+', ' ')
            filepath = os.path.join(AUDIO_BASE_PATH, unified + AUDIO_EXTENSION)
            if os.path.exists(filepath):
                return [('word', unified)]

        if self.enable_number_reading and segment.replace('.', '', 1).isdigit():
            num_parts = self.process_number(segment)
            if num_parts:
                return [('number', num_parts)]

        if not self.enable_number_reading:
            if segment.isdigit():
                return [('word', d) for d in segment]

        word = segment.lower()

        if word == 'the':
            if current_index + 1 < len(segments):
                next_word = segments[current_index + 1]
                if next_word and next_word[0] in 'aeiou':
                    return [('word', 'the_vowel')]
            return [('word', 'the_consonant')]

        if word in nato_map:
            word = nato_map[word]
        elif len(word) == 1 and word.isalpha():
            word = '_' + word

        if word.endswith('ed'):
            base = word[:-2]
            base_path = os.path.join(AUDIO_BASE_PATH, base + AUDIO_EXTENSION)
            ed_path = os.path.join(AUDIO_BASE_PATH, 'ed' + AUDIO_EXTENSION)
            if os.path.exists(base_path) and os.path.exists(ed_path):
                return [('word', base), ('word', 'ed')]

        filepath = os.path.join(AUDIO_BASE_PATH, word + AUDIO_EXTENSION)
        if os.path.exists(filepath):
            return [('word', word)]

        return []

    def check_spelling(self, text):
        segments = text.strip().split()
        not_found = []
        for seg in segments:
            word = seg.lower()
            if word.startswith('[speed_all:'):
                continue
            if word.startswith('[speed:'):
                continue
            if ']' in word and '[' in word:
                parts = word.split(']')
                word = parts[-1] if parts else word
            if '+' in word:
                word = word.replace('+', ' ')
            if word.isdigit():
                continue
            if word in ['.', ',', '、']:
                continue
            if word == 'mtf':
                continue
            if word in self.word_set:
                continue
            if word in nato_map:
                continue
            if len(word) == 1 and word.isalpha():
                if '_' + word in self.word_set:
                    continue
            if word.startswith('g') and len(word) == 2 and word[1].isdigit():
                if word in self.word_set:
                    continue
            not_found.append(seg)
        return not_found

    def _legacy_play_broadcast_stream(self, text):
        if self.is_playing:
            yield {"text": tr('play_busy'), "type": "error"}
            return
        if not text:
            yield {"text": tr('content_empty'), "type": "error"}
            return

        error_value = None

        while True:
            cmd_match = re.search(r'\[cd:([^\]]+)\]', text)
            if not cmd_match:
                break
            parts = cmd_match.group(1).split(',')
            if len(parts) < 2:
                yield {"text": "Error: CD command missing parameters, expected format: [cd:start,end,separator]", "type": "error"}
                text = text.replace(cmd_match.group(0), '')
                continue
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            sep = parts[2] if len(parts) > 2 else ' . '
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                yield {"text": "Error: CD command invalid number format", "type": "error"}
                text = text.replace(cmd_match.group(0), '')
                continue
            if start == end:
                yield {"text": "Error: CD command start value equals end value", "type": "error"}
                text = text.replace(cmd_match.group(0), '')
                continue
            if start > end:
                nums = list(range(start, end - 1, -1))
            else:
                nums = list(range(start, end + 1))
            result = str(nums[0])
            for n in nums[1:]:
                result += sep + str(n)
            text = text.replace(cmd_match.group(0), result)

        while True:
            cmd_match = re.search(r'\[mtf:([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)\]', text)
            if cmd_match:
                parts = [p.strip() for p in cmd_match.groups()]
                if len(parts) < 5:
                    yield {"text": "Error: MTF command missing parameters: [mtf:word1,number1,word2,number2,scp_count]", "type": "error"}
                    text = text.replace(cmd_match.group(0), '')
                else:
                    word1 = parts[0]
                    number1_str = parts[1]
                    word2 = parts[2]
                    number2_str = parts[3]
                    scp_count_str = parts[4]
                    if not word1 or not word2:
                        yield {"text": "Error: MTF command word cannot be empty", "type": "error"}
                        text = text.replace(cmd_match.group(0), '')
                    elif not number1_str.isdigit() or not number2_str.isdigit() or not scp_count_str.isdigit():
                        yield {"text": "Error: MTF command number must be a positive integer", "type": "error"}
                        text = text.replace(cmd_match.group(0), '')
                    else:
                        number1 = int(number1_str)
                        number2 = int(number2_str)
                        scp_count = int(scp_count_str)
                        if number1 < 1 or number2 < 1 or scp_count < 1:
                            yield {"text": "Error: MTF command number must be a positive integer", "type": "error"}
                            text = text.replace(cmd_match.group(0), '')
                        else:
                            subject = 'scp+subject' if scp_count == 1 else 'scp+subjects'
                            result = f"mobile+task+force+unit {word1} {number1} designated {word2} {number2} has+entered+the+facility . all+remaining+personnel . awating+recontainment . {scp_count} {subject} . "
                            text = text.replace(cmd_match.group(0), result)
            else:
                break

        while True:
            cmd_match = re.search(r'\[backup:([^,]+)\]', text)
            if cmd_match:
                parts = [p.strip() for p in cmd_match.groups()]
                if len(parts) < 1:
                    yield {"text": "Error: BackUp command missing parameters: [backup:word]", "type": "error"}
                    text = text.replace(cmd_match.group(0), '')
                else:
                    backup_word = parts[0]
                    result = f"{backup_word} backup unit has+entered+the+facility . "
                    text = text.replace(cmd_match.group(0), result)
            else:
                break

        while True:
            cmd_match = re.search(r'\[warhead:([^,]+),([^,]+)\]', text)
            if cmd_match:
                parts = [p.strip() for p in cmd_match.groups()]
                if len(parts) < 2:
                    yield {"text": "Error: Warhead command missing parameters: [Warhead:number,type(start/cancel/erstart)]", "type": "error"}
                    text = text.replace(cmd_match.group(0), '')
                else:
                    warhead_number = parts[0]
                    warhead_type = parts[1]
                    if warhead_type == "cancelled":
                        result = f"warhead+cancelled"
                    elif warhead_type =="resume":
                        result = f"warhead+{warhead_type} {warhead_number}s"
                    elif warhead_type =="start":
                        result = f"warhead+{warhead_type} {warhead_number}s"
                    else:
                        yield {"text": "Error: Warhead command missing parameters: [Warhead:number,type(start/cancel/erstart)]", "type": "error"}
                        result = f"[speed:0.85]error"
                    text = text.replace(cmd_match.group(0), result)
            else:
                break

        while True:
            cmd_match = re.search(r'\[hostile_enter:([^,]+),([^,]+),([^,]+),([^,]+)\]', text)
            if cmd_match:
                parts = [p.strip() for p in cmd_match.groups()]
                if len(parts) < 4:
                    yield {"text": "Error: HostileEnter command missing parameters: [hostile_enter:number1,word1,word2,word3]", "type": "error"}
                    text = text.replace(cmd_match.group(0), '')
                else:
                    number1_str = parts[0]
                    word1 = parts[1]
                    word2 = parts[2]
                    word3 = parts[3]
                    if not word3:
                        word3 = "lethal force authorized"
                    if not word1 or not word2:
                        yield {"text": "Error: HostileEnter command word cannot be empty", "type": "error"}
                        text = text.replace(cmd_match.group(0), '')
                    elif not number1_str.isdigit():
                        yield {"text": "Error: HostileEnter command number must be a positive integer", "type": "error"}
                        text = text.replace(cmd_match.group(0), '')
                    else:
                        number1 = int(number1_str)
                        if number1 < 1:
                            yield {"text": "Error: HostileEnter command number must be a positive integer", "type": "error"}
                            text = text.replace(cmd_match.group(0), '')
                        else:
                            result = f"attention , all personnel . detected {number1} {word1} at {word2} . {word3} . "
                            text = text.replace(cmd_match.group(0), result)
            else:
                break

        error_match = re.search(r'\[error:(\d+)\]', text)
        if error_match:
            error_value = int(error_match.group(1))
            text = re.sub(r'\[error:\d+\]', '', text)

        text = re.sub(r'\s+', ' ', text).strip()
        segments = text.lower().split()

        self.is_playing = True

        try:
            full_queue = []

            i = 0
            while i < len(segments):
                parsed = self.parse_segment(segments, i)
                if parsed:
                    full_queue.extend(parsed)
                    i += 1
                else:
                    yield {"text": tr('not_found', item=segments[i]), "type": "error"}
                    i += 1

            if error_value and error_value > 0:
                word_indices = [i for i, item in enumerate(full_queue) if item[0] == 'word']
                if word_indices:
                    select_count = min(error_value, len(word_indices))
                    chosen = random.sample(word_indices, select_count)
                    for pos in sorted(chosen, reverse=True):
                        orig = full_queue[pos][1]
                        if random.choice([0, 1]) == 0:
                            full_queue.insert(pos, ('word', f'g{random.randint(1,9)}'))
                        else:
                            full_queue[pos] = ('stutter', orig, random.randint(1,4))

            if self.enable_bell:
                if self.enable_special_bell:
                    start_file = os.path.join(SOUND_BASE_PATH, "bell_start.wav")
                    if os.path.exists(start_file):
                        self.play_bell_audio(start_file)
                        if self.verbose_mode:
                            yield {"text": tr('bell_playing', item='bell_start'), "type": "info"}
                    else:
                        yield {"text": tr('bell_missing', item='bell_start.wav'), "type": "error"}
                else:
                    total_duration = 0
                    for item in full_queue:
                        if item[0] == 'pause':
                            total_duration += item[1]
                        elif item[0] == 'stutter':
                            filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                            total_duration += self.get_audio_duration(filepath) * (item[2] + 1)
                        elif item[0] == 'word':
                            filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                            total_duration += self.get_audio_duration(filepath)
                        elif item[0] == 'number':
                            total_duration += sum(
                                self.get_audio_duration(os.path.join(AUDIO_BASE_PATH, word + AUDIO_EXTENSION))
                                for word in item[1]
                            )
                    need_seconds = int(total_duration) + 2 + int(self.bell_extra_duration)
                    if need_seconds < 4:
                        need_seconds = 4
                    bell_file = os.path.join(SOUND_BASE_PATH, "bg_" + str(need_seconds) + ".wav")
                    if os.path.exists(bell_file):
                        self.play_bell_audio(bell_file)
                        if self.verbose_mode:
                            yield {"text": tr('bell_playing', item='bg_' + str(need_seconds)), "type": "info"}
                    else:
                        yield {"text": tr('bell_missing', item='bg_' + str(need_seconds) + '.wav'), "type": "error"}
                time.sleep(self.bell_lead_time)

            current_speed_all = self.pitch
            current_channel = self.word_channel
            total_words = len([item for item in full_queue if item[0] in ('word', 'number', 'stutter')])
            word_index = 0
            
            for item in full_queue:
                if self.stop_requested:
                    break
                if item[0] == 'channel':
                    if item[1] == -1:
                        current_channel = self.word_channel
                    else:
                        current_channel = item[1]
                    continue
                if item[0] == 'speed_all':
                    current_speed_all = item[1]
                    continue
                if item[0] == 'pause':
                    if self.verbose_mode:
                        yield {"text": tr('verbose_pause', seconds=item[1]), "type": "info"}
                    time.sleep(item[1])
                elif item[0] == 'gap':
                    time.sleep(item[1])
                elif item[0] == 'stutter':
                    word_index += 1
                    filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                    stutter_count = item[2]
                    pitch = item[3] if len(item) > 3 and item[3] is not None else current_speed_all
                    full_play = item[4] if len(item) > 4 else True
                    if self.verbose_mode:
                        suffix = tr('verbose_stutter_full') if full_play else tr('verbose_stutter_only')
                        yield {"text": tr('verbose_stutter', index=word_index,
                                          total=total_words, word=item[1],
                                          count=stutter_count, pitch=pitch,
                                          suffix=suffix), "type": "info"}
                    self.play_stutter(filepath, stutter_count, pitch, speed=self.speed, channel=current_channel, full_play=full_play)
                elif item[0] == 'word':
                    word_index += 1
                    filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                    pitch = item[2] if len(item) > 2 else current_speed_all
                    if self.verbose_mode:
                        yield {"text": tr('verbose_word', index=word_index,
                                          total=total_words, word=item[1],
                                          pitch=pitch), "type": "info"}
                    self.play_audio_on_channel(current_channel, filepath, pitch=pitch, speed=self.speed)
                elif item[0] == 'number':
                    word_index += 1
                    pitch = current_speed_all
                    if self.verbose_mode:
                        yield {"text": tr('verbose_number', index=word_index,
                                          total=total_words,
                                          word=' '.join(item[1])), "type": "info"}
                    self.play_number_on_channel(current_channel, item[1], pitch=pitch, speed=self.speed)

            if self.enable_bell and self.enable_special_bell:
                end_file = os.path.join(SOUND_BASE_PATH, "bell_end.wav")
                if os.path.exists(end_file):
                    self.play_bell_audio(end_file)
                    if self.verbose_mode:
                        yield {"text": tr('bell_playing', item='bell_end'), "type": "info"}
                    time.sleep(self.get_audio_duration(end_file))

            if self.verbose_mode:
                yield {"text": tr('play_done'), "type": "info"}

        finally:
            self.is_playing = False
            self.stop_requested = False


    def play_broadcast_stream(self, text, lock_acquired=False):
        owns_lock = lock_acquired
        if not owns_lock and not self.play_lock.acquire(False):
            yield {"text": tr('play_busy'), "type": "error"}
            return
        owns_lock = True

        try:
            plan = self.interpret_broadcast_text(text)
            for error in plan['errors']:
                yield {"text": error, "type": "error"}
            events = plan['events']
            if not events:
                return

            self.is_playing = True
            playable = [event for event in events if len(event['audio']) > 0]

            # 只按行拆分，不重算读法：label / spoken_words 在生成事件时已算好。
            def log_pieces(event):
                if event.get('words'):
                    pieces = event['words']
                elif event.get('spoken_words'):
                    pieces = event['spoken_words']
                else:
                    pieces = [event.get('label', '')]
                return [str(piece) for piece in pieces if str(piece).strip()]

            # 按各片段的真实音频长度定位日志时刻，不能用时间槽等分：
            # 时间槽含混响拖尾，等分会让后面的片段和实际听到的时刻对不上。
            schedule = []
            if self.verbose_mode:
                timeline = []      # [(相对起点毫秒, 文本), ...] 已按时间排序
                for event in playable:
                    if event['channel'] == self.bell_channel:
                        continue
                    pieces = log_pieces(event)
                    if not pieces:
                        continue
                    start_ms = int(event['start_ms'])
                    offsets = self.spoken_offsets(event, pieces)
                    for position, piece in enumerate(pieces):
                        timeline.append((start_ms + offsets[position], piece))

                total_words = len(timeline)
                schedule = [
                    (at_ms, '[{}/{}] {}'.format(index, total_words, piece))
                    for index, (at_ms, piece) in enumerate(timeline, 1)
                ]

            playback_start = time.monotonic()
            channel_ready = {}
            cursor = 0

            def due_logs(before_ms):
                """吐出所有应当在 before_ms 之前出现的日志，并按真实时钟等待。"""
                nonlocal cursor
                while cursor < len(schedule) and schedule[cursor][0] <= before_ms:
                    at_ms, text = schedule[cursor]
                    wait = playback_start + at_ms / 1000.0 - time.monotonic()
                    if wait > 0:
                        time.sleep(wait)
                    cursor += 1
                    yield {"text": text, "type": "info"}

            total_play_ms = 0
            for event in playable:
                if event['channel'] == self.bell_channel:
                    continue
                total_play_ms = max(total_play_ms,
                                    int(event['start_ms'])
                                    + int(event.get('audio_length_ms', len(event['audio']))))
            self.set_progress_stage('play')
            span = self.PROGRESS_SPANS['play']
            yield {"type": "progress", "stage": 'play', "done": 0,
                   "total": max(1, total_play_ms // 1000),
                   "percent": span[0],
                   "duration_ms": total_play_ms,
                   "started_at": int(playback_start * 1000),
                   "is_playback": True}

            for event in playable:
                if self.stop_requested:
                    break
                event_start_ms = int(event['start_ms'])
                for entry in due_logs(event_start_ms):
                    yield entry

                delay = playback_start + event['start_ms'] / 1000.0 - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                duration = self._play_audio_segment(event['channel'], event['audio'], wait=False)
                channel_ready[event['channel']] = time.monotonic() + duration
                # 进度按"讲述时间"推进而非事件条数：事件长短不一，
                # 按条数算会让进度和听到的位置对不上
                played_ms = int(event_start_ms + duration)
                self._set_progress_position(played_ms, max(1, total_play_ms))
                self._emit_progress()
                yield {"type": "progress", "stage": 'play',
                       "done": played_ms // 1000,
                       "total": max(1, total_play_ms // 1000),
                       "percent": self.progress_percent(
                           'play', played_ms, max(1, total_play_ms)),
                       "duration_ms": total_play_ms,
                       "elapsed_ms": played_ms}

            # 事件循环结束后补完剩余日志（最后一条事件之后的部分）。
            # 被停止时不再等——否则用户按了停止还要陪着把剩余时间睡完。
            if not self.stop_requested:
                for entry in due_logs(float('inf')):
                    yield entry

            remaining = max(channel_ready.values(), default=time.monotonic()) - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            self.wait_for_channels(range(pygame.mixer.get_num_channels()))
            if self.verbose_mode:
                yield {"text": tr('play_done'), "type": "info"}
        except Exception as error:
            traceback.print_exc()
            yield {"text": tr('play_error', error=error), "type": "error"}
        finally:
            self.stop_all_audio()
            self.is_playing = False
            self.stop_requested = False
            if owns_lock:
                self.play_lock.release()

    def export_from_queue(self, text, output_path, include_bell=False, device=None,
                          pitch=1.0, speed=-10, enable_number_reading=False,
                          enable_special_bell=False):
        if not self.play_lock.acquire(False):
            return False, tr('play_busy')
        try:
            return self._export_from_queue_unlocked(
                text, output_path, include_bell, device, pitch, speed,
                enable_number_reading, enable_special_bell)
        finally:
            self.play_lock.release()

    def _export_from_queue_unlocked(self, text, output_path, include_bell=False, device=None,
                                    pitch=1.0, speed=-10, enable_number_reading=False,
                                    enable_special_bell=False):
        """合成到文件。

        进度按三个阶段上报：parse（解析+排期）、reverb（逐词加空间效果，
        最慢的一步）、export（混音写盘）。逐词加效果那一步是唯一能按单位
        推进的，所以 begin_progress 的总量就是可加效果的事件数。
        """
        if not text:
            return False, tr('nothing_to_export')
        self.set_progress_stage('parse')
        plan = self.interpret_broadcast_text(
            text, pitch=pitch, speed=speed,
            enable_number_reading=enable_number_reading,
            include_bell=include_bell, enable_special_bell=enable_special_bell)
        if not plan['events']:
            return False, '; '.join(plan['errors']) or tr('no_export_audio')

        # 收尾哨兵是空的，只用来延长总时长，不能拿它取采样参数
        audio_events = [event for event in plan['events'] if len(event['audio']) > 0]
        if not audio_events:
            return False, '; '.join(plan['errors']) or tr('no_export_audio')

        self.set_progress_stage('export')
        duration = max(event['end_ms'] for event in plan['events'])
        longest = max(event['start_ms'] + len(event['audio']) for event in audio_events)
        duration = max(duration, longest)
        first_audio = audio_events[0]['audio']
        output_audio = AudioSegment.silent(
            duration=duration, frame_rate=first_audio.frame_rate
        ).set_channels(first_audio.channels).set_sample_width(first_audio.sample_width)
        for event in audio_events:
            audio = event['audio'].set_frame_rate(output_audio.frame_rate)
            audio = audio.set_channels(output_audio.channels).set_sample_width(output_audio.sample_width)
            output_audio = output_audio.overlay(audio, position=event['start_ms'])
        output_audio += AudioSegment.silent(duration=1000, frame_rate=output_audio.frame_rate)

        try:
            self.export_audio(output_audio, output_path, fmt='wav')
        except Exception as error:
            return False, tr('wav_write_failed', error=error)
        self._emit_progress(force_percent=100)
        return True, output_path
    
    def process_audio_with_pitch(self, filepath, pitch):
        if pitch == 1.0:
            return filepath

        audio = self.load_audio(filepath)
        new_frame_rate = int(audio.frame_rate * pitch)
        audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
        audio = audio.set_frame_rate(audio.frame_rate)
        export_path = os.path.join(tempfile.gettempdir(), 'temp_stutter.wav')
        self.export_audio(audio, export_path)
        return export_path


    def snapshot_settings(self):
        """读取当前所有可调参数，作为一次调用的默认值。"""
        snapshot = {}
        for field in API_MUTABLE_FIELDS:
            snapshot[field] = getattr(self, field, SYNTHESIS_PARAM_DEFAULTS.get(field))
        return snapshot

    def merged_settings(self, overrides=None):
        """把请求里的覆盖项合并到当前参数之上。"""
        snapshot = self.snapshot_settings()
        for key, value in (overrides or {}).items():
            if key in API_MUTABLE_FIELDS and value is not None:
                snapshot[key] = value
        return snapshot

    @contextlib.contextmanager
    def settings_snapshot(self, overrides=None):
        """在给定参数下临时运行一段逻辑，退出时保证还原。"""
        settings = self.merged_settings(overrides)
        with self.settings_lock:
            backup = self.snapshot_settings()
            try:
                for key, value in settings.items():
                    setattr(self, key, value)
                yield settings
            finally:
                for key, value in backup.items():
                    setattr(self, key, value)

    def list_words(self):
        """返回素材库里所有可用单词（含北约音标、字母与数字音）。"""
        return sorted(self.word_set)

    def list_sounds(self):
        """返回 sounds 与 words 目录里的可用铃声文件名。"""
        names = set()
        for base in (SOUND_BASE_PATH, AUDIO_BASE_PATH):
            if not os.path.isdir(base):
                continue
            for name in os.listdir(base):
                if name.lower().endswith(AUDIO_EXTENSION):
                    names.add(name)
        return sorted(names)

    def library_status(self):
        """素材库概况：文件数、缺失项与配置好的铃声文件是否存在。"""
        words_dir = [f for f in os.listdir(AUDIO_BASE_PATH)
                     if f.lower().endswith(AUDIO_EXTENSION)] if os.path.isdir(AUDIO_BASE_PATH) else []
        sounds_dir = [f for f in os.listdir(SOUND_BASE_PATH)
                      if f.lower().endswith(AUDIO_EXTENSION)] if os.path.isdir(SOUND_BASE_PATH) else []
        return {
            'words_dir': AUDIO_BASE_PATH,
            'sounds_dir': SOUND_BASE_PATH,
            'word_files': len(words_dir),
            'sound_files': len(sounds_dir),
            'known_words': len(self.word_set),
            'special_bell_start_exists': os.path.exists(
                self.get_special_bell_path(self.special_bell_start, 'bell_start.wav')),
            'special_bell_end_exists': os.path.exists(
                self.get_special_bell_path(self.special_bell_end, 'bell_end.wav')),
            'ffmpeg_available': shutil.which('ffmpeg') is not None,
        }

    def validate_text(self, text):
        """拼写检查：返回文本里没有对应音频的单词。"""
        not_found = self.check_spelling(text or '')
        return {'text': text or '', 'not_found': not_found, 'ok': not not_found}

    def plan_broadcast(self, text, overrides=None):
        """只解析不合成，返回时间线摘要，便于调用方先校验再渲染。"""
        with self.settings_snapshot(overrides) as settings:
            started = time.monotonic()
            plan = self.interpret_broadcast_text(
                text,
                pitch=settings['pitch'],
                speed=settings['speed'],
                enable_number_reading=settings['enable_number_reading'],
                include_bell=settings['include_bell'],
                enable_special_bell=settings['enable_special_bell'],
            )
            elapsed = time.monotonic() - started
        all_events = plan['events']
        events = [event for event in all_events if not event.get('silent')]
        # 正文边界由解释器给出：整句模式下事件音频自带拖尾，
        # 从事件上反推会把拖尾算进正文
        content_end = int(plan.get('content_ms', 0))
        tail_end = int(plan.get('duration_ms', 0))
        return {
            'text': text,
            'errors': plan['errors'],
            'word_count': plan.get('word_count', 0),
            'event_count': len(events),
            'duration_ms': tail_end,
            'content_ms': content_end,
            'tail_ms': max(0, tail_end - content_end),
            'channels_used': sorted({event['channel'] for event in events}),
            'events': [{
                'index': index,
                'channel': event['channel'],
                'label': event.get('label', ''),
                'start_ms': int(event['start_ms']),
                'end_ms': int(event['end_ms']),
                'duration_ms': int(event.get('audio_length_ms', len(event['audio']))),
                'slot_ms': int(event['end_ms'] - event['start_ms']),
            } for index, event in enumerate(events)],
            'settings': settings,
            'elapsed_ms': int(elapsed * 1000),
        }

    def synthesize(self, text, output_path=None, overrides=None, filename=None):
        """合成广播为 WAV 文件，返回 (成功, 结果或错误, 元数据)。"""
        if not text or not text.strip():
            return False, tr('content_empty'), {}

        with self.settings_snapshot(overrides) as settings:
            started = time.monotonic()
            if output_path is None:
                handle = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                output_path = handle.name
                handle.close()

            if not self.play_lock.acquire(False):
                return False, tr('play_busy'), {}

            try:
                ok, result = self._export_from_queue_unlocked(
                    text,
                    output_path,
                    include_bell=settings['include_bell'],
                    pitch=settings['pitch'],
                    speed=settings['speed'],
                    enable_number_reading=settings['enable_number_reading'],
                    enable_special_bell=settings['enable_special_bell'],
                )
            finally:
                self.play_lock.release()

            if not ok:
                if os.path.exists(output_path):
                    os.unlink(output_path)
                return False, result, {}

            return True, output_path, {
                'text': text,
                'filename': filename or os.path.basename(output_path),
                'size_bytes': os.path.getsize(output_path),
                'elapsed_ms': int((time.monotonic() - started) * 1000),
                'settings': settings,
            }

    def start_playback(self, text, overrides=None):
        """异步播放广播，返回 (是否启动, 错误信息)。"""
        if not text or not text.strip():
            return False, tr('content_empty')
        if self.is_playing:
            return False, tr('play_busy')

        settings = self.merged_settings(overrides)

        def run():
            try:
                with self.settings_snapshot(settings):
                    for _ in self.play_broadcast_stream(text):
                        pass
            except Exception:
                traceback.print_exc()

        thread = threading.Thread(target=run, daemon=True, name='cassie-api-playback')
        thread.start()
        return True, ''

    def stop_playback(self):
        """请求停止播放并立刻静音所有声道。"""
        self.stop_requested = True
        self.stop_all_audio()
        return True

    def health(self):
        """运行状况自检。"""
        status = self.library_status()
        return {
            'api_version': API_VERSION,
            'project_version': PROJECT_VERSION,
            'status': 'ok',
            # 当前请求生效的语言，前端可据此确认语言协商的结果
            'language': current_language(),
            'pid': os.getpid(),
            'started_at': getattr(self, 'started_at', None),
            'features': self.feature_flags(),
            'spatial_quality_levels': len(self.SPATIAL_QUALITY_LEVELS),
            'python': '{}.{}.{}'.format(*sys.version_info[:3]),
            'platform': sys.platform,
            'playing': bool(self.is_playing),
            'stop_requested': bool(self.stop_requested),
            'play_lock_held': bool(self.play_lock.locked()),
            'preset_count': len(getattr(self, 'presets', {}) or {}),
            'audio_device_count': pygame.mixer.get_num_channels(),
            'mixer_initialized': bool(pygame.mixer.get_init()),
            'library': status,
        }

    def feature_flags(self):
        """当前进程实际支持的功能指纹。

        用反射判断，避免手工维护：某个功能对应的方法存在就说明这份代码有它。
        排查"改了没生效"时对照这里最快。
        """
        checks = {
            'spoken_label': 'spoken_label',
            'spoken_parts': 'spoken_parts',
            'number_words': 'NUMBER_WORDS',
            'spatial_quality_tiers': 'SPATIAL_QUALITY_LEVELS',
            'sentence_mode': 'uses_sentence_processing',
            'mono_reverb': 'spatial_profile',
            'settings_persistence': 'save_settings',
            'load_audio': 'load_audio',
            'serve_local_file_no_cache': 'serve_local_file',
        }
        flags = {}
        for name, attribute in checks.items():
            owner = type(self)
            flags[name] = hasattr(self, attribute) or hasattr(owner, attribute) \
                or hasattr(sys.modules[__name__], attribute)
        return flags

    def api_documentation(self):
        """返回接口清单，供客户端自动发现。"""
        return {
            'api_version': API_VERSION,
            'prefix': API_PREFIX,
            'description': tr('api_description'),
            'endpoints': sorted(
                ['{} {}'.format(method, rule) for rule in _API_ROUTES for method in _API_ROUTES[rule]]
            ),
            'parameter_defaults': SYNTHESIS_PARAM_DEFAULTS,
            'mutable_fields': list(API_MUTABLE_FIELDS),
        }


_API_ROUTES = {}


def api_route(rule, method='GET'):
    """注册 API 路由并记录清单，便于 /api/v1 自描述。"""
    def decorator(func):
        _API_ROUTES.setdefault(rule, []).append(method.upper())
        return route(API_PREFIX + rule, method=method)(func)
    return decorator


def api_success(data=None, status=200, **extra):
    response.status = status
    payload = {'ok': True, 'api_version': API_VERSION}
    if data is not None:
        payload['data'] = data
    payload.update(extra)
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps(payload, ensure_ascii=False)


def api_error(message, code='bad_request', status=400, **extra):
    response.status = status
    response.content_type = 'application/json; charset=UTF-8'
    error = {'code': code, 'message': str(message)}
    payload = {'ok': False, 'api_version': API_VERSION, 'error': error}
    for key in ('unknown_fields',):
        if key in extra:
            error[key] = extra.pop(key)
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def api_payload():
    """读取并校验请求体，支持 JSON 与 form 两种方式。"""
    raw = request.body.read()
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def api_guard():
    """可选的 API Key 校验。设置了 CASSIE_API_KEY 环境变量才启用。"""
    expected = os.environ.get('CASSIE_API_KEY')
    if not expected:
        return None
    provided = request.headers.get('X-API-Key') or request.query.get('api_key') or ''
    if provided == expected:
        return None
    return api_error(tr('api_key_invalid'), code='unauthorized', status=401)


cassie = CASSIETerminal()


def serve_local_file(relative_path, root):
    """发送项目内的静态文件，并强制浏览器每次都回来校验。

    默认的 static_file 只给 Last-Modified、不给 Cache-Control，浏览器会
    按「启发式缓存」自行决定缓存多久（可能好几小时）。结果是改了前端但
    用户看到的还是旧页面——甚至连 cassie_play.html 本身都被缓存，
    于是脚本标签上的 ?v= 版本号根本到不了浏览器，怎么刷新都没用。

    这里自己发文件，因为 static_file() 把它自己的 header 延后到响应
    收尾阶段才写入，路由里再 set_header 会被它覆盖掉。
    """
    target = os.path.normpath(os.path.join(root, relative_path))
    # 防目录穿越：规范化后必须仍在 root 内
    root_abs = os.path.normpath(os.path.abspath(root))
    target_abs = os.path.normpath(os.path.abspath(target))
    if not target_abs.startswith(root_abs + os.sep) and target_abs != root_abs:
        abort(404, 'Not found')
    if not os.path.isfile(target_abs):
        abort(404, 'Not found')

    response.content_type = mimetypes.guess_type(target_abs)[0] or 'application/octet-stream'
    response.set_header('Content-Length', str(os.path.getsize(target_abs)))
    response.set_header('Cache-Control', 'no-cache, must-revalidate')
    response.set_header('Pragma', 'no-cache')

    with open(target_abs, 'rb') as handle:
        return handle.read()


@route('/cassie_play')
def index():
    return serve_local_file('cassie_play.html', PROJECT_BASE_PATH)

@route('/static/<filepath:path>')
def serve_static(filepath):
    return serve_local_file(filepath, PROJECT_BASE_PATH + os.sep + 'static')

@route('/help')
def help_page():
    return serve_local_file('help.html', os.path.join(PROJECT_BASE_PATH, 'docs'))

@route('/developer')
def developer_page():
    return serve_local_file('developer.html', os.path.join(PROJECT_BASE_PATH, 'docs'))

@route('/word-search')
def word_search_page():
    return serve_local_file('index.html', os.path.join(PROJECT_BASE_PATH, 'tools', 'word_search'))

@route('/check_spelling', method='POST')
def check_spelling():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    not_found = cassie.check_spelling(data.get('text', ''))
    return {'not_found': not_found}

@route('/check_spelling_display', method='POST')
def check_spelling_display():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    text = data.get('text', '')
    not_found = cassie.check_spelling(text)
    return {'text': text, 'not_found': not_found}

@route('/get_presets', method='GET')
def get_presets():
    return cassie.presets

@route('/save_preset', method='POST')
def save_preset():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    cassie.presets[data['name']] = data['content']
    cassie.save_presets()
    return {'status': 'ok'}

@route('/delete_preset', method='POST')
def delete_preset():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    if data['name'] in cassie.presets:
        del cassie.presets[data['name']]
        cassie.save_presets()
    return {'status': 'ok'}

@route('/import_presets', method='POST')
def import_presets():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    for name, content in data.items():
        cassie.presets[name] = content
    cassie.save_presets()
    return {'status': 'ok'}

@route('/play', method='POST')
def play():
    try:
        response.content_type = 'text/event-stream'
        response.set_header('Cache-Control', 'no-cache')
        response.set_header('Access-Control-Allow-Origin', '*')
        
        body = request.body.read().decode('utf-8')
        data = json.loads(body)

        if not cassie.play_lock.acquire(False):
            yield_data = {"error": tr('play_or_export_busy')}
            return yield_data
        
        cassie.enable_bell = data.get('enable_bell', False)
        cassie.enable_special_bell = data.get('enable_special_bell', False)
        cassie.enable_number_reading = data.get('enable_number_reading', False)
        cassie.verbose_mode = data.get('verbose_mode', False)
        cassie.pitch = data.get('pitch', 1.0)
        cassie.speed = data.get('speed', -10)
        
        def generate():
            # 进度回调存在线程局部里，同一个线程消费生成器，所以是安全的
            queue = []

            def on_progress(stage, done, total, percent):
                queue.append({'type': 'progress', 'stage': stage, 'done': done,
                              'total': total, 'percent': percent})

            try:
                cassie.begin_progress(0, on_progress)
                yield "data: {}\n\n".format(json.dumps(
                    cassie.estimate_preprocess_event(data.get('text', '')),
                    ensure_ascii=False))
                for log in cassie.play_broadcast_stream(data.get('text', ''), lock_acquired=True):
                    # 攒下的进度事件要先发，否则时序会乱
                    while queue:
                        yield "data: {}\n\n".format(
                            json.dumps(queue.pop(0), ensure_ascii=False))
                    yield f"data: {json.dumps(log)}\n\n"
                while queue:
                    yield "data: {}\n\n".format(
                        json.dumps(queue.pop(0), ensure_ascii=False))
                yield "data: {\"type\": \"end\"}\n\n"
            except Exception as e:

                traceback.print_exc()
                yield f"data: {json.dumps({'text': tr('play_error', error=str(e)), 'type': 'error'})}\n\n"
            finally:
                cassie.end_progress()

        return generate()
    except Exception as e:

        traceback.print_exc()
        return {'error': str(e)}

@route('/export_progress', method='POST')
def export_wav_with_progress():
    """带真实进度的导出（SSE）。

    合成完之前不发音频本体，只发进度事件；最后一条 `done` 带上文件名，
    浏览器再走一次 /export 拿文件。这样进度条反映的是**服务端真实进度**，
    而不是前端猜的动画。

    用 SSE 而不是轮询：合成是单线程阻塞的，轮询需要另起线程共享状态，
    而 SSE 天然就是"一边算一边推"。
    """
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    text = data.get('text', '')
    if not text or not text.strip():
        return {'success': False, 'message': tr('content_empty')}

    response.content_type = 'text/event-stream'
    response.set_header('Cache-Control', 'no-cache')
    response.set_header('X-Accel-Buffering', 'no')

    def generate():
        queue = []
        finished = {'done': False, 'ok': False, 'message': ''}

        def on_progress(stage, done, total, percent):
            queue.append({'type': 'progress', 'stage': stage, 'done': done,
                          'total': total, 'percent': percent})

        def worker():
            try:
                with cassie.settings_snapshot({
                    'include_bell': bool(data.get('enable_bell', cassie.enable_bell)),
                    'enable_special_bell': bool(data.get('enable_special_bell',
                                                         cassie.enable_special_bell)),
                    'enable_number_reading': bool(data.get('enable_number_reading',
                                                           cassie.enable_number_reading)),
                    'pitch': float(data.get('pitch', cassie.pitch)),
                    'speed': float(data.get('speed', cassie.speed)),
                }):
                    cassie.begin_progress(0, on_progress)
                    try:
                        ok, result, meta = cassie.synthesize(
                            text=text, overrides=None,
                            filename='broadcast.wav')
                    finally:
                        cassie.end_progress()
                finished['ok'] = bool(ok)
                finished['message'] = '' if ok else str(result)
            except Exception as error:
                traceback.print_exc()
                finished['message'] = str(error)
            finally:
                finished['done'] = True

        thread = threading.Thread(target=worker, daemon=True, name='cassie-export')
        thread.start()
        yield 'data: {}\n\n'.format(json.dumps(
            {'type': 'start'}, ensure_ascii=False))

        last_sent = -1
        while True:
            while queue:
                event = queue.pop(0)
                if event['percent'] != last_sent or event['stage'] != 'reverb':
                    last_sent = event['percent']
                yield 'data: {}\n\n'.format(json.dumps(event, ensure_ascii=False))
            if finished['done']:
                break
            time.sleep(0.05)

        while queue:
            yield 'data: {}\n\n'.format(json.dumps(queue.pop(0), ensure_ascii=False))

        final = {'type': 'done', 'success': finished['ok']}
        if finished['ok']:
            final['filename'] = 'broadcast.wav'
        else:
            final['message'] = finished['message']
        yield 'data: {}\n\n'.format(json.dumps(final, ensure_ascii=False))

    return generate()


@route('/export', method='POST')
def export_wav():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    text = data.get('text', '')
    device_name = data.get('device', '')

    if not text:
        return {'success': False, 'message': tr('content_empty')}

    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_path = temp_file.name
    temp_file.close()

    try:

        success, result = cassie.export_from_queue(
            text=text,
            output_path=temp_path,
            include_bell=data.get('enable_bell', cassie.enable_bell),
            device=device_name,
            pitch=data.get('pitch', cassie.pitch),
            speed=data.get('speed', cassie.speed),
            enable_number_reading=data.get('enable_number_reading', cassie.enable_number_reading),
            enable_special_bell=data.get('enable_special_bell', cassie.enable_special_bell)
        )
        if success:
            with open(result, 'rb') as exported_file:
                response.content_type = 'audio/wav'
                response.set_header('Content-Disposition', 'attachment; filename="broadcast.wav"')
                content = exported_file.read()
            os.unlink(result)
            return content
        else:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return {'success': False, 'message': result}
    except Exception as e:

        traceback.print_exc()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return {'success': False, 'message': str(e)}


@route('/get_advanced_settings', method='GET')
def get_advanced_settings():
    return {
        'bell_lead_time': cassie.bell_lead_time,
        'bell_extra_duration': cassie.bell_extra_duration,
        'special_bell_start': cassie.special_bell_start,
        'special_bell_end': cassie.special_bell_end,
        'broadcast_effect_enabled': cassie.broadcast_effect_enabled,
        'low_cut_freq': cassie.low_cut_freq,
        'high_cut_freq': cassie.high_cut_freq,
        'mid_boost_gain': cassie.mid_boost_gain,
        'overdrive_gain': cassie.overdrive_gain,
        'clip_threshold': cassie.clip_threshold,
        'compressor_threshold': cassie.compressor_threshold,
        'compressor_ratio': cassie.compressor_ratio,
        'reverb_enabled': cassie.reverb_enabled,
        'reverb_pre_delay': cassie.reverb_pre_delay,
        'reverb_room_size': cassie.reverb_room_size,
        'reverb_decay_time': cassie.reverb_decay_time,
        'reverb_damping': cassie.reverb_damping,
        'reverb_diffusion': cassie.reverb_diffusion,
        'reverb_tail_brightness': cassie.reverb_tail_brightness,
        'reverb_wet': cassie.reverb_wet,
        'treble_stretch': cassie.treble_stretch,
        'treble_tail_gain': cassie.treble_tail_gain,
        'noise_volume': cassie.noise_volume,
        'noise_type': cassie.noise_type,
        'spatial_quality': cassie.spatial_quality,
        'spatial_mode': cassie.spatial_mode,
        'spatial_quality_levels': [
            # name / summary 是给前端渲染的文案，按当前请求语言取
            {'level': item['level'],
             'name': tr('spatial_level_{}_name'.format(item['level'])),
             'summary': tr('spatial_level_{}_summary'.format(item['level']))}
            for item in CASSIETerminal.SPATIAL_QUALITY_LEVELS
        ],
        'spatial_modes': list(CASSIETerminal.SPATIAL_MODES),
        'spatial_mode_labels': {mode: tr('spatial_mode_' + mode)
                                for mode in CASSIETerminal.SPATIAL_MODES},
        'spatial_mode_summaries': {mode: tr('spatial_mode_' + mode + '_summary')
                                   for mode in CASSIETerminal.SPATIAL_MODES},
    }

@route('/save_advanced_settings', method='POST')
def save_advanced_settings():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    cassie.bell_lead_time = data.get('bell_lead_time', 3.0)
    cassie.bell_extra_duration = data.get('bell_extra_duration', 3.0)
    cassie.special_bell_start = data.get('special_bell_start', 'bell_start.wav')
    cassie.special_bell_end = data.get('special_bell_end', 'bell_end.wav')
    cassie.broadcast_effect_enabled = data.get('broadcast_effect_enabled', False)
    cassie.low_cut_freq = data.get('low_cut_freq', 0)
    cassie.high_cut_freq = data.get('high_cut_freq', 0)
    cassie.mid_boost_gain = data.get('mid_boost_gain', 2.0)
    cassie.overdrive_gain = data.get('overdrive_gain', 0.0)
    cassie.clip_threshold = data.get('clip_threshold', 0.0)
    cassie.compressor_threshold = data.get('compressor_threshold', -12.0)
    cassie.compressor_ratio = data.get('compressor_ratio', 6.0)

    cassie.reverb_enabled = data.get('reverb_enabled', True)
    cassie.reverb_pre_delay = float(data.get('reverb_pre_delay', data.get('reverb_delay', 18.0)))
    cassie.reverb_room_size = float(data.get('reverb_room_size', 1.0))
    legacy_decay = data.get('reverb_decay')
    if data.get('reverb_decay_time') is not None:
        cassie.reverb_decay_time = float(data['reverb_decay_time'])
    elif legacy_decay is not None:
        cassie.reverb_decay_time = max(0.2, float(legacy_decay) / 1000.0)
    cassie.reverb_damping = float(data.get('reverb_damping', data.get('reverb_lowpass', 4000.0)))
    cassie.reverb_diffusion = float(data.get('reverb_diffusion', 0.72))
    cassie.reverb_tail_brightness = float(data.get('reverb_tail_brightness', 0.55))
    cassie.reverb_wet = float(data.get('reverb_wet', 0.35))

    cassie.treble_stretch = data.get('treble_stretch', 800.0)
    cassie.treble_tail_gain = float(data.get('treble_tail_gain', -28.0))
    cassie.noise_volume = data.get('noise_volume', -35.0)
    cassie.noise_type = data.get('noise_type', 'pink')

    cassie.spatial_quality = CASSIETerminal.quality_profile(
        data.get('spatial_quality', cassie.spatial_quality))['level']
    requested_mode = str(data.get('spatial_mode', cassie.spatial_mode)).lower()
    cassie.spatial_mode = requested_mode if requested_mode in CASSIETerminal.SPATIAL_MODES \
        else 'word'

    cassie._reverb_cache.clear()
    saved, message = cassie.save_settings()
    if not saved:
        return {'success': False, 'message': tr('settings_save_failed', message=message)}
    return {'success': True}


# HTTP API：全部挂在 /api/v1 下，响应是 JSON 信封；
# 只有 /api/v1/synthesize?download=1 例外，直接返回 WAV。

def _api_ready():
    """统一的鉴权入口，返回 None 表示通过，否则返回错误响应。"""
    return api_guard()


@api_route('')
@api_route('/')
def api_index():
    guard = _api_ready()
    if guard:
        return guard
    return api_success(cassie.api_documentation())


@api_route('/health')
def api_health():
    guard = _api_ready()
    if guard:
        return guard
    return api_success(cassie.health())


@api_route('/words')
def api_words():
    guard = _api_ready()
    if guard:
        return guard
    words = cassie.list_words()
    return api_success({'count': len(words), 'words': words})


@api_route('/sounds')
def api_sounds():
    guard = _api_ready()
    if guard:
        return guard
    sounds = cassie.list_sounds()
    return api_success({'count': len(sounds), 'sounds': sounds})


@api_route('/validate', method='POST')
def api_validate():
    guard = _api_ready()
    if guard:
        return guard
    data = api_payload()
    if data is None:
        return api_error(tr('json_object_required'), code='invalid_json')
    text = data.get('text', '')
    if not isinstance(text, str):
        return api_error(tr('text_must_be_string'))
    return api_success(cassie.validate_text(text))


@api_route('/plan', method='POST')
def api_plan():
    guard = _api_ready()
    if guard:
        return guard
    data = api_payload()
    if data is None:
        return api_error(tr('json_object_required'), code='invalid_json')
    text = data.get('text', '')
    if not text or not text.strip():
        return api_error(tr('content_empty'), code='empty_text')
    overrides = {k: v for k, v in data.items() if k in API_MUTABLE_FIELDS}
    try:
        result = cassie.plan_broadcast(text, overrides)
    except Exception as error:
        traceback.print_exc()
        return api_error(tr('plan_failed', error=error), code='plan_failed', status=500)
    return api_success(result)


@api_route('/synthesize', method='POST')
def api_synthesize():
    """合成广播。默认返回 JSON（含 base64 音频），download=1 时直接返回 WAV。"""
    guard = _api_ready()
    if guard:
        return guard
    data = api_payload()
    if data is None:
        return api_error(tr('json_object_required'), code='invalid_json')
    text = data.get('text', '')
    if not text or not text.strip():
        return api_error(tr('content_empty'), code='empty_text')

    overrides = {k: v for k, v in data.items() if k in API_MUTABLE_FIELDS}
    download = bool(data.get('download')) or request.query.get('download') in ('1', 'true', 'yes')
    as_base64 = bool(data.get('base64'))
    filename = data.get('filename') or 'cassie_broadcast.wav'
    if not str(filename).lower().endswith('.wav'):
        filename = '{}.wav'.format(filename)
    filename = os.path.basename(str(filename))

    ok, result, metadata = cassie.synthesize(text, overrides=overrides, filename=filename)
    if not ok:
        # 文案随语言变化，两种语言都要认得，才能给出 409
        status = 409 if any(message in str(result) for message in
                            (MESSAGES['zh']['play_busy'], MESSAGES['en']['play_busy'])) else 400
        return api_error(result, code='synthesize_failed', status=status)

    try:
        with open(result, 'rb') as handle:
            payload = handle.read()
    except OSError as error:
        return api_error(tr('read_result_failed', error=error), code='read_failed', status=500)
    finally:
        try:
            os.unlink(result)
        except OSError:
            pass

    digest = hashlib.sha256(payload).hexdigest()
    metadata['sha256'] = digest
    metadata['size_bytes'] = len(payload)

    if download:
        response.content_type = 'audio/wav'
        response.set_header('Content-Disposition',
                            'attachment; filename="{}"'.format(filename))
        response.set_header('X-Cassie-Sha256', digest)
        response.set_header('X-Cassie-Elapsed-Ms', str(metadata['elapsed_ms']))
        return payload

    body = {'metadata': metadata}
    if as_base64 or not download:
        body['audio_base64'] = base64.b64encode(payload).decode('ascii')
    return api_success(body)


@api_route('/play', method='POST')
def api_play():
    guard = _api_ready()
    if guard:
        return guard
    data = api_payload()
    if data is None:
        return api_error(tr('json_object_required'), code='invalid_json')
    text = data.get('text', '')
    if not text or not text.strip():
        return api_error(tr('content_empty'), code='empty_text')
    overrides = {k: v for k, v in data.items() if k in API_MUTABLE_FIELDS}
    started, message = cassie.start_playback(text, overrides)
    if not started:
        return api_error(message, code='playback_rejected', status=409)
    return api_success({'playing': True, 'text': text}, status=202)


@api_route('/stop', method='POST')
def api_stop():
    guard = _api_ready()
    if guard:
        return guard
    cassie.stop_playback()
    return api_success({'playing': False, 'stop_requested': True})


@api_route('/status')
def api_status():
    guard = _api_ready()
    if guard:
        return guard
    return api_success({
        'playing': bool(cassie.is_playing),
        'stop_requested': bool(cassie.stop_requested),
        'play_lock_held': bool(cassie.play_lock.locked()),
    })


@api_route('/settings')
def api_get_settings():
    guard = _api_ready()
    if guard:
        return guard
    return api_success({
        'settings': cassie.snapshot_settings(),
        'defaults': SYNTHESIS_PARAM_DEFAULTS,
        'mutable_fields': list(API_MUTABLE_FIELDS),
    })


@api_route('/settings', method='POST')
@api_route('/settings', method='PUT')
def api_set_settings():
    guard = _api_ready()
    if guard:
        return guard
    data = api_payload()
    if data is None:
        return api_error(tr('json_object_required'), code='invalid_json')

    reset = bool(data.get('reset'))
    fields = {key: value for key, value in data.items() if key != 'reset'}

    unknown = sorted(key for key in fields if key not in API_MUTABLE_FIELDS)
    if unknown:
        return api_error(tr('unknown_fields', fields=', '.join(unknown)),
                         code='unknown_fields', unknown_fields=unknown)

    if reset:
        applied = dict(SYNTHESIS_PARAM_DEFAULTS)
    else:
        applied = {key: value for key, value in fields.items() if key in API_MUTABLE_FIELDS}

    if not applied:
        return api_error(tr('no_fields'), code='no_fields')

    if 'spatial_quality' in applied:
        applied['spatial_quality'] = CASSIETerminal.quality_profile(
            applied['spatial_quality'])['level']
    if 'spatial_mode' in applied:
        mode = str(applied['spatial_mode']).lower()
        if mode not in CASSIETerminal.SPATIAL_MODES:
            return api_error(
                tr('spatial_mode_invalid',
                   modes=language_join(CASSIETerminal.SPATIAL_MODES)),
                code='invalid_value')
        applied['spatial_mode'] = mode

    with cassie.settings_lock:
        for key, value in applied.items():
            setattr(cassie, key, value)
        cassie._reverb_cache.clear()
        cassie.save_settings()

    return api_success({'applied': applied, 'settings': cassie.snapshot_settings()})


@api_route('/presets')
def api_list_presets():
    guard = _api_ready()
    if guard:
        return guard
    presets = getattr(cassie, 'presets', {}) or {}
    return api_success({'count': len(presets), 'presets': presets})


@api_route('/presets', method='POST')
def api_save_preset():
    guard = _api_ready()
    if guard:
        return guard
    data = api_payload()
    if data is None:
        return api_error(tr('json_object_required'), code='invalid_json')
    name = (data.get('name') or '').strip()
    content = data.get('content')
    if not name:
        return api_error(tr('missing_name'), code='missing_name')
    if content is None:
        return api_error(tr('missing_content'), code='missing_content')
    cassie.presets[name] = content
    cassie.save_presets()
    return api_success({'name': name, 'content': content, 'count': len(cassie.presets)},
                       status=201)


@api_route('/presets/<name>', method='DELETE')
@api_route('/presets/<name>', method='GET')
def api_preset_detail(name):
    guard = _api_ready()
    if guard:
        return guard
    presets = getattr(cassie, 'presets', {}) or {}
    if request.method == 'DELETE':
        if name not in presets:
            return api_error(tr('preset_not_found', name=name), code='not_found', status=404)
        del presets[name]
        cassie.save_presets()
        return api_success({'deleted': name, 'count': len(presets)})

    if name not in presets:
        return api_error(tr('preset_not_found', name=name), code='not_found', status=404)
    return api_success({'name': name, 'content': presets[name]})


@api_route('/presets/<name>/play', method='POST')
def api_play_preset(name):
    guard = _api_ready()
    if guard:
        return guard
    presets = getattr(cassie, 'presets', {}) or {}
    if name not in presets:
        return api_error(tr('preset_not_found', name=name), code='not_found', status=404)
    started, message = cassie.start_playback(presets[name])
    if not started:
        return api_error(message, code='playback_rejected', status=409)
    return api_success({'playing': True, 'name': name, 'text': presets[name]}, status=202)


if __name__ == '__main__':
    _health = cassie.health()
    _missing = [name for name, present in _health['features'].items() if not present]
    _library = _health['library']

    # 素材缺失时放在最前面说清楚：这是新用户最容易卡住的地方，
    # 埋在后面的功能指纹里他们看不到。
    if not _library['word_files']:
        print()
        print('=' * 68)
        print(tr('assets_missing_title'))
        print(tr('assets_missing_where', path=_library['words_dir']))
        print(tr('assets_missing_how'))
        print(tr('assets_missing_how2', url=ASSETS_DOWNLOAD_URL))
        print(tr('assets_missing_after'))
        print('=' * 68)
        print()

    print(tr('startup_banner', version=PROJECT_VERSION, started_at=_health['started_at']))
    print(tr('startup_quality_levels', count=_health['spatial_quality_levels']))
    print(tr('startup_fingerprint',
             status=tr('startup_all_ready') if not _missing
             else tr('startup_missing', items=', '.join(_missing)),
             hint='' if not _missing else tr('startup_outdated_hint')))
    print(tr('startup_health_hint'))
    print(tr('startup_open_browser', port=port))
    run(host='localhost', port=port, server='cheroot', debug=True)
