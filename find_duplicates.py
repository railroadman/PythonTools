import os
import sys
import hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_file_size(path):
    try:
        return os.path.getsize(path)
    except:
        return -1

def md5(filepath, block_size=65536):
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(block_size), b""):
                hash_md5.update(chunk)
        return filepath, hash_md5.hexdigest()
    except:
        return filepath, None

def group_by_size(folder):
    size_map = defaultdict(list)
    for root, _, files in os.walk(folder):
        for name in files:
            full_path = os.path.join(root, name)
            size = get_file_size(full_path)
            if size >= 0:
                size_map[size].append(full_path)
    # Отфильтровываем только потенциальные дубликаты (одинаковый размер)
    return [files for files in size_map.values() if len(files) > 1]

def hash_groups(groups):
    hash_map = defaultdict(list)
    total_files = sum(len(g) for g in groups)
    done = 0

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = []
        for group in groups:
            for file in group:
                futures.append(executor.submit(md5, file))

        for future in as_completed(futures):
            done += 1
            if done % 10 == 0 or done == total_files:
                print(f"\rОбработка: {int((done / total_files) * 100)}% ({done}/{total_files})", end='', flush=True)
            filepath, filehash = future.result()
            if filehash:
                hash_map[filehash].append(filepath)

    print()
    return {k: v for k, v in hash_map.items() if len(v) > 1}

def save_result(duplicates, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        for group in duplicates.values():
            for file in group:
                f.write(file + "\n")
            f.write("================================\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python find_dupes.py <путь_к_папке> <файл_результата>")
        sys.exit(1)

    folder = sys.argv[1]
    output = sys.argv[2]

    print(f"Сканирование {folder}...")
    size_groups = group_by_size(folder)
    print(f"Найдено {len(size_groups)} групп одинакового размера.")

    duplicates = hash_groups(size_groups)
    save_result(duplicates, output)

    print(f"\nНайдено {len(duplicates)} групп дубликатов. Сохранено в {output}")
