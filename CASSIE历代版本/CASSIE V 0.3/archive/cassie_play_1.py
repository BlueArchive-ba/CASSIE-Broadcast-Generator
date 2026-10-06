from bottle import route, run, request, static_file, response
import json
import os
import time
import threading
import re
import pygame
import random
import wave
import contextlib
import tempfile
import traceback
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

AUDIO_BASE_PATH = "cassie/words/"
SOUND_BASE_PATH = "cassie/sounds/"
AUDIO_EXTENSION = ".wav"
PRESET_FILE = "presets.json"

pygame.mixer.init()
pygame.mixer.set_num_channels(4)

nato_map = {
    'alpha': 'a', 'bravo': 'b', 'charlie': 'c', 'delta': 'd',
    'echo': 'e', 'foxtrot': 'f', 'golf': 'g', 'hotel': 'h',
    'india': 'i', 'juliett': 'j', 'kilo': 'k', 'lima': 'l',
    'mike': 'm', 'november': 'n', 'oscar': 'o', 'papa': 'p',
    'quebec': 'q', 'romeo': 'r', 'sierra': 's', 'tango': 't',
    'uniform': 'u', 'victor': 'v', 'whiskey': 'w', 'xray': 'x',
    'yankee': 'y', 'zulu': 'z'
}

