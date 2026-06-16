import struct
import sys
import array
import wave
import os

# Таблицы для IMA ADPCM
IMA_STEP_TABLE = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
    157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544,
    598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707,
    1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871,
    5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635,
    13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
]

IMA_INDEX_TABLE = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]

def clamp16(value):
    return max(-32768, min(32767, value))

def decode_ima_nibble(nibble, predictor, step_index):
    """Декодирование одного nibble IMA ADPCM"""
    step = IMA_STEP_TABLE[step_index]
    
    delta = step >> 3
    if nibble & 1:
        delta += step >> 2
    if nibble & 2:
        delta += step >> 1
    if nibble & 4:
        delta += step
    if nibble & 8:
        delta = -delta
    
    predictor += delta
    predictor = clamp16(predictor)
    
    step_index += IMA_INDEX_TABLE[nibble & 0x7]
    if step_index < 0:
        step_index = 0
    elif step_index > 88:
        step_index = 88
    
    return predictor, step_index

def decode_radp_file(radp_file, output_wav=None):
    """
    Декодирование файла .radp в WAV
    Формат: 
      "radp\0RADP" (9 байт)
      channels (4 байта, uint32 LE)
      sample_rate (4 байта, uint32 LE)
      unknown (4 байта, uint32 LE) - обычно 0x0F или 0x1B
      data_size (4 байта, uint32 LE)
      adpcm_data (data_size байт)
    """
    
    print(f"Обработка файла RADP: {radp_file}")
    print("=" * 50)
    
    # Читаем файл
    try:
        with open(radp_file, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return False
    
    print(f"Размер файла: {len(data)} байт")
    
    # Проверяем сигнатуру
    if not data.startswith(b'radp\0RADP'):
        print("Ошибка: неверная сигнатура RADP файла")
        print(f"Первые 9 байт: {data[:9].hex()}")
        return False
    
    print("✓ Сигнатура 'radp\\0RADP' подтверждена")
    
    # Пропускаем сигнатуру (9 байт)
    pos = 9
    
    if len(data) < pos + 16:
        print("Ошибка: файл слишком мал для заголовка")
        return False
    
    # Читаем заголовок
    channels = struct.unpack('<I', data[pos:pos+4])[0]
    sample_rate = struct.unpack('<I', data[pos+4:pos+8])[0]
    unknown = struct.unpack('<I', data[pos+8:pos+12])[0]
    data_size = struct.unpack('<I', data[pos+12:pos+16])[0]
    
    print(f"\nЗаголовок RADP:")
    print(f"  Каналы: {channels}")
    print(f"  Частота дискретизации: {sample_rate} Гц")
    print(f"  Неизвестное поле: 0x{unknown:X}")
    print(f"  Размер ADPCM данных: {data_size} байт")
    
    # Начало ADPCM данных
    adpcm_start = pos + 16
    adpcm_end = adpcm_start + data_size
    
    print(f"  Начало данных: байт {adpcm_start}")
    print(f"  Конец данных: байт {adpcm_end}")
    
    if adpcm_end > len(data):
        print(f"Внимание: data_size выходит за пределы файла")
        print(f"  Ожидалось: {data_size} байт")
        print(f"  Доступно: {len(data) - adpcm_start} байт")
        data_size = len(data) - adpcm_start
        adpcm_end = adpcm_start + data_size
    
    # Извлекаем ADPCM данные
    adpcm_data = data[adpcm_start:adpcm_end]
    
    print(f"\nФактически прочитано ADPCM данных: {len(adpcm_data)} байт")
    
    # RAD IMA ADPCM параметры
    BLOCK_SIZE = 0x14  # 20 байт на блок на канал
    SAMPLES_PER_BLOCK = 32  # 32 сэмпла на блок
    
    # Проверяем структуру
    if channels == 0:
        print("Ошибка: channels = 0")
        return False
    
    bytes_per_channel = len(adpcm_data) // channels
    blocks_per_channel = bytes_per_channel // BLOCK_SIZE
    
    print(f"\nСтруктура ADPCM:")
    print(f"  Размер блока: {BLOCK_SIZE} байт")
    print(f"  Байт на канал: {bytes_per_channel}")
    print(f"  Блоков на канал: {blocks_per_channel}")
    print(f"  Сэмплов на блок: {SAMPLES_PER_BLOCK}")
    print(f"  Всего сэмплов на канал: {blocks_per_channel * SAMPLES_PER_BLOCK}")
    
    # Декодируем каждый канал
    all_samples = [[] for _ in range(channels)]
    
    for ch in range(channels):
        print(f"\nДекодирование канала {ch+1}/{channels}...")
        
        for block_idx in range(blocks_per_channel):
            # Начало блока для этого канала
            block_start = block_idx * BLOCK_SIZE * channels + ch * BLOCK_SIZE
            
            if block_start + BLOCK_SIZE > len(adpcm_data):
                break
            
            # Извлекаем блок
            block_data = adpcm_data[block_start:block_start + BLOCK_SIZE]
            
            # Читаем заголовок блока (первые 4 байта)
            if len(block_data) >= 4:
                # Пробуем определить формат заголовка
                val1 = struct.unpack('<H', block_data[0:2])[0]
                val2 = struct.unpack('<H', block_data[2:4])[0]
                
                # Определяем predictor и step_index
                if 0 <= val1 <= 88:
                    step_index = val1
                    predictor = struct.unpack('<h', block_data[2:4])[0]
                elif 0 <= val2 <= 88:
                    step_index = val2
                    predictor = struct.unpack('<h', block_data[0:2])[0]
                else:
                    # Возможно оба значения - predictor (одинаковые)
                    predictor = struct.unpack('<h', block_data[0:2])[0]
                    step_index = 0
                
                step_index = max(0, min(step_index, 88))
            else:
                predictor = 0
                step_index = 0
            
            # Декодируем оставшиеся 16 байт блока (32 nibble = 32 сэмпла)
            for i in range(4, BLOCK_SIZE):
                if i >= len(block_data):
                    break
                
                byte = block_data[i]
                
                # Два nibble в каждом байте: low nibble first
                for shift in [0, 4]:
                    nibble = (byte >> shift) & 0xF
                    predictor, step_index = decode_ima_nibble(nibble, predictor, step_index)
                    all_samples[ch].append(predictor)
        
        print(f"  Декодировано сэмплов: {len(all_samples[ch])}")
    
    # Проверяем, что все каналы имеют данные
    if not any(all_samples):
        print("Ошибка: не удалось декодировать ни одного канала")
        return False
    
    # Находим минимальную длину
    min_length = min(len(ch) for ch in all_samples if ch)
    
    if min_length == 0:
        print("Ошибка: один из каналов пуст")
        return False
    
    # Интерливинг для WAV
    interleaved_samples = []
    for i in range(min_length):
        for ch in range(channels):
            interleaved_samples.append(all_samples[ch][i])
    
    print(f"\nИтог декодирования:")
    print(f"  Сэмплов на канал: {min_length}")
    print(f"  Всего сэмплов: {len(interleaved_samples)}")
    print(f"  Длительность: {min_length / sample_rate:.2f} сек")
    
    # Определяем имя выходного файла
    if output_wav is None:
        base_name = os.path.splitext(radp_file)[0]
        output_wav = f"{base_name}.wav"
    
    # Сохраняем в WAV
    print(f"\nСохранение в WAV: {output_wav}")
    
    try:
        audio_array = array.array('h', interleaved_samples)
        
        with wave.open(output_wav, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_array.tobytes())
        
        # Проверяем результат
        if os.path.exists(output_wav):
            file_size = os.path.getsize(output_wav)
            print(f"✓ Файл успешно создан")
            print(f"  Размер WAV: {file_size} байт")
            print(f"  Длительность: {min_length / sample_rate:.2f} сек")
            
            # Открываем для проверки
            with wave.open(output_wav, 'rb') as wav_check:
                print(f"\nПроверка WAV файла:")
                print(f"  Каналы: {wav_check.getnchannels()}")
                print(f"  Частота: {wav_check.getframerate()} Гц")
                print(f"  Сэмплов: {wav_check.getnframes()}")
            
            return True
        else:
            print("✗ Ошибка: WAV файл не был создан")
            return False
            
    except Exception as e:
        print(f"✗ Ошибка сохранения WAV: {e}")
        
        # Пробуем сохранить как сырой PCM
        try:
            raw_file = output_wav.replace('.wav', '.raw')
            with open(raw_file, 'wb') as f:
                for sample in interleaved_samples:
                    f.write(struct.pack('<h', sample))
            print(f"✓ Сохранено как сырой PCM: {raw_file}")
            print(f"  Размер: {len(interleaved_samples) * 2} байт")
            return True
        except Exception as e2:
            print(f"✗ Ошибка сохранения PCM: {e2}")
            return False

def batch_decode_radp(input_dir, output_dir=None):
    """Пакетное декодирование всех .radp файлов в папке"""
    
    if not os.path.exists(input_dir):
        print(f"Папка не существует: {input_dir}")
        return
    
    if output_dir is None:
        output_dir = os.path.join(input_dir, "decoded")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Ищем все .radp файлы
    radp_files = []
    for file in os.listdir(input_dir):
        if file.lower().endswith('.radp'):
            radp_files.append(os.path.join(input_dir, file))
    
    print(f"Найдено {len(radp_files)} RADP файлов")
    print("=" * 50)
    
    # Декодируем каждый файл
    success_count = 0
    for i, radp_file in enumerate(radp_files):
        filename = os.path.basename(radp_file)
        print(f"\n[{i+1}/{len(radp_files)}] {filename}")
        
        output_wav = os.path.join(output_dir, filename.replace('.radp', '.wav'))
        
        if decode_radp_file(radp_file, output_wav):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"Готово! Успешно декодировано: {success_count}/{len(radp_files)}")
    print(f"WAV файлы сохранены в: {output_dir}")

