import os

FOLDER = "тест_ALL_VARIANTS"

# Маркер, который мы НЕ трогаем
MARKER = bytes.fromhex("72 61 64 70 00 52 41 44 50")  # "radp\0RADP"

# Новый блок, который вставляем ПЕРЕД radp\0RADP
NEW_BLOCK = bytes.fromhex("""
50 33 44 FF 0C 00 00 00 24 94 00 00 00 00 00 FE 6D 01 00 00 6D 01 00 00 0A 00 00 00 15 00 00 00 41 75 64 69 6F 44 69 61 6C 6F 67 75 65 53 75 62 74 69 74 6C 65 00 01 00 00 00 0E 00 00 00 38 35 35 38 5F 6D 61 72 5F 61 5F 32 39 39 00 B4 A8 4E 4E A4 85 0A 22 D0 A5 49 73 01 07 00 00 00 73 70 61 6E 69 73 68 00 1E 00 00 00 C2 A1 44 69 73 70 65 72 73 61 6F 73 2C 20 6F 6A 6F 20 61 6C 20 64 69 73 70 61 72 61 72 21 00 BC 39 AB E3 07 F5 77 FE 01 07 00 00 00 69 74 61 6C 69 61 6E 00 1A 00 00 00 44 69 73 70 65 72 64 65 74 65 76 69 2C 20 6E 6F 6E 20 73 70 61 72 61 74 65 21 00 AE 31 91 EB 7B CC E1 9A 01 07 00 00 00 72 65 76 65 72 73 65 00 00 00 00 00 00 F8 CE 6B D8 00 3F 7B 22 01 06 00 00 00 66 72 65 6E 63 68 00 29 00 00 00 44 69 73 70 65 72 73 65 7A 2D 76 6F 75 73 C2 A0 21 20 56 C3 A9 72 69 66 69 65 7A 20 76 6F 73 20 63 69 62 6C 65 73 C2 A0 21 00 BC 8A 33 49 3C 49 07 09 01 07 00 00 00 65 6E 67 6C 69 73 68 00 38 00 00 00 D0 A0 D0 B0 D1 81 D1 81 D1 80 D0 B5 D0 B4 D0 BE D1 82 D0 BE D1 87 D0 B8 D1 82 D1 8C D1 81 D1 8F 2C 20 D0 BD D0 B5 20 D1 81 D1 82 D1 80 D0 B5 D0 BB D1 8F D1 82 D1 8C 21 00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 FE AB 92 00 00 AB 92 00 00 0A 00 00 00 09 00 00 00 41 75 64 69 6F 46 69 6C 65 00 02 00 00 00 0E 00 00 00 38 35 35 38 5F 6D 61 72 5F 61 5F 32 39 39 00 10 00 00 00 4B 45 59 3A 34 5C 65 5C 34 65 34 65 61 38 62 34 00 00 00 00 00 04 00 00 00
""")

patched = 0

for root, dirs, files in os.walk(FOLDER):
    for fname in files:
        path = os.path.join(root, fname)

        with open(path, "rb") as f:
            data = f.read()

        idx = data.find(MARKER)
        if idx == -1:
            continue  # нет radp -> не трогаем файл

        

        # Собираем новый файл:
        # [НОВЫЙ БЛОК] + [radp... и всё что дальше]
        new_data = NEW_BLOCK + data[idx:]

        with open(path, "wb") as f:
            f.write(new_data)

        print(f"[OK] Заменено ДО radp в: {path}")
        patched += 1

print(f"\nГотово. Изменено файлов: {patched}")
