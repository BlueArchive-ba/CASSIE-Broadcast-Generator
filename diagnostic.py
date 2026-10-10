import os
import json

def main():
    print("必要文件检测:")

    print("\n__pycache__:")
    if os.path.exists("__pycache__"):
        pycache_files = os.listdir("__pycache__")
        if len(pycache_files) == 2 and all(f.endswith(".pyc") for f in pycache_files):
            print("  存在，内容正确")
        else:
            print("  存在，内容不正确")
    else:
        print("  不存在")

    print("\n.vscode:")
    if os.path.exists(".vscode"):
        vscode_files = os.listdir(".vscode")
        if len(vscode_files) == 1 and "settings.json" in vscode_files:
            print("  存在，内容正确")
        else:
            print("  存在，内容不正确")
    else:
        print("  不存在")

    print("\ncassie:")
    if os.path.exists("cassie"):
        cassie_dirs = [d for d in os.listdir("cassie") if os.path.isdir(os.path.join("cassie", d))]
        if len(cassie_dirs) == 2 and "sounds" in cassie_dirs and "words" in cassie_dirs:
            print("  存在，内容正确")
        else:
            print("  存在，内容不正确")
    else:
        print("  不存在")

    print("\nstatic:")
    if os.path.exists("static"):
        static_files = os.listdir("static")
        if len(static_files) == 1 and "style.css" in static_files:
            print("  存在，内容正确")
        else:
            print("  存在，内容不正确")
    else:
        print("  不存在")

    print("\npresets.json:")
    if os.path.exists("presets.json"):
        print("  存在")
    else:
        print("  不存在")

    print("\ncassie_play.py:")
    if os.path.exists("cassie_play.py"):
        print("  存在")
    else:
        print("  不存在")

    print("\n" + "=" * 40 + "\n")

    if not os.path.exists("word_list.json") or not os.path.exists("sound_list.json"):
        print("word_list.json 或 sound_list.json 不存在，跳过音频检测")
        return

    with open("word_list.json", 'r', encoding='utf-8') as f:
        words_expected = set(json.load(f))
    with open("sound_list.json", 'r', encoding='utf-8') as f:
        sounds_expected = set(json.load(f))

    words_existing = set()
    if os.path.exists("cassie/words/"):
        for f in os.listdir("cassie/words/"):
            if f.endswith(".wav"):
                words_existing.add(f[:-4])

    sounds_existing = set()
    if os.path.exists("cassie/sounds/"):
        for f in os.listdir("cassie/sounds/"):
            if f.endswith(".wav"):
                sounds_existing.add(f[:-4])

    words_missing = words_expected - words_existing
    sounds_missing = sounds_expected - sounds_existing
    words_wrong_place = words_expected & sounds_existing
    sounds_wrong_place = sounds_expected & words_existing

    print("检测完毕")
    print(f"总文件数量: {len(words_expected) + len(sounds_expected)}")
    print(f"words文件夹文件数量: {len(words_expected)}")
    print(f"sounds文件夹文件数量: {len(sounds_expected)}")
    print(f"未检测到文件总数: {len(words_missing) + len(sounds_missing)}")
    print(f"words文件夹缺失: {len(words_missing)}")
    print(f"sounds文件夹缺失: {len(sounds_missing)}")

    if words_missing or sounds_missing:
        if words_missing:
            print("\nwords文件夹缺失:")
            for w in sorted(words_missing):
                print(f"  {w}.wav")
        if sounds_missing:
            print("sounds文件夹缺失:")
            for s in sorted(sounds_missing):
                print(f"  {s}.wav")

    if words_wrong_place or sounds_wrong_place:
        print("\n文件错位:")
        if words_wrong_place:
            print("应在words文件夹但出现在sounds文件夹:")
            for w in sorted(words_wrong_place):
                print(f"  {w}.wav")
        if sounds_wrong_place:
            print("应在sounds文件夹但出现在words文件夹:")
            for s in sorted(sounds_wrong_place):
                print(f"  {s}.wav")

    errors = words_missing or sounds_missing or words_wrong_place or sounds_wrong_place
    if errors:
        print("\n检测未通过")
    else:
        print("\n检测通过")

if __name__ == "__main__":
    main()