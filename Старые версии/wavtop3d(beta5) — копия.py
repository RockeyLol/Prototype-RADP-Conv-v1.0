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

def encode_ima_nibble(sample, predictor, step_index):
    """Кодирование одного сэмпла в nibble IMA ADPCM (используется в Prototype)"""
    step = IMA_STEP_TABLE[step_index]
    
    diff = sample - predictor
    sign = 1 if diff < 0 else 0
    diff = abs(diff)
    
    delta = step >> 3
    code = 0
    
    if diff >= step:
        code = 7
        delta += step
    elif diff >= (step >> 1) + (step >> 2) + (step >> 3):
        code = 6
        delta += (step >> 1) + (step >> 2) + (step >> 3)
    elif diff >= (step >> 1) + (step >> 2):
        code = 5
        delta += (step >> 1) + (step >> 2)
    elif diff >= (step >> 1) + (step >> 3):
        code = 4
        delta += (step >> 1) + (step >> 3)
    elif diff >= (step >> 1):
        code = 3
        delta += step >> 1
    elif diff >= (step >> 2) + (step >> 3):
        code = 2
        delta += (step >> 2) + (step >> 3)
    elif diff >= (step >> 2):
        code = 1
        delta += step >> 2
    else:
        code = 0
    
    if sign:
        delta = -delta
        code |= 8
    
    new_predictor = predictor + delta
    new_predictor = clamp16(new_predictor)
    
    new_step_index = step_index + IMA_INDEX_TABLE[code & 0x7]
    new_step_index = max(0, min(new_step_index, 88))
    
    return code, new_predictor, new_step_index

def read_wav_file(wav_file):
    """Чтение WAV файла"""
    try:
        with wave.open(wav_file, 'rb') as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sampwidth = wav.getsampwidth()
            nframes = wav.getnframes()
            
            print(f"Чтение WAV: {wav_file}")
            print(f"  Каналы: {channels}")
            print(f"  Частота: {sample_rate} Гц")
            print(f"  Битность: {sampwidth * 8} бит")
            print(f"  Сэмплов: {nframes}")
            print(f"  Длительность: {nframes / sample_rate:.2f} сек")
            
            raw_data = wav.readframes(nframes)
            
            if sampwidth == 2:
                samples = struct.unpack(f'<{len(raw_data)//2}h', raw_data)
            elif sampwidth == 1:
                samples = [(b - 128) * 256 for b in raw_data]
            else:
                print(f"Неподдерживаемая ширина сэмпла: {sampwidth} байт")
                return None
            
            return {
                'channels': channels,
                'sample_rate': sample_rate,
                'samples': samples,
                'nframes': nframes
            }
            
    except Exception as e:
        print(f"Ошибка чтения WAV: {e}")
        return None

