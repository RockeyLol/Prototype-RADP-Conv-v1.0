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
    """Точная обратная операция decode_ima_nibble из декодера"""
    step = IMA_STEP_TABLE[step_index]
    
    desired_delta = sample - predictor
    
    if desired_delta >= 0:
        sign = 0
        abs_delta = desired_delta
    else:
        sign = 8
        abs_delta = -desired_delta
    
    base_delta = step >> 3
    best_nibble = 0
    best_delta = base_delta
    best_error = abs(abs_delta - base_delta)
    
    for nibble_code in range(8):
        delta = base_delta
        
        if nibble_code & 1:
            delta += step >> 2
        if nibble_code & 2:
            delta += step >> 1
        if nibble_code & 4:
            delta += step
        
        error = abs(abs_delta - delta)
        
        if error < best_error:
            best_error = error
            best_nibble = nibble_code
            best_delta = delta
    
    if sign:
        best_delta = -best_delta
    
    nibble = best_nibble | sign
    
    new_predictor = predictor + best_delta
    new_predictor = clamp16(new_predictor)
    
    new_step_index = step_index + IMA_INDEX_TABLE[nibble & 0x7]
    if new_step_index < 0:
        new_step_index = 0
    elif new_step_index > 88:
        new_step_index = 88
    
    return nibble, new_predictor, new_step_index

def read_wav_file(wav_file):
    """Чтение WAV файла"""
    try:
        with wave.open(wav_file, 'rb') as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sampwidth = wav.getsampwidth()
            nframes = wav.getnframes()
            
            print(f"Чтение WAV: {os.path.basename(wav_file)}")
            print(f"  Каналы: {channels}")
            print(f"  Частота: {sample_rate} Гц")
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

def encode_wav_to_radp(wav_file, output_radp, channels=None, sample_rate=None, unknown_field=0x18):
    """
    Конвертация WAV в RADP файл
    """
    print("=" * 60)
    print("КОНВЕРТАЦИЯ WAV → RADP")
    print("=" * 60)
    
    # Читаем WAV
    wav_data = read_wav_file(wav_file)
    if not wav_data:
        return False
    
    # Используем параметры из WAV или указанные
    if channels is None:
        channels = wav_data['channels']
    if sample_rate is None:
        sample_rate = wav_data['sample_rate']
    
    samples = wav_data['samples']
    
    # Разделяем сэмплы по каналам
    channel_samples = []
    for ch in range(channels):
        channel_samples.append(samples[ch::channels])
    
    BLOCK_SIZE = 0x14  # 20 байт
    SAMPLES_PER_BLOCK = 32
    
    samples_per_channel = len(channel_samples[0])
    blocks_per_channel = (samples_per_channel + SAMPLES_PER_BLOCK - 1) // SAMPLES_PER_BLOCK
    
    encoded_channels = []
    
    for ch in range(channels):
        channel_data = bytearray()
        ch_samples = channel_samples[ch]
        
        predictor = 0
        step_index = 0
        
        for block_idx in range(blocks_per_channel):
            start_sample = block_idx * SAMPLES_PER_BLOCK
            end_sample = min(start_sample + SAMPLES_PER_BLOCK, samples_per_channel)
            block_samples = ch_samples[start_sample:end_sample]
            
            # Заполняем блок последним сэмплом
            if len(block_samples) < SAMPLES_PER_BLOCK:
                last_val = block_samples[-1] if block_samples else 0
                block_samples = list(block_samples) + [last_val] * (SAMPLES_PER_BLOCK - len(block_samples))
            
            # Заголовок блока: step_index (2), predictor (2)
            header = struct.pack('<Hh', step_index, predictor)
            channel_data.extend(header)
            
            # Кодируем 32 сэмпла
            nibbles = []
            for sample in block_samples:
                nibble, predictor, step_index = encode_ima_nibble(sample, predictor, step_index)
                nibbles.append(nibble)
            
            # Упаковываем nibbles (low nibble first)
            for i in range(0, len(nibbles), 2):
                if i + 1 < len(nibbles):
                    byte = nibbles[i] | (nibbles[i+1] << 4)
                else:
                    byte = nibbles[i]
                channel_data.append(byte)
        
        # Доводим до нужного размера
        expected_size = blocks_per_channel * BLOCK_SIZE
        if len(channel_data) < expected_size:
            channel_data.extend(b'\x00' * (expected_size - len(channel_data)))
        
        encoded_channels.append(bytes(channel_data))
    
    # Интерливинг блоков
    adpcm_data = bytearray()
    for block_idx in range(blocks_per_channel):
        for ch in range(channels):
            start_pos = block_idx * BLOCK_SIZE
            end_pos = start_pos + BLOCK_SIZE
            adpcm_data.extend(encoded_channels[ch][start_pos:end_pos])
    
    # Создаем RADP файл
    radp_data = bytearray()
    radp_data.extend(b'radp\0RADP')
    radp_data.extend(struct.pack('<I', channels))
    radp_data.extend(struct.pack('<I', sample_rate))
    radp_data.extend(struct.pack('<I', unknown_field))
    radp_data.extend(struct.pack('<I', len(adpcm_data)))
    radp_data.extend(adpcm_data)
    
    # Сохраняем
    with open(output_radp, 'wb') as f:
        f.write(radp_data)
    
    print(f"\n✓ Создан RADP файл: {output_radp}")
    print(f"  Размер: {len(radp_data)} байт")
    print(f"  Каналы: {channels}")
    print(f"  Частота: {sample_rate} Гц")
    print(f"  Unknown поле: 0x{unknown_field:X}")
    print(f"  ADPCM данных: {len(adpcm_data)} байт")
    print(f"  Блоков на канал: {blocks_per_channel}")
    
    return True

