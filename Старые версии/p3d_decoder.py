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

def decode_rad_ima_adpcm(data, channels, sample_rate, data_size):
    """
    Декодирование RAD IMA ADPCM согласно спецификации из p3d.c
    Структура: block_size = 0x14 байт на канал
    """
    # Проверяем входные данные
    if len(data) == 0 or channels == 0:
        return []
    
    # Размер блока фиксированный для RAD IMA
    BLOCK_SIZE = 0x14  # 20 байт
    SAMPLES_PER_BLOCK = 32  # 0x14 байт * 2 nibble/byte
    
    # Вычисляем количество полных блоков
    total_bytes = len(data)
    bytes_per_channel = total_bytes // channels
    blocks_per_channel = bytes_per_channel // BLOCK_SIZE
    
    print(f"Декодирование RAD IMA ADPCM:")
    print(f"  Каналы: {channels}")
    print(f"  Частота: {sample_rate} Гц")
    print(f"  Всего байт: {total_bytes}")
    print(f"  Байт на канал: {bytes_per_channel}")
    print(f"  Блоков на канал: {blocks_per_channel}")
    print(f"  Размер блока: 0x{BLOCK_SIZE:X} байт")
    print(f"  Сэмплов на блок: {SAMPLES_PER_BLOCK}")
    
    # Подготавливаем массивы для каждого канала
    channel_samples = [[] for _ in range(channels)]
    
    # Декодируем блок за блоком
    for block_idx in range(blocks_per_channel):
        for ch in range(channels):
            # Вычисляем позицию блока для этого канала
            block_start = block_idx * BLOCK_SIZE * channels + ch * BLOCK_SIZE
            
            if block_start + BLOCK_SIZE > len(data):
                continue
            
            # Извлекаем блок данных
            block_data = data[block_start:block_start + BLOCK_SIZE]
            
            # В RAD IMA первые 4 байта блока - заголовок
            # Формат заголовка: step_index (16bit), predictor (16bit)
            if len(block_data) >= 4:
                # Читаем как little-endian 16-bit значения
                header_val1 = struct.unpack('<H', block_data[0:2])[0]
                header_val2 = struct.unpack('<H', block_data[2:4])[0]
                
                # Определяем, что есть что (step_index должен быть 0-88)
                if 0 <= header_val1 <= 88:
                    step_index = header_val1
                    predictor = struct.unpack('<h', block_data[2:4])[0]
                elif 0 <= header_val2 <= 88:
                    step_index = header_val2
                    predictor = struct.unpack('<h', block_data[0:2])[0]
                else:
                    # По умолчанию (может быть только predictor)
                    predictor = struct.unpack('<h', block_data[0:2])[0]
                    step_index = 0
                
                # Защита от некорректных значений
                step_index = max(0, min(step_index, 88))
            else:
                # Если блок слишком короткий
                predictor = 0
                step_index = 0
            
            # Декодируем оставшиеся 16 байт блока (после 4-байтного заголовка)
            # Это дает 16 байт * 2 nibble/байт = 32 сэмпла на блок
            for i in range(4, BLOCK_SIZE):
                if i >= len(block_data):
                    break
                
                byte = block_data[i]
                
                # RAD IMA: low nibble first (0, затем 4)
                for shift in [0, 4]:
                    nibble = (byte >> shift) & 0xF
                    predictor, step_index = decode_ima_nibble(nibble, predictor, step_index)
                    channel_samples[ch].append(predictor)
    
    # Проверяем, что все каналы имеют данные
    if not any(channel_samples):
        print("Внимание: не удалось декодировать ни одного канала")
        return []
    
    # Находим минимальную длину среди каналов
    min_length = min(len(ch) for ch in channel_samples)
    
    if min_length == 0:
        print("Внимание: один из каналов пуст")
        return []
    
    # Интерливинг сэмплов для WAV формата
    interleaved = []
    for i in range(min_length):
        for ch in range(channels):
            interleaved.append(channel_samples[ch][i])
    
    print(f"  Декодировано: {min_length} сэмплов на канал")
    print(f"  Всего сэмплов: {len(interleaved)}")
    print(f"  Длительность: {min_length / sample_rate:.2f} секунд")
    
    return interleaved

