import os
import json

def get_existing_files(folder_path, extension=".wav"):
    existing = []
    if os.path.exists(folder_path):
        for f in os.listdir(folder_path):
            if f.endswith(extension):
                existing.append(f)
    return existing

def main():
    with open("word_list.json", 'r', encoding='utf-8') as f:
        words_expected = set(json.load(f))
    with open("sound_list.json", 'r', encoding='utf-8') as f:
        sounds_expected = set(json.load(f))

    words_existing = get_existing_files("cassie/words/")
    sounds_existing = get_existing_files("cassie/sounds/")

    words_expected_set = set(words_expected)
    sounds_expected_set = set(sounds_expected)

    words_new = [f for f in words_existing if f[:-4] not in words_expected_set]
    sounds_new = [f for f in sounds_existing if f[:-4] not in sounds_expected_set]

    print("=" * 50)
    print("CASSIE 文件差异检测")
    print("=" * 50)

    print(f"\nwords文件夹新增文件 ({len(words_new)} 个):")
    if words_new:
        for f in sorted(words_new):
            print(f"  {f}")
    else:
        print("  无")

    print(f"\nsounds文件夹新增文件 ({len(sounds_new)} 个):")
    if sounds_new:
        for f in sorted(sounds_new):
            print(f"  {f}")
    else:
        print("  无")

if __name__ == "__main__":
    main()