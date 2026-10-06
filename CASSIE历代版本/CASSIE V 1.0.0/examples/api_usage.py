"""C.A.S.S.I.E. API 用法示例。

直接运行（进程内模式，不需要先启服务）：

    python examples/api_usage.py

只想离线合成、不发声：

    set SDL_AUDIODRIVER=dummy    # Windows
    python examples/api_usage.py

连到已经运行的 web 服务：

    python examples/api_usage.py --remote http://127.0.0.1:8080
"""
import argparse
import os
import sys

PROJECT_BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_BASE_PATH)

from cassie_api import CassieAPIError, CassieClient  # noqa: E402


def section(title):
    print()
    print('=' * 68)
    print(title)
    print('=' * 68)


def main():
    parser = argparse.ArgumentParser(description='C.A.S.S.I.E. API 用法示例')
    parser.add_argument('--remote', metavar='URL',
                        help='调用远程服务，例如 http://127.0.0.1:8080')
    parser.add_argument('--out', default='cassie_output', help='输出目录')
    parser.add_argument('--play', action='store_true', help='顺便真的播放一次')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    client = CassieClient.remote(args.remote) if args.remote \
        else CassieClient.local()

    mode = '远程 ' + args.remote if args.remote else '进程内'
    print('模式:', mode)

    with client:
        section('1. 运行状况')
        health = client.health()
        print('状态        :', health['status'])
        print('项目版本    :', health['project_version'], ' API:', health['api_version'])
        print('Python      :', health['python'], ' on', health['platform'])
        print('单词素材文件:', health['library']['word_files'])
        print('铃声素材文件:', health['library']['sound_files'])
        print('ffmpeg 可用 :', health['library']['ffmpeg_available'])
        print('正在播放    :', health['playing'])

        section('2. 素材库')
        words = client.words()
        sounds = client.sounds()
        print('可用单词 {} 个，前 12 个: {}'.format(len(words), ', '.join(words[:12])))
        print('可用铃声 {} 个，前 6 个 : {}'.format(len(sounds), ', '.join(sounds[:6])))

        section('3. 拼写检查')
        for text in ('attention , all personnel .', 'attention zzzznotaword .'):
            result = client.validate(text)
            print('{!r:42s} -> 缺失 {}'.format(text, result['not_found'] or '无'))

        section('4. 解析时间线（不合成）')
        # 混响会把每个单词的音频往后延长一段拖尾，时间线随之变长；
        # 想先看纯干声的排布，把 effects 关掉即可。
        dry = client.describe('mtf epsilon 11 . all personnel .', effects=False)
        print('--- 关闭空间效果（纯排布）---')
        print(dry['summary'])
        wet = client.describe('mtf epsilon 11 . all personnel .',
                              effects=True, decay_time=6.0, wet=0.4)
        print()
        print('--- 开启走廊混响 ---')
        print('总时长 {:.2f}s（干声排布 {:.2f}s，末尾多出的是拖尾）'.format(
            wet['plan']['duration_ms'] / 1000.0, dry['plan']['duration_ms'] / 1000.0))

        section('5. 参数化合成')
        jobs = [
            ('纯干声', 'attention , all personnel .', {'speed': -10}),
            ('默认空间效果', 'attention , all personnel .',
             {'speed': -10, 'effects': True}),
            ('走廊拉长', 'attention , all personnel .',
             {'speed': -10, 'effects': True, 'room_size': 2.0, 'decay_time': 9.0,
              'wet': 0.6, 'brightness': 0.7}),
            ('高音+快语速', 'warhead 90 start', {'speed': -16, 'pitch': 1.25}),
            ('故障效果', 'mobile task force unit epsilon 11 [error:3] .',
             {'speed': -10, 'effects': True, 'decay_time': 4.0, 'wet': 0.4}),
        ]
        for label, text, params in jobs:
            target = os.path.join(args.out, '{}.wav'.format(
                label.replace('+', '_').replace(' ', '_')))
            try:
                metadata = client.synthesize(text, target, **params)
                duration = CassieClient.duration_of(metadata['path'])
                print('{:<14s} {:>7.2f}s  {:>10,d} 字节  {}'.format(
                    label, duration, metadata['size_bytes'], os.path.basename(metadata['path'])))
            except CassieAPIError as error:
                print('{:<14s} 失败: {} ({})'.format(label, error, error.code))

        section('6. 直接拿字节流')
        data = client.synthesize_bytes('all remaining personnel .')
        print('WAV 头部:', data[:4], ' 共 {} 字节'.format(len(data)))

        section('7. 预设管理')
        client.save_preset('示例-走廊广播', 'attention , all personnel .')
        print('已保存预设，当前共 {} 个: {}'.format(
            len(client.presets()), ', '.join(client.presets())))
        print('读取内容:', repr(client.preset('示例-走廊广播')))
        client.delete_preset('示例-走廊广播')
        print('已删除，剩余 {} 个'.format(len(client.presets())))

        section('8. 服务端默认参数')
        print('当前混响时长:', client.settings()['reverb_decay_time'])
        client.update_settings(reverb_decay_time=7.0)
        print('改后混响时长:', client.settings()['reverb_decay_time'])
        client.update_settings(reset=True)
        print('复位后      :', client.settings()['reverb_decay_time'])

        section('9. 播放控制')
        if args.play:
            client.play('mtf epsilon 11 .', speed=-8)
            print('播放中:', client.status()['playing'])
            finished = client.wait_until_done(timeout=60)
            print('播放结束:', finished)
        else:
            print('未加 --play，跳过实际播放。')
            print('用法: client.play("mtf epsilon 11"); client.wait_until_done(); client.stop()')

        section('完成')
        print('输出目录:', os.path.abspath(args.out))


if __name__ == '__main__':
    main()