class CASSIETerminal:
    def __init__(self):
        self.is_playing = False
        self.enable_bell = False
        self.enable_special_bell = False
        self.enable_number_reading = False
        self.verbose_mode = False
        self.stop_requested = False
        self.stutter_duration = 0.14
        self.word_channel = 0
        self.bell_channel = 1
        self.current_input = ""
        self.preset_file = PRESET_FILE
        self.word_set = self.load_word_set()
        self.load_presets()
        self.pitch = 1.0
        self.speed = 20
        self.alert_thread = None
        self.alert_running = False
        self.alert_stop = threading.Event()

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

    def get_audio_duration(self, filepath):
        if not os.path.exists(filepath):
            return 0
        try:
            import wave
            import contextlib
            with contextlib.closing(wave.open(filepath, 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return frames / float(rate)
        except:
            return 0.5

    def play_bell_audio(self, filepath):
        def play():
            if not os.path.exists(filepath):
                return
            sound = pygame.mixer.Sound(filepath)
            pygame.mixer.Channel(self.bell_channel).play(sound)
            time.sleep(self.get_audio_duration(filepath))
        thread = threading.Thread(target=play)
        thread.daemon = True
        thread.start()

    def play_audio_on_channel(self, channel, filepath, start_delay=0, pitch=1.0, speed=0):
        if start_delay > 0:
            time.sleep(start_delay)
        if not os.path.exists(filepath):
            return
        
        from pydub import AudioSegment
        from pydub.silence import detect_leading_silence
        
        with open(filepath, 'rb') as f:
            audio = AudioSegment.from_wav(f)
        
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
        
        processed_duration = len(audio) / 1000.0
        export_path = "/tmp/temp_audio.wav"
        audio.export(export_path, format="wav")
        sound = pygame.mixer.Sound(export_path)
        pygame.mixer.Channel(channel).play(sound)
        time.sleep(processed_duration)

    def play_stutter(self, filepath, stutter_count, pitch=1.0, speed=0, full_play=True):
        if not os.path.exists(filepath):
            return
        
        from pydub import AudioSegment
        from pydub.silence import detect_leading_silence
        
        with open(filepath, 'rb') as f:
            audio = AudioSegment.from_wav(f)
        
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
        
        export_path = "/tmp/temp_stutter.wav"
        audio.export(export_path, format="wav")
        
        if speed > 0:
            wait_time = (speed / 20) * 1.0
            time.sleep(wait_time)
        
        duration = self.get_audio_duration(export_path)
        
        stutter_duration = min(duration, self.stutter_duration)
        sound = pygame.mixer.Sound(export_path)
        
        for _ in range(stutter_count):
            pygame.mixer.Channel(self.word_channel).play(sound)
            time.sleep(stutter_duration)
            pygame.mixer.Channel(self.word_channel).stop()
        
        if full_play:
            pygame.mixer.Channel(self.word_channel).play(sound)
            time.sleep(duration)

    

    def process_number(self, num_str):
        num = float(num_str)
        parts = num_str.split('.')
        integer_part = int(parts[0])
        decimal_part = parts[1] if len(parts) > 1 else None
        result = []
        if integer_part > 0:
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
            result.append('full')
            result.append('stop')
            for digit in decimal_part:
                result.append(digit)
        return result

    def play_alert(self, alert_id, mode):
        template_path = "template_library.json"
        with open(template_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        found = None
        for t in data.get('templates', []):
            if t.get('id') == alert_id:
                found = t
                break
        if not found:
            print(f"[错误] 未找到警报模板: {alert_id}")
            return
        filepath = found.get('path')
        if not os.path.exists(filepath):
            print(f"[错误] 警报文件不存在: {filepath}")
            return
        with open(filepath, 'rb') as f:
            audio = AudioSegment.from_wav(f)
        if mode == 'loop':
            self.alert_stop.clear()
            self.alert_running = True
            def alert_loop():
                while self.alert_running and not self.alert_stop.is_set():
                    pygame.mixer.Channel(self.bell_channel).play(pygame.mixer.Sound(filepath))
                    time.sleep(len(audio) / 1000.0)
            self.alert_thread = threading.Thread(target=alert_loop)
            self.alert_thread.daemon = True
            self.alert_thread.start()
        else:
            sound = pygame.mixer.Sound(filepath)
            pygame.mixer.Channel(self.bell_channel).play(sound)
    
    def stop_all_alerts(self):
        self.alert_running = False
        self.alert_stop.set()
        if self.alert_thread and self.alert_thread.is_alive():
            self.alert_thread.join(timeout=0.5)
        pygame.mixer.Channel(self.bell_channel).stop()

    def parse_segment(self, segments, current_index):
        if not segments or current_index >= len(segments):
            return []
        segment = segments[current_index]
        if not segment:
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
            if segment == '[gap:none]':
                return [('gap', None)]
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

        if segment.startswith('[alert:'):
            if segment == '[alert:none]':
                self.stop_all_alerts()
                return []
            try:
                inner = segment[7:-1]
                parts = inner.split(',')
                alert_id = parts[0].strip()
                mode = parts[1].strip() if len(parts) > 1 else 'once'
                self.play_alert(alert_id, mode)
                return []
            except:
                return []

        stutter_match = re.match(r'^\[stutter:(\d+)(?:\|full:(true|false))?\](.+)$', segment)
        if stutter_match:
            stutter_count = int(stutter_match.group(1))
            full_play = stutter_match.group(2) if stutter_match.group(2) else 'true'
            full_play = full_play == 'true'
            actual_word = stutter_match.group(3)
            temp_segments = segments[:current_index] + [actual_word] + segments[current_index+1:]
            word_queue = self.parse_segment(temp_segments, current_index)
            if word_queue:
                pitch = word_queue[0][2] if len(word_queue[0]) > 2 else 1.0
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
            return [('pause', 0.5)]
        if segment == ',':
            return [('pause', 0.2)]
        if segment == '、':
            return [('pause', 0.1)]

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
                return [('word', p) for p in num_parts]

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

    def play_broadcast_stream(self, text):
        if self.is_playing:
            yield {"text": "正在播放中，请稍后再试", "type": "error"}
            return
        if not text:
            yield {"text": "内容不能为空", "type": "error"}
            return

        gap_value = None
        error_value = None
        #print("text before processing:", repr(text))

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


#backup unit has+entered+the+facility
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

        

        gap_match = re.search(r'\[gap:([^\]]+)\]', text)
        if gap_match:
            gap_raw = gap_match.group(1).strip()
            if gap_raw == 'none':
                gap_value = None
            else:
                try:
                    gap_value = float(gap_raw)
                except:
                    gap_value = None
            text = re.sub(r'\[gap:[^\]]+\]', '', text)

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
                    yield {"text": "[未找到] " + segments[i], "type": "error"}
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
                            yield {"text": "[播放铃声] bell_start", "type": "info"}
                    else:
                        yield {"text": "[铃声缺失] bell_start.wav", "type": "error"}
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
                    need_seconds = int(total_duration) + 2
                    if need_seconds < 4:
                        need_seconds = 4
                    bell_file = os.path.join(SOUND_BASE_PATH, "bg_" + str(need_seconds) + ".wav")
                    if os.path.exists(bell_file):
                        self.play_bell_audio(bell_file)
                        if self.verbose_mode:
                            yield {"text": "[播放铃声] bg_" + str(need_seconds), "type": "info"}
                    else:
                        yield {"text": "[铃声缺失] bg_" + str(need_seconds) + ".wav", "type": "error"}
                time.sleep(1)

            if gap_value is not None:
                time.sleep(gap_value)

            current_speed_all = self.pitch
            total_words = len([item for item in full_queue if item[0] in ('word', 'stutter')])
            word_index = 0

            for item in full_queue:
                if self.stop_requested:
                    break
                if item[0] == 'speed_all':
                    current_speed_all = item[1]
                    continue
                if item[0] == 'pause':
                    if self.verbose_mode:
                        yield {"text": "[停顿] " + str(item[1]) + "秒", "type": "info"}
                    time.sleep(item[1])
                elif item[0] == 'stutter':
                    word_index += 1
                    filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                    stutter_count = item[2]
                    pitch = item[3] if len(item) > 3 else current_speed_all
                    if self.verbose_mode:
                        yield {"text": "[" + str(word_index) + "/" + str(total_words) + "] " + item[1] + " (卡顿" + str(stutter_count) + "次, 音高 " + str(pitch) + ")", "type": "info"}
                    self.play_stutter(filepath, stutter_count, pitch, speed=self.speed)
                elif item[0] == 'word':
                    word_index += 1
                    filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                    pitch = item[2] if len(item) > 2 else current_speed_all
                    if self.verbose_mode:
                        yield {"text": "[" + str(word_index) + "/" + str(total_words) + "] " + item[1] + " (音高 " + str(pitch) + ")", "type": "info"}
                    self.play_audio_on_channel(self.word_channel, filepath, pitch=pitch, speed=self.speed)

            if self.enable_bell and self.enable_special_bell:
                end_file = os.path.join(SOUND_BASE_PATH, "bell_end.wav")
                if os.path.exists(end_file):
                    self.play_bell_audio(end_file)
                    if self.verbose_mode:
                        yield {"text": "[播放铃声] bell_end", "type": "info"}
                    time.sleep(self.get_audio_duration(end_file))

            if self.verbose_mode:
                yield {"text": "播放完成", "type": "info"}

        finally:
            self.is_playing = False
            self.stop_requested = False
            #self.stop_all_alerts()


    def export_from_queue(self, full_queue, output_path, include_bell=False):
        if not full_queue:
            return False, "没有音频可导出"

        from pydub import AudioSegment
        from pydub.silence import detect_leading_silence
        import os

        combined = AudioSegment.empty()
        speed = self.speed

        for item in full_queue:
            if item[0] == 'word':
                filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                if not os.path.exists(filepath):
                    continue
                with open(filepath, 'rb') as f:
                    audio = AudioSegment.from_wav(f)
                pitch = item[2] if len(item) > 2 else 1.0
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
                combined += audio

            elif item[0] == 'stutter':
                filepath = os.path.join(AUDIO_BASE_PATH, item[1] + AUDIO_EXTENSION)
                if not os.path.exists(filepath):
                    continue
                with open(filepath, 'rb') as f:
                    audio = AudioSegment.from_wav(f)
                pitch = item[3] if len(item) > 3 else 1.0
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
                stutter_duration_ms = int(self.stutter_duration * 1000)
                if len(audio) > stutter_duration_ms:
                    stutter_piece = audio[:stutter_duration_ms]
                else:
                    stutter_piece = audio
                for _ in range(item[2]):
                    combined += stutter_piece
                combined += audio

            elif item[0] == 'pause':
                sample_rate = 44100
                silent = AudioSegment.silent(duration=int(item[1] * 1000), frame_rate=sample_rate)
                combined += silent

            elif item[0] == 'gap':
                if item[1] is not None:
                    sample_rate = 44100
                    silent = AudioSegment.silent(duration=int(item[1] * 1000), frame_rate=sample_rate)
                    combined += silent

        if include_bell:
            bell_file = os.path.join(SOUND_BASE_PATH, "bell_start.wav")
            if os.path.exists(bell_file):
                with open(bell_file, 'rb') as f:
                    bell = AudioSegment.from_wav(f)
                combined = bell + combined
            end_file = os.path.join(SOUND_BASE_PATH, "bell_end.wav")
            if os.path.exists(end_file):
                with open(end_file, 'rb') as f:
                    end_bell = AudioSegment.from_wav(f)
                combined = combined + end_bell

        if len(combined) == 0:
            return False, "没有音频数据可导出"

        output_path_mp3 = output_path.replace('.mp3', '.wav')
        combined.export(output_path_mp3, format="mp3")
        return True, output_path_mp3
    
    def process_audio_with_pitch(self, filepath, pitch):
        if pitch == 1.0:
            return filepath
        from pydub import AudioSegment
        with open(filepath, 'rb') as f:
            audio = AudioSegment.from_wav(f)
        new_frame_rate = int(audio.frame_rate * pitch)
        audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
        audio = audio.set_frame_rate(audio.frame_rate)
        export_path = "/tmp/temp_pitch_audio.wav"
        audio.export(export_path, format="wav")
        return export_path

cassie = CASSIETerminal()

@route('/cassie_play')
def index():
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>C.A.S.S.I.E. 广播生成器</title>
    <link rel="stylesheet" href="/static/style.css">
    <style>
.slider-group {
    display: flex;
    align-items: center;
    gap: 16px;
    color: #cbd5e6;
    font-size: 13px;
    margin: 4px 0;
}

.slider-label {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 80px;
}

.slider-label span {
    color: #eef2f5;
    font-size: 13px;
    font-weight: 400;
}

.slider-value {
    min-width: 44px;
    text-align: right;
    font-family: 'Fira Code', monospace;
    font-size: 13px;
    font-weight: 500;
    color: #79c0ff;
}

input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 120px;
    height: 4px;
    border-radius: 2px;
    background: #3a4050;
    outline: none;
    cursor: pointer;
}

input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #6c7ea0;
    cursor: pointer;
    border: 2px solid #8e9aaf;
}

input[type="range"]::-webkit-slider-thumb:hover {
    background: #7c8aa0;
    transform: scale(1.1);
}

input[type="range"]::-webkit-slider-thumb:active {
    transform: scale(0.92);
}
</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>C.A.S.S.I.E. 广播生成器</h1>
            <div class="subtitle">Central Autonomic Service System for Internal Emergencies</div>
        </div>
        <div class="options-panel">
    <!-- 勾选框保持不变 -->
    <label class="checkbox-label">
        <input type="checkbox" id="enableBell">
        <span class="checkbox-custom"></span>
        <span>广播铃声</span>
    </label>
    <label class="checkbox-label">
        <input type="checkbox" id="enableSpecialBell" disabled>
        <span class="checkbox-custom"></span>
        <span>特殊铃声</span>
    </label>
    <label class="checkbox-label">
        <input type="checkbox" id="enableNumberReading">
        <span class="checkbox-custom"></span>
        <span>数字朗读</span>
    </label>
    <label class="checkbox-label">
        <input type="checkbox" id="verboseMode">
        <span class="checkbox-custom"></span>
        <span>详细输出</span>
    </label>

    <!-- 音高控制 -->
    <div class="slider-group">
        <label class="slider-label">
            <span>音高</span>
            <span class="slider-value" id="pitchValue">1.00</span>
        </label>
        <input type="range" id="pitchSlider" min="0.1" max="10.0" step="0.05" value="1.0">
    </div>

    <!-- 语速控制 -->
    <div class="slider-group">
        <label class="slider-label">
            <span>语速</span>
            <span class="slider-value" id="speedValue">-10</span>
        </label>
        <input type="range" id="speedSlider" min="-20" max="20" step="1" value="-10">
    </div>
</div>
        <div class="terminal">
            <div class="terminal-header">
                <span>输出终端</span>
                <button id="clearTerminal" class="clear-btn">清空</button>
            </div>
            <div id="terminalContent" class="terminal-content">
                <div class="terminal-line normal">就绪。请输入广播内容。</div>
            </div>
        </div>
        <div class="input-area">
            <textarea id="broadcastInput" rows="4" placeholder="输入广播内容..."></textarea>
<div class="button-group">
    <button id="spellCheckBtn" class="spellcheck-button">拼写检查</button>
    <button id="exportBtn" class="play-button">导出WAV</button>
    <button id="playBtn" class="play-button">播放广播</button>
</div>
        </div>
        <div class="status-bar">
            <span class="status-text" id="statusText">等待播放</span>
            <div class="volume-indicator" id="volumeIndicator">
                <div class="volume-fill" id="volumeFill"></div>
            </div>
        </div>
        <div class="bottom-bar">
            <a href="/help" target="_blank" class="help-link">使用说明</a>
            <button id="presetBtn" class="help-link">预设管理</button>
        </div>
    </div>
    <div id="presetModal" class="modal-overlay">
        <div class="modal">
            <button id="closeModal" class="modal-close">&times;</button>
            <h3>预设管理</h3>
            <div id="presetList" class="preset-list"></div>
            <input type="text" id="presetName" placeholder="预设名称">
            <textarea id="presetContent" rows="2" placeholder="广播内容"></textarea>
            <div class="modal-buttons">
                <button id="savePreset">保存预设</button>
                <button id="importPreset">从文件导入</button>
                <button id="playSelectedBtn">播放选中</button>
            </div>
        </div>
    </div>
    <script>
        var enableBell = false;
        var enableSpecialBell = false;
        var enableNumberReading = false;
        var verboseMode = false;
        var presets = {};
        var selectedPresets = [];

        var enableBellCheckbox = document.getElementById('enableBell');
        var enableSpecialBellCheckbox = document.getElementById('enableSpecialBell');
        var enableNumberReadingCheckbox = document.getElementById('enableNumberReading');
        var verboseModeCheckbox = document.getElementById('verboseMode');
        var broadcastInput = document.getElementById('broadcastInput');
        var playBtn = document.getElementById('playBtn');
        var spellCheckBtn = document.getElementById('spellCheckBtn');
        var clearTerminalBtn = document.getElementById('clearTerminal');
        var terminalContent = document.getElementById('terminalContent');
        var statusText = document.getElementById('statusText');
        var volumeFill = document.getElementById('volumeFill');
        var presetBtn = document.getElementById('presetBtn');
        var presetModal = document.getElementById('presetModal');
        var closeModal = document.getElementById('closeModal');
        var presetList = document.getElementById('presetList');
        var presetName = document.getElementById('presetName');
        var presetContent = document.getElementById('presetContent');
        var savePreset = document.getElementById('savePreset');
        var importPreset = document.getElementById('importPreset');
        var playSelectedBtn = document.getElementById('playSelectedBtn');
        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'preset-checkbox';

        enableBellCheckbox.addEventListener('change', function() {
            enableBell = this.checked;
            enableSpecialBellCheckbox.disabled = !enableBell;
            if (!enableBell) enableSpecialBellCheckbox.checked = false;
        });
        enableSpecialBellCheckbox.addEventListener('change', function() { enableSpecialBell = this.checked; });
        enableNumberReadingCheckbox.addEventListener('change', function() { enableNumberReading = this.checked; });
        verboseModeCheckbox.addEventListener('change', function() { verboseMode = this.checked; });

        function addTerminalLine(text, type) {
            var line = document.createElement('div');
            line.className = 'terminal-line ' + type;
            line.textContent = text;
            terminalContent.appendChild(line);
            line.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function addTerminalLineWithHighlight(text, notFoundWords) {
            var line = document.createElement('div');
            line.className = 'terminal-line spellcheck';
            var words = text.split(' ');
            var html = '';
            for (var i = 0; i < words.length; i++) {
                var word = words[i];
                if (notFoundWords.indexOf(word) !== -1) {
                    html += '<span style="color: #ff7b72; text-decoration: underline wavy #ff7b72;">' + word + '</span> ';
                } else {
                    html += word + ' ';
                }
            }
            line.innerHTML = html;
            terminalContent.appendChild(line);
            line.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function clearTerminal() {
            terminalContent.innerHTML = '';
            addTerminalLine('就绪。请输入广播内容。', 'normal');
        }
        clearTerminalBtn.addEventListener('click', clearTerminal);

        spellCheckBtn.addEventListener('click', function() {
            var text = broadcastInput.value.trim();
            if (!text) {
                addTerminalLine('请输入广播内容', 'error');
                return;
            }
            fetch('/check_spelling_display', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            }).then(function(res) { return res.json(); }).then(function(data) {
                addTerminalLineWithHighlight(data.text, data.not_found);
            });
        });

        var currentEventSource = null;
        function playBroadcast() {
            var text = broadcastInput.value.trim();
            if (!text) {
                addTerminalLine('请输入广播内容', 'error');
                return;
            }
            if (currentEventSource) {
                currentEventSource.close();
                currentEventSource = null;
            }
            statusText.textContent = '播放中';
            if (verboseMode) {
                terminalContent.innerHTML = '';
            }
            fetch('/play', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    enable_bell: enableBell,
                    enable_special_bell: enableSpecialBell,
                    enable_number_reading: enableNumberReading,
                    verbose_mode: verboseMode
                })
            }).then(function(response) {
                var reader = response.body.getReader();
                var decoder = new TextDecoder();
                function readStream() {
                    reader.read().then(function(result) {
                        if (result.done) {
                            statusText.textContent = '等待播放';
                            return;
                        }
                        var chunk = decoder.decode(result.value);
                        var lines = chunk.split('\\n');
                        for (var i = 0; i < lines.length; i++) {
                            if (lines[i].startsWith('data: ')) {
                                var data = JSON.parse(lines[i].substring(6));
                                if (data.type === 'end') {
                                    statusText.textContent = '等待播放';
                                    return;
                                }
                                addTerminalLine(data.text, data.type);
                            }
                        }
                        readStream();
                    });
                }
                readStream();
            }).catch(function(err) {
                addTerminalLine('播放失败: ' + err, 'error');
                statusText.textContent = '等待播放';
            });
        }
        playBtn.addEventListener('click', playBroadcast);

        function loadPresets() {
            fetch('/get_presets').then(function(res) { return res.json(); }).then(function(data) {
                presets = data;
                renderPresetList();
            });
        }

        function renderPresetList() {
    presetList.innerHTML = '';
    var names = Object.keys(presets);
    if (names.length === 0) {
        presetList.innerHTML = '<div style="color: #5c6e8c; text-align: center; padding: 20px;">暂无预设</div>';
        return;
    }
    var table = document.createElement('table');
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    table.style.fontFamily = 'monospace';
    table.style.fontSize = '12px';
    for (var i = 0; i < names.length; i++) {
        var name = names[i];
        var content = presets[name];
        var tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #232830';
        // 勾选框单元格
        var tdCheckbox = document.createElement('td');
        tdCheckbox.style.width = '30px';
        tdCheckbox.style.padding = '8px 0';
        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'preset-checkbox';
        checkbox.setAttribute('data-name', name);
        checkbox.addEventListener('change', function(e) {
            var n = e.target.getAttribute('data-name');
            if (e.target.checked) {
                if (selectedPresets.indexOf(n) === -1) selectedPresets.push(n);
            } else {
                var idx = selectedPresets.indexOf(n);
                if (idx !== -1) selectedPresets.splice(idx, 1);
            }
        });
        tdCheckbox.appendChild(checkbox);
        // 预设名称单元格
        var tdName = document.createElement('td');
        tdName.style.padding = '8px 12px';
        tdName.style.color = '#eef2f5';
        tdName.style.cursor = 'pointer';
        tdName.style.whiteSpace = 'nowrap';
        tdName.textContent = name;
        tdName.addEventListener('click', (function(n) {
            return function() {
                broadcastInput.value = presets[n];
                presetModal.classList.remove('show');
            };
        })(name));
        // 预览内容单元格
        var tdPreview = document.createElement('td');
        tdPreview.style.padding = '8px 0';
        tdPreview.style.color = '#5c6e8c';
        tdPreview.style.width = '100%';
        tdPreview.style.whiteSpace = 'nowrap';
        tdPreview.style.overflowX = 'auto';
        tdPreview.style.maxWidth = '300px';
        var preview = content.length > 50 ? content.substring(0, 50) + '...' : content;
        tdPreview.textContent = preview;
        // 删除按钮单元格
        var tdDelete = document.createElement('td');
        tdDelete.style.width = '30px';
        tdDelete.style.padding = '8px 0';
        tdDelete.style.textAlign = 'center';
        var deleteBtn = document.createElement('button');
        deleteBtn.textContent = '×';
        deleteBtn.style.background = 'none';
        deleteBtn.style.border = 'none';
        deleteBtn.style.color = '#ff7b72';
        deleteBtn.style.cursor = 'pointer';
        deleteBtn.style.fontSize = '16px';
        deleteBtn.setAttribute('data-name', name);
        deleteBtn.addEventListener('click', (function(n) {
            return function(e) {
                e.stopPropagation();
                fetch('/delete_preset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: n })
                }).then(function() { loadPresets(); });
            };
        })(name));
        tdDelete.appendChild(deleteBtn);
        tr.appendChild(tdCheckbox);
        tr.appendChild(tdName);
        tr.appendChild(tdPreview);
        tr.appendChild(tdDelete);
        table.appendChild(tr);
    }
    presetList.appendChild(table);
}

        presetBtn.addEventListener('click', function() {
            selectedPresets = [];
            loadPresets();
            presetModal.classList.add('show');
        });
        closeModal.addEventListener('click', function() { presetModal.classList.remove('show'); });
        presetModal.addEventListener('click', function(e) {
            if (e.target === presetModal) presetModal.classList.remove('show');
        });

        savePreset.addEventListener('click', function() {
            var name = presetName.value.trim();
            var content = presetContent.value.trim();
            if (!name || !content) return;
            fetch('/save_preset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, content: content })
            }).then(function() {
                presetName.value = '';
                presetContent.value = '';
                loadPresets();
            });
        });

        importPreset.addEventListener('click', function() {
            var input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.onchange = function(e) {
                var file = e.target.files[0];
                var reader = new FileReader();
                reader.onload = function(ev) {
                    fetch('/import_presets', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: ev.target.result
                    }).then(function() { loadPresets(); });
                };
                reader.readAsText(file);
            };
            input.click();
        });

        playSelectedBtn.addEventListener('click', function() {
            if (selectedPresets.length === 0) {
                addTerminalLine('请至少选择一个预设', 'error');
                return;
            }
            var combined = [];
            for (var i = 0; i < selectedPresets.length; i++) {
                combined.push(presets[selectedPresets[i]]);
            }
            var text = combined.join(' . ');
            broadcastInput.value = text;
            presetModal.classList.remove('show');
            playBroadcast();
        });

        var exportBtn = document.getElementById('exportBtn');