def print_file_info(radp_file):
    """Вывод информации о RADP файле"""
    try:
        with open(radp_file, 'rb') as f:
            data = f.read()
    except:
        print(f"Не удалось прочитать файл: {radp_file}")
        return
    
    print(f"Файл: {radp_file}")
    print(f"Размер: {len(data)} байт")
    
    if not data.startswith(b'radp\0RADP'):
        print("Не является RADP файлом")
        return
    
    pos = 9
    if len(data) >= pos + 16:
        channels = struct.unpack('<I', data[pos:pos+4])[0]
        sample_rate = struct.unpack('<I', data[pos+4:pos+8])[0]
        unknown = struct.unpack('<I', data[pos+8:pos+12])[0]
        data_size = struct.unpack('<I', data[pos+12:pos+16])[0]
        
        print(f"\nЗаголовок:")
        print(f"  Каналы: {channels}")
        print(f"  Частота: {sample_rate} Гц")
        print(f"  Unknown: 0x{unknown:X}")
        print(f"  Размер ADPCM: {data_size} байт")
        
        # Быстрый расчет длительности
        if sample_rate > 0 and channels > 0:
            blocks = data_size // (0x14 * channels)
            samples = blocks * 32
            duration = samples / sample_rate
            print(f"  Расчетная длительность: {duration:.2f} сек")
    
    # Hex дамп начала
    print(f"\nПервые 64 байта:")
    for i in range(0, min(64, len(data)), 16):
        line = f"  {i:04X}: "
        hex_part = ""
        ascii_part = ""
        
        for j in range(16):
            if i + j < len(data):
                byte = data[i + j]
                hex_part += f"{byte:02X} "
                ascii_part += chr(byte) if 32 <= byte < 127 else '.'
            else:
                hex_part += "   "
                ascii_part += " "
        
        print(f"{line}{hex_part.ljust(48)} |{ascii_part}|")