def parse_p3d_file(data):
    """Парсинг P3D файла и извлечение параметров"""
    
    # Проверяем сигнатуру
    if len(data) < 12:
        return None
    
    magic = data[:4]
    if magic != b'P3D\xFF':
        print(f"Неверная сигнатура: {magic.hex()}")
        return None
    
    print("Найден P3D файл (little-endian)")
    
    # Ищем AudioFile секцию
    audiofile_pos = data.find(b'AudioFile')
    if audiofile_pos == -1:
        print("Не найдена секция AudioFile")
        return None
    
    print(f"Секция AudioFile на 0x{audiofile_pos:X}")
    
    # Ищем radp кодек
    radp_pos = data.find(b'radp')
    if radp_pos == -1:
        print("Не найден кодек 'radp'")
        return None
    
    print(f"Кодек 'radp' на 0x{radp_pos:X}")
    
    # Пропускаем "radp\0"
    pos = radp_pos + 5
    
    # Проверяем наличие "RADP" (опционально)
    if data[pos:pos+4] == b'RADP':
        pos += 4
    
    # Читаем заголовок RADP (16 байт)
    if pos + 16 > len(data):
        print("Недостаточно данных для заголовка RADP")
        return None
    
    # Структура: channels(4), sample_rate(4), unknown(4), data_size(4)
    channels = struct.unpack('<I', data[pos:pos+4])[0]
    sample_rate = struct.unpack('<I', data[pos+4:pos+8])[0]
    unknown = struct.unpack('<I', data[pos+8:pos+12])[0]
    data_size = struct.unpack('<I', data[pos+12:pos+16])[0]
    
    # Начало ADPCM данных
    adpcm_start = pos + 16
    adpcm_end = adpcm_start + data_size
    
    print(f"\nПараметры RAD IMA ADPCM:")
    print(f"  Каналы: {channels}")
    print(f"  Частота дискретизации: {sample_rate} Гц")
    print(f"  Неизвестное поле: 0x{unknown:X}")
    print(f"  Размер данных: 0x{data_size:X} байт")
    print(f"  Начало данных: 0x{adpcm_start:X}")
    print(f"  Конец данных: 0x{adpcm_end:X}")
    
    # Проверяем границы
    if adpcm_end > len(data):
        print(f"Внимание: data_size выходит за пределы файла")
        adpcm_end = len(data)
        data_size = adpcm_end - adpcm_start
        print(f"  Исправленный размер: 0x{data_size:X} байт")
    
    # Извлекаем ADPCM данные
    adpcm_data = data[adpcm_start:adpcm_end]
    
    return {
        'channels': channels,
        'sample_rate': sample_rate,
        'data_size': data_size,
        'adpcm_data': adpcm_data
    }

def decode_p3d_to_wav(input_file, output_file):
    """Основная функция декодирования P3D в WAV"""
    
    print(f"Обработка файла: {input_file}")
    print("=" * 60)
    
    # Читаем файл
    try:
        with open(input_file, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return False
    
    # Парсим P3D файл
    params = parse_p3d_file(data)
    if not params:
        print("Не удалось распарсить P3D файл")
        return False
    
    print("\n" + "=" * 60)
    
    # Декодируем ADPCM
    pcm_samples = decode_rad_ima_adpcm(
        params['adpcm_data'],
        params['channels'],
        params['sample_rate'],
        params['data_size']
    )
    
    if not pcm_samples:
        print("Не удалось декодировать аудио")
        return False
    
    print("\n" + "=" * 60)
    
    # Сохраняем в WAV
    print(f"Сохранение в WAV: {output_file}")
    
    try:
        # Создаем массив 16-битных сэмплов
        audio_array = array.array('h', pcm_samples)
        
        # Создаем WAV файл
        with wave.open(output_file, 'wb') as wav_file:
            wav_file.setnchannels(params['channels'])
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(params['sample_rate'])
            wav_file.writeframes(audio_array.tobytes())
        
        # Проверяем созданный файл
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"Файл успешно создан: {output_file}")
            print(f"Размер WAV файла: {file_size} байт")
            
            # Открываем и проверяем параметры
            with wave.open(output_file, 'rb') as wav_check:
                print(f"Параметры WAV файла:")
                print(f"  Каналы: {wav_check.getnchannels()}")
                print(f"  Ширина сэмпла: {wav_check.getsampwidth()} байт")
                print(f"  Частота: {wav_check.getframerate()} Гц")
                print(f"  Количество фреймов: {wav_check.getnframes()}")
                print(f"  Длительность: {wav_check.getnframes() / wav_check.getframerate():.2f} сек")
            
            return True
        else:
            print("Ошибка: WAV файл не был создан")
            return False
            
    except Exception as e:
        print(f"Ошибка сохранения WAV файла: {e}")
        
        # Пробуем сохранить как сырой PCM
        try:
            raw_file = output_file.replace('.wav', '.pcm')
            with open(raw_file, 'wb') as f:
                for sample in pcm_samples:
                    f.write(struct.pack('<h', sample))
            print(f"Сохранено как сырой PCM: {raw_file}")
            return True
        except Exception as e2:
            print(f"Ошибка сохранения PCM: {e2}")
            return False