exportBtn.addEventListener('click', function() {
    var text = broadcastInput.value.trim();
    if (!text) {
        addTerminalLine('请输入广播内容', 'error');
        return;
    }
    statusText.textContent = '导出中';
    fetch('/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text })
}).then(function(res) {
    return res.blob();
}).then(function(blob) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'broadcast.wav';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    addTerminalLine('导出成功: broadcast.wav', 'normal');
    statusText.textContent = '等待播放';
}).catch(function(err) {
    addTerminalLine('导出失败: ' + err.message, 'error');
    statusText.textContent = '等待播放';
});
});
// 获取滑块元素
var pitchSlider = document.getElementById('pitchSlider');
var speedSlider = document.getElementById('speedSlider');
var pitchValue = document.getElementById('pitchValue');
var speedValue = document.getElementById('speedValue');

// 音高滑块事件
pitchSlider.addEventListener('input', function() {
    var val = parseFloat(this.value).toFixed(2);
    pitchValue.textContent = val;
});

// 语速滑块事件
speedSlider.addEventListener('input', function() {
    var val = parseInt(this.value, 10);
    speedValue.textContent = val;
    var color = '#79c0ff';
    if (val === -10) {
        color = '#ffffff';
    } else if (val < -10) {
        color = '#ff7b72';
    } else if (val < 0) {
        color = '#ffa500';
    } else if (val > 0) {
        color = '#ff7b72';
    } else {
        color = '#79c0ff';
    }
    speedValue.style.color = color;
});
// 初始化语速颜色
speedSlider.dispatchEvent(new Event('input'));