def main():
    """Главная функция"""
    
    if len(sys.argv) < 2:
        print("""
RADP (RAD IMA ADPCM) Декодер для Prototype 1/2
        
Использование:
    python radp_decoder.py decode input.radp [output.wav]
    python radp_decoder.py batch input_folder [output_folder]
    python radp_decoder.py info file.radp
        
Примеры:
    # Декодирование одного файла
    python radp_decoder.py decode sound.radp sound.wav
    
    # Пакетное декодирование
    python radp_decoder.py batch .\\sounds\\ .\\decoded\\
    
    # Информация о файле
    python radp_decoder.py info sound.radp
    
    # Декодирование с автоименованием
    python radp_decoder.py decode sound.radp
        """)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "decode":
        if len(sys.argv) < 3:
            print("Использование: python radp_decoder.py decode input.radp [output.wav]")
            sys.exit(1)
        
        radp_file = sys.argv[2]
        output_wav = sys.argv[3] if len(sys.argv) > 3 else None
        
        if not os.path.exists(radp_file):
            print(f"Файл не найден: {radp_file}")
            sys.exit(1)
        
        success = decode_radp_file(radp_file, output_wav)
        
        if not success:
            sys.exit(1)
    
    elif command == "batch":
        if len(sys.argv) < 3:
            print("Использование: python radp_decoder.py batch input_folder [output_folder]")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None
        
        batch_decode_radp(input_dir, output_dir)
    
    elif command == "info":
        if len(sys.argv) < 3:
            print("Использование: python radp_decoder.py info file.radp")
            sys.exit(1)
        
        radp_file = sys.argv[2]
        
        if not os.path.exists(radp_file):
            print(f"Файл не найден: {radp_file}")
            sys.exit(1)
        
        print_file_info(radp_file)
    
    else:
        print(f"Неизвестная команда: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()