def batch_decode_p3d(input_dir, output_dir):
    """Пакетное декодирование всех P3D файлов в папке"""
    if not os.path.exists(input_dir):
        print(f"Папка не существует: {input_dir}")
        return
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Ищем все P3D файлы
    p3d_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.p3d'):
                p3d_files.append(os.path.join(root, file))
    
    print(f"Найдено {len(p3d_files)} P3D файлов")
    
    # Декодируем каждый файл
    success_count = 0
    for i, p3d_file in enumerate(p3d_files):
        print(f"\n[{i+1}/{len(p3d_files)}] Обработка: {os.path.basename(p3d_file)}")
        
        output_file = os.path.join(
            output_dir, 
            os.path.splitext(os.path.basename(p3d_file))[0] + '.wav'
        )
        
        if decode_p3d_to_wav(p3d_file, output_file):
            success_count += 1
    
    print(f"\nГотово! Успешно декодировано: {success_count}/{len(p3d_files)} файлов")

def print_usage():
    """Вывод справки"""
    print("""
P3D (RAD IMA ADPCM) Декодер для Prototype 1/2
    
Использование:
    python p3d_decoder.py input.p3d output.wav
    python p3d_decoder.py batch input_folder output_folder
    
Примеры:
    python p3d_decoder.py sound.p3d sound.wav
    python p3d_decoder.py batch .\\sounds\\ .\\decoded\\
    
Описание:
    Декодирует P3D файлы из игр Prototype 1/2 в WAV формат.
    Поддерживает RAD IMA ADPCM кодек.
    """)

# Основная программа
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    # Режим пакетной обработки
    if sys.argv[1].lower() == 'batch':
        if len(sys.argv) < 4:
            print("Использование для пакетной обработки:")
            print("  python p3d_decoder.py batch input_folder output_folder")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3]
        batch_decode_p3d(input_dir, output_dir)
    
    # Режим одиночного файла
    else:
        if len(sys.argv) < 3:
            print("Использование:")
            print("  python p3d_decoder.py input.p3d output.wav")
            sys.exit(1)
        
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        
        # Проверяем расширение
        if not output_file.lower().endswith('.wav'):
            output_file += '.wav'
        
        success = decode_p3d_to_wav(input_file, output_file)
        
        if success:
            print("\n" + "=" * 60)
            print("Декодирование успешно завершено!")
            print(f"Файл сохранен как: {output_file}")
            
            # Предлагаем прослушать (если есть плеер)
            try:
                import platform
                system = platform.system()
                
                if system == 'Windows':
                    os.startfile(output_file)
                    print("Запуск медиаплеера...")
                elif system == 'Darwin':  # macOS
                    os.system(f'open "{output_file}"')
                    print("Открытие в медиаплеере...")
                elif system == 'Linux':
                    os.system(f'xdg-open "{output_file}"')
                    print("Открытие в медиаплеере...")
            except:
                pass  # Игнорируем ошибки открытия
        else:
            print("\n" + "=" * 60)
            print("Декодирование не удалось!")
            sys.exit(1)