def create_p3d_from_radp(radp_file, output_p3d, template_p3d=None):
    """
    ПРОСТОЙ вариант - скопируем как ты сделал
    """
    with open(radp_file, 'rb') as f:
        radp_data = f.read()
    
    # Имя файла как у тебя
    filename = b"1.temp       \x00"  # 14 байт
    
    # Создаем заголовок ВРУЧНУЮ как в твоем работающем файле
    header = bytearray()
    header.extend(b'P3D\xFF')
    header.extend(b'\x0C\x00\x00\x00')
    header.extend(b'\x00\x00\x00\x00')  # размер
    header.extend(b'\x00\x00\x00\xFE')
    header.extend(b'\x00\x00\x00\x00')  # size-12
    header.extend(b'\x00\x00\x00\x00')  # size-12 дубль
    
    header.extend(b'\x0A\x00\x00\x00')
    header.extend(b'\x09\x00\x00\x00')
    header.extend(b'AudioFile\x00')
    
    header.extend(b'\x02\x00\x00\x00')
    header.extend(b'\x0E\x00\x00\x00')  # длина имени
    header.extend(filename)
    
    # КЛЮЧЕВОЕ: как у тебя - 00 перед длиной KEY
    header.extend(b'\x00')  # лишний нуль
    header.extend(b'\x10\x00\x00\x00')  # длина KEY
    
    header.extend(b'KEY:4\\e\\4e4ea8b4\x00')
    header.extend(b'\x00\x00\x00\x00')
    header.extend(b'\x04\x00\x00\x00')
    header.extend(b'radp\x00')
    
    # RADP данные
    if radp_data.startswith(b'radp\0'):
        radp_inside = radp_data[5:]
    else:
        radp_inside = radp_data
    
    # Собираем
    p3d_data = bytearray()
    p3d_data.extend(header)
    p3d_data.extend(radp_inside)
    
    # Обновляем размер
    final_size = len(p3d_data)
    p3d_data[8:12] = struct.pack('<I', final_size)
    size_minus_12 = final_size - 12
    p3d_data[16:20] = struct.pack('<I', size_minus_12)
    p3d_data[20:24] = struct.pack('<I', size_minus_12)
    
    with open(output_p3d, 'wb') as f:
        f.write(p3d_data)
    
    return True

def create_basic_p3d_header():
    """Создание базового заголовка P3D"""
    header = bytearray()
    
    # P3D сигнатура
    header.extend(b'P3D\xFF')
    
    # Размер файла (временно 0)
    header.extend(b'\x00\x00\x00\x00')
    
    # Неизвестное поле
    header.extend(b'\x0C\x00\x00\x00')
    
    # Смещение до AudioFile (временно)
    header.extend(b'\x00\x00\x00\x00')
    
    # AudioFile секция маркер
    header.extend(b'\x00\x00\x00\xFE')
    
    # Размер секции (временно)
    header.extend(b'\x00\x00\x00\x00')
    header.extend(b'\x00\x00\x00\x00')
    
    # AudioFile заголовок
    header.extend(b'\x0A\x00\x00\x00')  # Длина имени типа
    header.extend(b'\x09\x00\x00\x00')  # Длина строки
    header.extend(b'AudioFile\x00')     # Имя типа
    
    # Имена (2 имени)
    header.extend(b'\x02\x00\x00\x00')  # Количество имен
    
    # Первое имя
    header.extend(b'\x0F\x00\x00\x00')  # Длина
    header.extend(b'custom_audio_000\x00')
    
    # Второе имя  
    header.extend(b'\x10\x00\x00\x00')  # Длина
    header.extend(b'KEY:custom\\audio\x00')
    
    # Тип
    header.extend(b'\x00\x00\x00\x00')
    
    # Кодек radp
    header.extend(b'\x04\x00\x00\x00')  # Длина
    header.extend(b'radp\x00')
    
    return header