def encode_rad_ima_adpcm(wav_data):
    """Кодирование в RAD IMA ADPCM (формат Prototype)"""
    channels = wav_data['channels']
    samples = wav_data['samples']
    
    # Разделяем сэмплы по каналам
    channel_samples = []
    for ch in range(channels):
        channel_samples.append(samples[ch::channels])
    
    BLOCK_SIZE = 0x14  # 20 байт
    SAMPLES_PER_BLOCK = 32
    
    # Вычисляем количество блоков
    samples_per_channel = len(channel_samples[0])
    blocks_per_channel = (samples_per_channel + SAMPLES_PER_BLOCK - 1) // SAMPLES_PER_BLOCK
    
    # Подготавливаем данные для каждого канала
    encoded_channels = []
    
    for ch in range(channels):
        channel_data = bytearray()
        ch_samples = channel_samples[ch]
        
        for block_idx in range(blocks_per_channel):
            start_sample = block_idx * SAMPLES_PER_BLOCK
            end_sample = min(start_sample + SAMPLES_PER_BLOCK, samples_per_channel)
            block_samples = ch_samples[start_sample:end_sample]
            
            # Заполняем блок последним сэмплом
            if len(block_samples) < SAMPLES_PER_BLOCK:
                last_val = block_samples[-1] if block_samples else 0
                block_samples = list(block_samples) + [last_val] * (SAMPLES_PER_BLOCK - len(block_samples))
            
            # В Prototype: шаг (step_index) идет ПЕРВЫМ (2 байта), затем predictor (2 байта)
            # Инициализируем новый блок
            if block_idx == 0:
                predictor = block_samples[0]
                step_index = 0
            else:
                # Используем значения из предыдущего блока
                predictor = last_predictor
                step_index = last_step_index
            
            # Заголовок блока: step_index (uint16), predictor (int16)
            header = struct.pack('<Hh', step_index, predictor)
            channel_data.extend(header)
            
            # Кодируем 32 сэмпла
            nibbles = []
            for sample in block_samples:
                nibble, predictor, step_index = encode_ima_nibble(sample, predictor, step_index)
                nibbles.append(nibble)
            
            # Сохраняем для следующего блока
            last_predictor = predictor
            last_step_index = step_index
            
            # Упаковываем nibbles в байты (low nibble first)
            for i in range(0, len(nibbles), 2):
                if i + 1 < len(nibbles):
                    # LOW nibble first (как в оригинале)
                    byte = nibbles[i] | (nibbles[i+1] << 4)
                else:
                    byte = nibbles[i]
                channel_data.append(byte)
        
        # Убеждаемся, что размер правильный
        expected_size = blocks_per_channel * BLOCK_SIZE
        if len(channel_data) < expected_size:
            channel_data.extend(b'\x00' * (expected_size - len(channel_data)))
        
        encoded_channels.append(bytes(channel_data))
    
    # Интерливинг блоков (блок канала 1, блок канала 2, ...)
    adpcm_data = bytearray()
    for block_idx in range(blocks_per_channel):
        for ch in range(channels):
            start_pos = block_idx * BLOCK_SIZE
            end_pos = start_pos + BLOCK_SIZE
            adpcm_data.extend(encoded_channels[ch][start_pos:end_pos])
    
    return bytes(adpcm_data)