// 修改 playBroadcast 函数中的 fetch 请求，增加 pitch 和 speed 参数
function playBroadcast() {
    var text = broadcastInput.value.trim();
    if (!text) {
        addTerminalLine('请输入广播内容', 'error');
        return;
    }
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }
    statusText.textContent = '播放中';
    if (verboseMode) {
        terminalContent.innerHTML = '';
    }
    var pitch = parseFloat(pitchSlider.value);
    var speed = parseInt(speedSlider.value, 10);
    fetch('/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text: text,
            enable_bell: enableBell,
            enable_special_bell: enableSpecialBell,
            enable_number_reading: enableNumberReading,
            verbose_mode: verboseMode,
            pitch: pitch,
            speed: speed
        })
    }).then(function(response) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        function readStream() {
            reader.read().then(function(result) {
                if (result.done) {
                    statusText.textContent = '等待播放';
                    return;
                }
                var chunk = decoder.decode(result.value);
                var lines = chunk.split('\\n');
                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].startsWith('data: ')) {
                        var data = JSON.parse(lines[i].substring(6));
                        if (data.type === 'end') {
                            statusText.textContent = '等待播放';
                            return;
                        }
                        addTerminalLine(data.text, data.type);
                    }
                }
                readStream();
            });
        }
        readStream();
    }).catch(function(err) {
        addTerminalLine('播放失败: ' + err, 'error');
        statusText.textContent = '等待播放';
    });
}

        function updateVolume() {
            if (navigator.getUserMedia) {
                navigator.getUserMedia({ audio: true }, function(stream) {
                    var audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    var source = audioContext.createMediaStreamSource(stream);
                    var analyser = audioContext.createAnalyser();
                    analyser.fftSize = 256;
                    source.connect(analyser);
                    var dataArray = new Uint8Array(analyser.frequencyBinCount);
                    function getVolume() {
                        analyser.getByteFrequencyData(dataArray);
                        var sum = 0;
                        for (var i = 0; i < dataArray.length; i++) {
                            sum += dataArray[i];
                        }
                        var avg = sum / dataArray.length;
                        var percent = Math.min(100, (avg / 255) * 100);
                        volumeFill.style.width = percent + '%';
                        requestAnimationFrame(getVolume);
                    }
                    getVolume();
                }, function(err) {
                    console.log('麦克风权限未授予');
                });
            }
        }
        updateVolume();
    </script>