def extract_radp_from_p3d(p3d_file, output_radp):
    """Извлечение RADP из P3D файла"""
    print("=" * 60)
    print("ИЗВЛЕЧЕНИЕ RADP ИЗ P3D")
    print("=" * 60)
    
    if not os.path.exists(p3d_file):
        print(f"P3D файл не найден: {p3d_file}")
        return False
    
    with open(p3d_file, 'rb') as f:
        data = f.read()
    
    # Ищем radp
    radp_pos = data.find(b'radp')
    if radp_pos == -1:
        print("Ошибка: не найден radp в P3D файле")
        return False
    
    # Определяем начало RADP данных
    start_pos = radp_pos
    if data[radp_pos+5:radp_pos+9] == b'RADP':
        # Формат: radp\0RADP
        print("Найден формат: radp\\0RADP")
    else:
        # Формат: radp\0
        print("Найден формат: radp\\0")
    
    # Ищем конец файла или следующую секцию
    # Просто берем все от radp до конца файла
    radp_data = data[start_pos:]
    
    # Сохраняем
    with open(output_radp, 'wb') as f:
        f.write(radp_data)
    
    print(f"\n✓ Извлечен RADP файл: {output_radp}")
    print(f"  Размер: {len(radp_data)} байт")
    
    return True

def main():
    """Главная функция"""
    
    if len(sys.argv) < 2:
        print("""
ПРОСТОЙ КОНВЕРТЕР WAV ↔ P3D/RADP
        
Использование:
    
1. Конвертация WAV в RADP:
    python simple_p3d.py wav2radp input.wav output.radp [каналы] [частота] [unknown]
    
2. Конвертация WAV в P3D:
    python simple_p3d.py wav2p3d input.wav output.p3d [шаблон.p3d]
    
3. Создание P3D из RADP:
    python simple_p3d.py radp2p3d input.radp output.p3d [шаблон.p3d]
    
4. Извлечение RADP из P3D:
    python simple_p3d.py extract input.p3d output.radp
    
Параметры:
    каналы     - количество каналов (1-2, по умолчанию из WAV)
    частота    - частота дискретизации (по умолчанию из WAV)
    unknown    - unknown поле (по умолчанию 0x18)
    шаблон.p3d - оригинальный P3D для копирования структуры (опционально)
        
Примеры:
    # WAV → RADP
    python simple_p3d.py wav2radp sound.wav sound.radp
    
    # WAV → P3D (с шаблоном)
    python simple_p3d.py wav2p3d sound.wav sound.p3d original.p3d
    
    # WAV → P3D (без шаблона)
    python simple_p3d.py wav2p3d sound.wav sound.p3d
    
    # RADP → P3D
    python simple_p3d.py radp2p3d sound.radp sound.p3d
    
    # Извлечь RADP
    python simple_p3d.py extract original.p3d extracted.radp
        """)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'wav2radp':
        if len(sys.argv) < 4:
            print("Использование: python simple_p3d.py wav2radp input.wav output.radp [каналы] [частота] [unknown]")
            sys.exit(1)
        
        wav_file = sys.argv[2]
        output_radp = sys.argv[3]
        
        channels = None
        sample_rate = None
        unknown = 0x18
        
        if len(sys.argv) > 4:
            try:
                channels = int(sys.argv[4])
            except:
                pass
        
        if len(sys.argv) > 5:
            try:
                sample_rate = int(sys.argv[5])
            except:
                pass
        
        if len(sys.argv) > 6:
            try:
                unknown = int(sys.argv[6], 16) if 'x' in sys.argv[6] else int(sys.argv[6])
            except:
                pass
        
        success = encode_wav_to_radp(wav_file, output_radp, channels, sample_rate, unknown)
        
    elif command == 'wav2p3d':
        if len(sys.argv) < 4:
            print("Использование: python simple_p3d.py wav2p3d input.wav output.p3d [шаблон.p3d]")
            sys.exit(1)
        
        wav_file = sys.argv[2]
        output_p3d = sys.argv[3]
        template_p3d = sys.argv[4] if len(sys.argv) > 4 else None
        
        # Сначала создаем RADP
        temp_radp = output_p3d.replace('.p3d', '.temp.radp')
        
        if encode_wav_to_radp(wav_file, temp_radp):
            # Затем создаем P3D из RADP
            success = create_p3d_from_radp(temp_radp, output_p3d, template_p3d)
            
            # Удаляем временный файл
            if os.path.exists(temp_radp):
                os.remove(temp_radp)
        else:
            success = False
    
    elif command == 'radp2p3d':
        if len(sys.argv) < 4:
            print("Использование: python simple_p3d.py radp2p3d input.radp output.p3d [шаблон.p3d]")
            sys.exit(1)
        
        radp_file = sys.argv[2]
        output_p3d = sys.argv[3]
        template_p3d = sys.argv[4] if len(sys.argv) > 4 else None
        
        success = create_p3d_from_radp(radp_file, output_p3d, template_p3d)
    
    elif command == 'extract':
        if len(sys.argv) < 4:
            print("Использование: python simple_p3d.py extract input.p3d output.radp")
            sys.exit(1)
        
        p3d_file = sys.argv[2]
        output_radp = sys.argv[3]
        
        success = extract_radp_from_p3d(p3d_file, output_radp)
    
    else:
        print(f"Неизвестная команда: {command}")
        sys.exit(1)
    
    if success:
        print("\n✓ Готово!")
    else:
        print("\n✗ Ошибка!")
        sys.exit(1)

if __name__ == "__main__":
    main()