def create_exact_p3d(wav_file, output_p3d, original_p3d_template=None):
    """Создание точного P3D файла (копирует структуру оригинального)"""
    
    print("=" * 70)
    print("СОЗДАНИЕ ТОЧНОГО P3D ФАЙЛА ДЛЯ PROTOTYPE")
    print("=" * 70)
    
    # 1. Читаем WAV
    wav_data = read_wav_file(wav_file)
    if not wav_data:
        return False
    
    channels = wav_data['channels']
    sample_rate = wav_data['sample_rate']
    
    # 2. Кодируем в ADPCM
    print(f"\nКодирование в RAD IMA ADPCM...")
    adpcm_data = encode_rad_ima_adpcm(wav_data)
    
    if not adpcm_data:
        print("Ошибка кодирования")
        return False
    
    print(f"  Закодировано: {len(adpcm_data)} байт ADPCM данных")
    
    # 3. Создаем P3D структуру
    print(f"\nСоздание структуры P3D...")
    
    # Анализируем оригинальный шаблон, если он есть
    if original_p3d_template and os.path.exists(original_p3d_template):
        print(f"Использую шаблон: {original_p3d_template}")
        with open(original_p3d_template, 'rb') as f:
            template = f.read()
        
        # Находим RADP секцию
        radp_pos = template.find(b'radp')
        if radp_pos != -1:
            pos = radp_pos + 5
            if template[pos:pos+4] == b'RADP':
                pos += 4
            
            # Читаем параметры из шаблона
            template_channels = struct.unpack('<I', template[pos:pos+4])[0]
            template_sample_rate = struct.unpack('<I', template[pos+4:pos+8])[0]
            unknown_field = struct.unpack('<I', template[pos+8:pos+12])[0]  # Обычно 0x18 или 0x0F
            
            print(f"  Параметры из шаблона:")
            print(f"    Каналы: {template_channels}")
            print(f"    Частота: {template_sample_rate}")
            print(f"    Unknown поле: 0x{unknown_field:X}")
            
            # Используем параметры из шаблона
            if channels != template_channels:
                print(f"  ВНИМАНИЕ: Количество каналов не совпадает!")
                print(f"    WAV: {channels}, Шаблон: {template_channels}")
            
            sample_rate = template_sample_rate
            use_unknown_field = unknown_field
        else:
            use_unknown_field = 0x18  # По умолчанию для Prototype
    else:
        use_unknown_field = 0x18  # По умолчанию для Prototype
    
    # 4. Строим P3D с нуля, копируя точную структуру из HEX-дампа
    p3d = bytearray()
    
    # --- Заголовок P3D ---
    # P3D сигнатура
    p3d.extend(b'P3D\xFF')
    
    # Размер файла (пока 0, заполним позже)
    file_size_pos = len(p3d)
    p3d.extend(b'\x00\x00\x00\x00')
    
    # Неизвестное поле (0x0C)
    p3d.extend(b'\x0C\x00\x00\x00')
    
    # Размер до AudioFile? (0xC0 0F 00 00 = 4032 байт)
    # В оригинале: C0 0F 00 00
    # Вычисляем: header (12) + до AudioFile
    audiofile_start = 12 + 4  # После этого поля
    p3d.extend(struct.pack('<I', audiofile_start))
    
    # --- AudioFile секция ---
    # Маркер секции
    p3d.extend(b'\x00\x00\x00\xFE')
    
    # Размер секции (пока 0, заполним позже)
    section_size1_pos = len(p3d)
    p3d.extend(b'\x00\x00\x00\x00')
    section_size2_pos = len(p3d)
    p3d.extend(b'\x00\x00\x00\x00')
    
    # AudioFile заголовок
    p3d.extend(b'\x0A\x00\x00\x00')  # Длина имени типа
    p3d.extend(b'\x09\x00\x00\x00')  # Длина строки
    p3d.extend(b'AudioFile\x00')     # Имя типа
    
    # Имена (2 имени)
    p3d.extend(b'\x02\x00\x00\x00')  # Количество имен
    
    # Первое имя (15 байт)
    p3d.extend(b'\x0F\x00\x00\x00')  # Длина
    p3d.extend(b'11271_maoff_142\x00')
    
    # Второе имя (16 байт)
    p3d.extend(b'\x10\x00\x00\x00')  # Длина
    p3d.extend(b'KEY:f\\3\\f35c7b78\x00')
    
    # Тип (0)
    p3d.extend(b'\x00\x00\x00\x00')
    
    # Кодек
    p3d.extend(b'\x04\x00\x00\x00')  # Длина
    p3d.extend(b'radp\x00')
    
    # --- RADP секция ---
    p3d.extend(b'RADP')
    
    # Заголовок RADP
    p3d.extend(struct.pack('<I', channels))      # Каналы
    p3d.extend(struct.pack('<I', sample_rate))   # Частота
    p3d.extend(struct.pack('<I', use_unknown_field))  # Unknown поле (0x18)
    p3d.extend(struct.pack('<I', len(adpcm_data)))    # Размер ADPCM данных
    
    # ADPCM данные
    p3d.extend(adpcm_data)
    
    # 5. Заполняем размеры
    file_size = len(p3d)
    p3d[file_size_pos:file_size_pos+4] = struct.pack('<I', file_size)
    
    # Размер секции AudioFile
    section_start = file_size_pos + 4  # После размера файла
    section_size = file_size - section_start
    p3d[section_size1_pos:section_size1_pos+4] = struct.pack('<I', section_size)
    p3d[section_size2_pos:section_size2_pos+4] = struct.pack('<I', section_size)
    
    # 6. Сохраняем файл
    try:
        with open(output_p3d, 'wb') as f:
            f.write(p3d)
        
        print(f"\n✓ P3D файл создан: {output_p3d}")
        print(f"  Размер файла: {file_size} байт")
        print(f"  ADPCM данных: {len(adpcm_data)} байт")
        print(f"  Unknown поле: 0x{use_unknown_field:X}")
        
        # Проверяем структуру
        print(f"\nПроверка структуры:")
        print(f"  Сигнатура: {p3d[:4].hex()}")
        print(f"  Размер файла: {struct.unpack('<I', p3d[4:8])[0]} байт")
        print(f"  Поле после сигнатуры: 0x{struct.unpack('<I', p3d[8:12])[0]:X}")
        print(f"  Поле до AudioFile: 0x{struct.unpack('<I', p3d[12:16])[0]:X}")
        
        # Проверяем RADP заголовок
        radp_pos = p3d.find(b'RADP')
        if radp_pos != -1:
            print(f"\nRADP заголовок:")
            print(f"  Каналы: {struct.unpack('<I', p3d[radp_pos+4:radp_pos+8])[0]}")
            print(f"  Частота: {struct.unpack('<I', p3d[radp_pos+8:radp_pos+12])[0]} Гц")
            print(f"  Unknown: 0x{struct.unpack('<I', p3d[radp_pos+12:radp_pos+16])[0]:X}")
            print(f"  Размер ADPCM: {struct.unpack('<I', p3d[radp_pos+16:radp_pos+20])[0]} байт")
        
        return True
        
    except Exception as e:
        print(f"✗ Ошибка сохранения P3D: {e}")
        return False