</body>
</html>
    '''

@route('/static/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root='static')

@route('/help')
def help_page():
    return static_file('help.html', root='.')

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

@route('/play', method='POST')
def play():
    response.content_type = 'text/event-stream'
    response.set_header('Cache-Control', 'no-cache')
    response.set_header('Access-Control-Allow-Origin', '*')
    
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    
    cassie.enable_bell = data.get('enable_bell', False)
    cassie.enable_special_bell = data.get('enable_special_bell', False)
    cassie.enable_number_reading = data.get('enable_number_reading', False)
    cassie.verbose_mode = data.get('verbose_mode', False)
    
    def generate():
        for log in cassie.play_broadcast_stream(data.get('text', '')):
            yield f"data: {json.dumps(log)}\n\n"
        yield "data: {\"type\": \"end\"}\n\n"
    
    return generate()

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
    response.content_type = 'text/event-stream'
    response.set_header('Cache-Control', 'no-cache')
    response.set_header('Access-Control-Allow-Origin', '*')
    
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    
    cassie.enable_bell = data.get('enable_bell', False)
    cassie.enable_special_bell = data.get('enable_special_bell', False)
    cassie.enable_number_reading = data.get('enable_number_reading', False)
    cassie.verbose_mode = data.get('verbose_mode', False)
    cassie.pitch = data.get('pitch', 1.0)
    cassie.speed = data.get('speed', -10)
    
    def generate():
        for log in cassie.play_broadcast_stream(data.get('text', '')):
            yield f"data: {json.dumps(log)}\n\n"
        yield "data: {\"type\": \"end\"}\n\n"
    
    return generate()

@route('/export', method='POST')
def export_wav():
    body = request.body.read().decode('utf-8')
    data = json.loads(body)
    text = data.get('text', '')

    if not text:
        return {'success': False, 'message': '内容不能为空'}

    gap_value = None
    error_value = None

    gap_match = re.search(r'\[gap:([^\]]+)\]', text)
    if gap_match:
        gap_raw = gap_match.group(1).strip()
        if gap_raw == 'none':
            gap_value = None
        else:
            try:
                gap_value = float(gap_raw)
            except:
                gap_value = None
        text = re.sub(r'\[gap:[^\]]+\]', '', text)

    error_match = re.search(r'\[error:(\d+)\]', text)
    if error_match:
        error_value = int(error_match.group(1))
        text = re.sub(r'\[error:\d+\]', '', text)

    text = re.sub(r'\s+', ' ', text).strip()
    segments = text.lower().split()

    full_queue = []
    i = 0
    while i < len(segments):
        parsed = cassie.parse_segment(segments, i)
        if parsed:
            full_queue.extend(parsed)
            i += 1
        else:
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

    if not full_queue:
        return {'success': False, 'message': '没有可导出的音频'}

    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_path = temp_file.name
    temp_file.close()

    try:
        success, result = cassie.export_from_queue(full_queue, temp_path, include_bell=cassie.enable_bell)
        if success:
            return static_file(os.path.basename(result), root=os.path.dirname(result), download='broadcast.mp3')
        else:
            return {'success': False, 'message': result}
    except Exception as e:
        traceback.print_exc()
        return {'success': False, 'message': str(e)}

if __name__ == '__main__':
    run(host='localhost', port=8080, debug=True)