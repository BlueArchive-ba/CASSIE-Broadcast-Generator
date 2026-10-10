import os
import json

PROJECT_BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def extract_filenames(folder_path, extension=".wav"):
    if not os.path.exists(folder_path):
        return []
    files = []
    for f in os.listdir(folder_path):
        if f.endswith(extension):
            files.append(f[:-len(extension)])
    files.sort()
    return files

def main():
    words_path = os.path.join(PROJECT_BASE_PATH, "cassie", "words")
    sounds_path = os.path.join(PROJECT_BASE_PATH, "cassie", "sounds")
    extension = ".wav"

    word_list = extract_filenames(words_path, extension)
    sound_list = extract_filenames(sounds_path, extension)

    with open(os.path.join(PROJECT_BASE_PATH, "word_list.json"), "w", encoding="utf-8") as f:
        json.dump(word_list, f, ensure_ascii=False, indent=2)

    with open(os.path.join(PROJECT_BASE_PATH, "sound_list.json"), "w", encoding="utf-8") as f:
        json.dump(sound_list, f, ensure_ascii=False, indent=2)

    print(f"word_list.json 已生成，共 {len(word_list)} 个单词音频")
    print(f"sound_list.json 已生成，共 {len(sound_list)} 个铃声音频")

if __name__ == "__main__":
    main()