def batch_encode_p3d(input_dir, output_dir, template_p3d=None):
    """Пакетное кодирование WAV в P3D"""
    if not os.path.exists(input_dir):
        print(f"Папка не существует: {input_dir}")
        return
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Ищем все WAV файлы
    wav_files = []
    for file in os.listdir(input_dir):
        if file.lower().endswith('.wav'):
            wav_files.append(os.path.join(input_dir, file))
    
    print(f"Найдено {len(wav_files)} WAV файлов")
    
    success_count = 0
    for wav_file in wav_files:
        print(f"\nОбработка: {os.path.basename(wav_file)}")
        
        output_p3d = os.path.join(
            output_dir,
            os.path.splitext(os.path.basename(wav_file))[0] + '.p3d'
        )
        
        if create_exact_p3d(wav_file, output_p3d, template_p3d):
            success_count += 1
    
    print(f"\nГотово! Успешно создано: {success_count}/{len(wav_files)} P3D файлов")

def main():
    """Главная функция"""
    
    if len(sys.argv) < 3:
        print("""
ТОЧНЫЙ P3D ЭНКОДЕР ДЛЯ PROTOTYPE
        
Использование:
    python exact_p3d_encoder.py input.wav output.p3d [template.p3d]
    python exact_p3d_encoder.py batch input_folder output_folder [template.p3d]
        
Примеры:
    # Один файл
    python exact_p3d_encoder.py sound.wav sound.p3d
    python exact_p3d_encoder.py sound.wav sound.p3d template.p3d
    
    # Пакетная обработка
    python exact_p3d_encoder.py batch ./wavs/ ./p3ds/
    python exact_p3d_encoder.py batch ./wavs/ ./p3ds/ template.p3d
        
Описание:
    Создает P3D файлы с ТОЧНОЙ структурой оригинальных файлов Prototype.
    Использует правильный формат заголовков и параметры кодирования.
        """)
        sys.exit(1)
    
    if sys.argv[1].lower() == 'batch':
        # Пакетный режим
        if len(sys.argv) < 4:
            print("Использование для пакетной обработки:")
            print("  python exact_p3d_encoder.py batch input_folder output_folder [template.p3d]")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3]
        template_p3d = sys.argv[4] if len(sys.argv) > 4 else None
        
        batch_encode_p3d(input_dir, output_dir, template_p3d)
    
    else:
        # Одиночный файл
        wav_file = sys.argv[1]
        output_p3d = sys.argv[2]
        template_p3d = sys.argv[3] if len(sys.argv) > 3 else None
        
        if not os.path.exists(wav_file):
            print(f"Файл не найден: {wav_file}")
            sys.exit(1)
        
        success = create_exact_p3d(wav_file, output_p3d, template_p3d)
        
        if success:
            print("\n" + "=" * 70)
            print("ФАЙЛ УСПЕШНО СОЗДАН!")
            print("=" * 70)
            print(f"\nПроверьте файл в игре: {output_p3d}")
        else:
            print("\nОшибка создания файла")
            sys.exit(1)

if __name__ == "__main__":
    main()