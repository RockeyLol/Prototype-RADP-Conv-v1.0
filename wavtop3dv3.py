"""
Prototype Radp Conv
Авторы: студия FreedomHellVOICE
Руководитель: Никита Шишкин
"""

import struct
import sys
import os
import wave
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from threading import Thread
import array
import tempfile

# ========== ПЕРЕВОДЫ ==========
LANGUAGES = {
    'ru': {
        'title': 'Prototype Radp Conv v1.0',
        'subtitle': 'Конвертер аудиоформатов для Prototype',
        'mode_frame': 'Режим работы',
        'folders_frame': 'Папки',
        'input_dir': 'Входная папка:',
        'output_dir': 'Выходная папка:',
        'browse': 'Обзор',
        'progress_frame': 'Прогресс',
        'ready': 'Готов к работе',
        'log_frame': 'Лог',
        'batch_process': 'Пакетная обработка',
        'single_file': 'Одиночный файл',
        'clear': 'Очистить',
        'modes': [
            ('WAV → RADP', 'wav2radp'),
            ('WAV → P3D', 'wav2p3d'),
            ('P3D → WAV', 'p3d2wav'),
            ('P3D → RADP', 'p3d2radp'),
            ('RADP → P3D', 'radp2p3d'),
            ('RADP → WAV', 'radp2wav'),
            ('Извлечь RADP', 'extract')
        ],
        'language': 'Язык:',
        'credits_title': 'Об авторах',
        'credits_text': """
╔══════════════════════════════════════════╗
║        PROTOTYPE RADP CONV v1.0          ║
║                                          ║
║     Разработано студией FreedomHellVOICE ║
║                                          ║
║        Руководитель: Никита Шишкин       ║
║                                          ║
║  Конвертер аудиоформатов для игры        ║
║  Prototype и других проектов Bohemia     ║
║                                          ║
║  Поддерживаемые форматы:                 ║
║  • WAV ↔ RADP ↔ P3D                      ║
║  • Пакетная обработка                    ║
║  • Извлечение аудио из P3D контейнеров   ║
║                                          ║
║         © FreedomHellVOICE 2024          ║
╚══════════════════════════════════════════╝
""",
        'errors': {
            'no_input': 'Выберите входную папку',
            'no_output': 'Выберите выходную папку',
            'no_files': 'В папке нет файлов с нужными расширениями',
            'conversion_error': 'Ошибка при конвертации'
        },
        'success': 'Готово',
        'processing': 'Обработка: {} ({}/{})',
        'complete': 'Готово! Успешно: {}, Ошибок: {}'
    },
    'en': {
        'title': 'Prototype Radp Conv v1.0',
        'subtitle': 'Audio converter for Prototype',
        'mode_frame': 'Mode',
        'folders_frame': 'Folders',
        'input_dir': 'Input folder:',
        'output_dir': 'Output folder:',
        'browse': 'Browse',
        'progress_frame': 'Progress',
        'ready': 'Ready',
        'log_frame': 'Log',
        'batch_process': 'Batch Process',
        'single_file': 'Single File',
        'clear': 'Clear',
        'modes': [
            ('WAV → RADP', 'wav2radp'),
            ('WAV → P3D', 'wav2p3d'),
            ('P3D → WAV', 'p3d2wav'),
            ('P3D → RADP', 'p3d2radp'),
            ('RADP → P3D', 'radp2p3d'),
            ('RADP → WAV', 'radp2wav'),
            ('Extract RADP', 'extract')
        ],
        'language': 'Language:',
        'credits_title': 'About',
        'credits_text': """
╔══════════════════════════════════════════╗
║        PROTOTYPE RADP CONV v1.0          ║
║                                          ║
║      Developed by FreedomHellVOICE       ║
║                                          ║
║         Lead: Nikita Shishkin            ║
║                                          ║
║  Audio converter for Prototype game      ║
║  and other Bohemia Interactive projects  ║
║                                          ║
║  Supported formats:                      ║
║  • WAV ↔ RADP ↔ P3D                      ║
║  • Batch processing                      ║
║  • Audio extraction from P3D containers  ║
║                                          ║
║         © FreedomHellVOICE 2024          ║
╚══════════════════════════════════════════╝
""",
        'errors': {
            'no_input': 'Select input folder',
            'no_output': 'Select output folder',
            'no_files': 'No supported files in folder',
            'conversion_error': 'Conversion error'
        },
        'success': 'Done',
        'processing': 'Processing: {} ({}/{})',
        'complete': 'Complete! Success: {}, Failed: {}'
    }
}

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
    """Декодирование IMA ADPCM nibble"""
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

def encode_ima_nibble(sample, predictor, step_index):
    """Кодирование IMA ADPCM nibble"""
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

def decode_radp_to_wav(radp_file, output_wav):
    """Декодирование RADP в WAV"""
    print(f"Декодирование RADP → WAV: {os.path.basename(radp_file)}")
    
    with open(radp_file, 'rb') as f:
        data = f.read()
    
    if not data.startswith(b'radp\0RADP'):
        print("Ошибка: неверный формат RADP")
        return False
    
    # Читаем заголовок RADP
    channels = struct.unpack('<I', data[9:13])[0]
    sample_rate = struct.unpack('<I', data[13:17])[0]
    unknown = struct.unpack('<I', data[17:21])[0]
    adpcm_size = struct.unpack('<I', data[21:25])[0]
    
    print(f"  Каналы: {channels}")
    print(f"  Частота: {sample_rate} Гц")
    print(f"  Unknown: 0x{unknown:X}")
    print(f"  Размер ADPCM: {adpcm_size} байт")
    
    # Параметры блока
    BLOCK_SIZE = 0x14  # 20 байт
    SAMPLES_PER_BLOCK = 32
    blocks_per_channel = adpcm_size // (BLOCK_SIZE * channels)
    
    # Декодируем каждый канал
    all_samples = []
    for ch in range(channels):
        channel_samples = []
        
        for block_idx in range(blocks_per_channel):
            # Позиция блока для этого канала
            block_pos = 25 + (block_idx * channels + ch) * BLOCK_SIZE
            
            if block_pos + BLOCK_SIZE > len(data):
                break
            
            block_data = data[block_pos:block_pos + BLOCK_SIZE]
            
            # Читаем заголовок блока
            step_index = struct.unpack('<H', block_data[0:2])[0]
            predictor = struct.unpack('<h', block_data[2:4])[0]
            
            # Декодируем nibbles
            for i in range(SAMPLES_PER_BLOCK):
                byte_pos = 4 + (i // 2)
                if i % 2 == 0:
                    nibble = block_data[byte_pos] & 0x0F
                else:
                    nibble = (block_data[byte_pos] >> 4) & 0x0F
                
                predictor, step_index = decode_ima_nibble(nibble, predictor, step_index)
                channel_samples.append(predictor)
        
        all_samples.append(channel_samples)
    
    # Интерливинг сэмплов для WAV
    if channels == 1:
        wav_samples = all_samples[0]
    else:
        wav_samples = []
        for i in range(len(all_samples[0])):
            for ch in range(channels):
                wav_samples.append(all_samples[ch][i])
    
    # Создаем WAV файл
    with wave.open(output_wav, 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        
        # Конвертируем в байты
        samples_bytes = struct.pack(f'<{len(wav_samples)}h', *wav_samples)
        wav.writeframes(samples_bytes)
    
    print(f"✓ Создан WAV: {output_wav}")
    print(f"  Сэмплов: {len(wav_samples)}")
    print(f"  Длительность: {len(wav_samples) / sample_rate / channels:.2f} сек")
    
    return True

def encode_wav_to_radp(wav_file, output_radp, channels=None, sample_rate=None, unknown_field=0x18):
    """Кодирование WAV в RADP"""
    print(f"Кодирование WAV → RADP: {os.path.basename(wav_file)}")
    
    try:
        with wave.open(wav_file, 'rb') as wav:
            wav_channels = wav.getnchannels()
            wav_sample_rate = wav.getframerate()
            sampwidth = wav.getsampwidth()
            nframes = wav.getnframes()
            
            print(f"  Каналы: {wav_channels}")
            print(f"  Частота: {wav_sample_rate} Гц")
            print(f"  Сэмплов: {nframes}")
            
            raw_data = wav.readframes(nframes)
            
            if sampwidth == 2:
                samples = struct.unpack(f'<{len(raw_data)//2}h', raw_data)
            elif sampwidth == 1:
                samples = [(b - 128) * 256 for b in raw_data]
            else:
                print(f"  Неподдерживаемая ширина сэмпла: {sampwidth}")
                return False
            
            # Используем параметры из WAV или указанные
            if channels is None:
                channels = wav_channels
            if sample_rate is None:
                sample_rate = wav_sample_rate
            
            # Разделяем сэмплы по каналам
            channel_samples = []
            for ch in range(channels):
                channel_samples.append(samples[ch::channels])
            
            BLOCK_SIZE = 0x14
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
                    
                    if len(block_samples) < SAMPLES_PER_BLOCK:
                        last_val = block_samples[-1] if block_samples else 0
                        block_samples = list(block_samples) + [last_val] * (SAMPLES_PER_BLOCK - len(block_samples))
                    
                    header = struct.pack('<Hh', step_index, predictor)
                    channel_data.extend(header)
                    
                    nibbles = []
                    for sample in block_samples:
                        nibble, predictor, step_index = encode_ima_nibble(sample, predictor, step_index)
                        nibbles.append(nibble)
                    
                    for i in range(0, len(nibbles), 2):
                        if i + 1 < len(nibbles):
                            byte = nibbles[i] | (nibbles[i+1] << 4)
                        else:
                            byte = nibbles[i]
                        channel_data.append(byte)
                
                expected_size = blocks_per_channel * BLOCK_SIZE
                if len(channel_data) < expected_size:
                    channel_data.extend(b'\x00' * (expected_size - len(channel_data)))
                
                encoded_channels.append(bytes(channel_data))
            
            # Интерливинг
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
            
            with open(output_radp, 'wb') as f:
                f.write(radp_data)
            
            print(f"✓ Создан RADP: {output_radp}")
            print(f"  Размер: {len(radp_data)} байт")
            
            return True
            
    except Exception as e:
        print(f"  Ошибка: {e}")
        return False

def create_p3d_from_radp(radp_file, output_p3d, template_p3d=None):
    """Создание P3D из RADP"""
    print(f"Создание P3D из RADP: {os.path.basename(radp_file)}")
    
    with open(radp_file, 'rb') as f:
        radp_data = f.read()
    
    if not radp_data.startswith(b'radp\0RADP'):
        print("  Ошибка: неверный формат RADP")
        return False
    
    # Имя файла (14 байт) - как в рабочем варианте "1.temp       "
    base_name = os.path.splitext(os.path.basename(radp_file))[0]
    if len(base_name) > 13:
        base_name = base_name[:13]
    
    # Создаем имя в стиле "1.temp       "
    filename = "1.temp       \x00"  # Фиксированное имя как в рабочем варианте
    filename_bytes = filename.encode('ascii')
    
    # Создаем заголовок P3D
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
    header.extend(b'\x0E\x00\x00\x00')  # длина имени = 14
    header.extend(filename_bytes)
    
    # Ключевое выравнивание - добавляем 1 нуль (как в рабочем варианте)
    header.extend(b'\x00')  # лишний нуль для выравнивания
    
    header.extend(b'\x10\x00\x00\x00')  # длина KEY = 16
    header.extend(b'KEY:4\\e\\4e4ea8b4\x00')
    header.extend(b'\x00\x00\x00\x00')
    header.extend(b'\x04\x00\x00\x00')
    header.extend(b'radp\x00')
    
    # RADP данные без "radp\0"
    if radp_data.startswith(b'radp\0'):
        radp_inside = radp_data[5:]
    else:
        radp_inside = radp_data
    
    # Собираем P3D
    p3d_data = bytearray()
    p3d_data.extend(header)
    p3d_data.extend(radp_inside)
    
    # Обновляем размер
    final_size = len(p3d_data)
    p3d_data[8:12] = struct.pack('<I', final_size)  # общий размер
    size_minus_12 = final_size - 12
    p3d_data[16:20] = struct.pack('<I', size_minus_12)
    p3d_data[20:24] = struct.pack('<I', size_minus_12)
    
    with open(output_p3d, 'wb') as f:
        f.write(p3d_data)
    
    print(f"✓ Создан P3D: {output_p3d}")
    print(f"  Размер: {final_size} байт")
    
    return True

def extract_radp_from_p3d(p3d_file, output_radp):
    """Извлечение RADP из P3D"""
    print(f"Извлечение RADP из P3D: {os.path.basename(p3d_file)}")
    
    with open(p3d_file, 'rb') as f:
        data = f.read()
    
    # Ищем radp
    radp_pos = data.find(b'radp')
    if radp_pos == -1:
        print("  Ошибка: не найден radp")
        return False
    
    # Определяем начало RADP данных
    start_pos = radp_pos
    if data[radp_pos+5:radp_pos+9] == b'RADP':
        # Формат: radp\0RADP
        radp_data = data[start_pos:]
    else:
        # Формат: radp\0
        radp_data = b'radp\0RADP' + data[start_pos+5:]
    
    with open(output_radp, 'wb') as f:
        f.write(radp_data)
    
    print(f"✓ Извлечен RADP: {output_radp}")
    print(f"  Размер: {len(radp_data)} байт")
    
    return True

def p3d_to_wav(p3d_file, output_wav):
    """Прямое преобразование P3D в WAV"""
    print(f"Преобразование P3D → WAV: {os.path.basename(p3d_file)}")
    
    # Сначала извлекаем RADP
    temp_dir = tempfile.gettempdir()
    temp_radp = os.path.join(temp_dir, f"temp_{os.path.basename(p3d_file)}.radp")
    
    if not extract_radp_from_p3d(p3d_file, temp_radp):
        return False
    
    # Затем декодируем RADP в WAV
    success = decode_radp_to_wav(temp_radp, output_wav)
    
    # Удаляем временный файл
    if os.path.exists(temp_radp):
        os.remove(temp_radp)
    
    return success

def batch_convert(input_dir, output_dir, mode, progress_callback=None):
    """Пакетная конвертация"""
    if not os.path.exists(input_dir):
        return False, "Входная папка не существует"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    supported_extensions = {
        'wav2radp': ['.wav'],
        'wav2p3d': ['.wav'],
        'p3d2wav': ['.p3d'],
        'p3d2radp': ['.p3d'],
        'radp2p3d': ['.radp'],
        'radp2wav': ['.radp'],
        'extract': ['.p3d']
    }
    
    if mode not in supported_extensions:
        return False, f"Неизвестный режим: {mode}"
    
    files = []
    for ext in supported_extensions[mode]:
        files.extend([f for f in os.listdir(input_dir) if f.lower().endswith(ext)])
    
    if not files:
        return False, f"В папке нет файлов с расширениями: {', '.join(supported_extensions[mode])}"
    
    success_count = 0
    fail_count = 0
    
    for i, filename in enumerate(files):
        if progress_callback:
            progress_callback(i, len(files), filename)
        
        input_path = os.path.join(input_dir, filename)
        base_name = os.path.splitext(filename)[0]
        
        try:
            if mode == 'wav2radp':
                output_path = os.path.join(output_dir, base_name + '.radp')
                if encode_wav_to_radp(input_path, output_path):
                    success_count += 1
                else:
                    fail_count += 1
            
            elif mode == 'wav2p3d':
                output_path = os.path.join(output_dir, base_name + '.p3d')
                # Создаем временный RADP файл
                temp_dir = tempfile.gettempdir()
                temp_radp = os.path.join(temp_dir, f"temp_{filename}.radp")
                
                if encode_wav_to_radp(input_path, temp_radp) and \
                   create_p3d_from_radp(temp_radp, output_path):
                    success_count += 1
                else:
                    fail_count += 1
                
                # Удаляем временный файл
                if os.path.exists(temp_radp):
                    os.remove(temp_radp)
            
            elif mode == 'p3d2wav':
                output_path = os.path.join(output_dir, base_name + '.wav')
                if p3d_to_wav(input_path, output_path):
                    success_count += 1
                else:
                    fail_count += 1
            
            elif mode == 'p3d2radp':
                output_path = os.path.join(output_dir, base_name + '.radp')
                if extract_radp_from_p3d(input_path, output_path):
                    success_count += 1
                else:
                    fail_count += 1
            
            elif mode == 'radp2p3d':
                output_path = os.path.join(output_dir, base_name + '.p3d')
                if create_p3d_from_radp(input_path, output_path):
                    success_count += 1
                else:
                    fail_count += 1
            
            elif mode == 'radp2wav':
                output_path = os.path.join(output_dir, base_name + '.wav')
                if decode_radp_to_wav(input_path, output_path):
                    success_count += 1
                else:
                    fail_count += 1
            
            elif mode == 'extract':
                output_path = os.path.join(output_dir, base_name + '.radp')
                if extract_radp_from_p3d(input_path, output_path):
                    success_count += 1
                else:
                    fail_count += 1
        
        except Exception as e:
            print(f"Ошибка при обработке {filename}: {e}")
            fail_count += 1
    
    return True, f"Готово! Успешно: {success_count}, Ошибок: {fail_count}"

class PrototypeRadpConvGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Prototype Radp Conv v1.0")
        self.root.geometry("800x700")
        
        # Текущий язык
        self.current_lang = 'ru'
        self.lang = LANGUAGES[self.current_lang]
        
        # Секретная комбинация
        self.root.bind('<Shift-F1>', self.show_credits)
        
        self.setup_ui()
    
    def setup_ui(self):
        # Верхняя панель с языком
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=5)
        
        tk.Label(top_frame, text=self.lang['language'], 
                font=("Arial", 10)).pack(side="left")
        
        self.lang_var = tk.StringVar(value=self.current_lang)
        lang_menu = tk.OptionMenu(top_frame, self.lang_var, 'ru', 'en', 
                                 command=self.change_language)
        lang_menu.pack(side="left", padx=5)
        
        # Заголовок
        title_frame = tk.Frame(self.root)
        title_frame.pack(pady=10)
        
        self.title_label = tk.Label(title_frame, text=self.lang['title'], 
                                   font=("Arial", 16, "bold"))
        self.title_label.pack()
        
        self.subtitle_label = tk.Label(title_frame, text=self.lang['subtitle'], 
                                      font=("Arial", 10))
        self.subtitle_label.pack()
        
        # Режимы работы - в одну строку
        self.mode_frame = tk.LabelFrame(self.root, text=self.lang['mode_frame'], 
                                       padx=10, pady=10)
        self.mode_frame.pack(pady=10, padx=20, fill="x")
        
        self.mode_var = tk.StringVar(value="wav2radp")
        self.setup_mode_buttons()
        
        # Папки
        self.folders_frame = tk.LabelFrame(self.root, text=self.lang['folders_frame'], 
                                          padx=10, pady=10)
        self.folders_frame.pack(pady=10, padx=20, fill="x")
        
        self.setup_folders()
        
        # Прогресс
        self.progress_frame = tk.LabelFrame(self.root, text=self.lang['progress_frame'], 
                                           padx=10, pady=10)
        self.progress_frame.pack(pady=10, padx=20, fill="x")
        
        self.progress_var = tk.StringVar(value=self.lang['ready'])
        self.progress_label = tk.Label(self.progress_frame, textvariable=self.progress_var, 
                                      wraplength=750)
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, length=750, mode='determinate')
        self.progress_bar.pack(pady=5)
        
        # Кнопки
        buttons_frame = tk.Frame(self.root)
        buttons_frame.pack(pady=15)
        
        self.batch_button = tk.Button(buttons_frame, text=self.lang['batch_process'], 
                                     command=self.start_batch_process, bg="#4CAF50", fg="white",
                                     font=("Arial", 11, "bold"), padx=25, pady=12)
        self.batch_button.pack(side="left", padx=10)
        
        self.single_button = tk.Button(buttons_frame, text=self.lang['single_file'], 
                                      command=self.single_file, bg="#2196F3", fg="white",
                                      font=("Arial", 11), padx=25, pady=12)
        self.single_button.pack(side="left", padx=10)
        
        self.clear_button = tk.Button(buttons_frame, text=self.lang['clear'], 
                                     command=self.clear_fields, bg="#f44336", fg="white",
                                     font=("Arial", 11), padx=25, pady=12)
        self.clear_button.pack(side="left", padx=10)
        
        # Лог
        self.log_frame = tk.LabelFrame(self.root, text=self.lang['log_frame'], 
                                      padx=10, pady=10)
        self.log_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.log_text = tk.Text(self.log_frame, height=12, width=90)
        self.log_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def setup_mode_buttons(self):
        # Очищаем фрейм
        for widget in self.mode_frame.winfo_children():
            widget.destroy()
        
        # Создаем фрейм для кнопок в одну строку
        mode_buttons_frame = tk.Frame(self.mode_frame)
        mode_buttons_frame.pack(fill="x")
        
        # Создаем радиокнопки в одну строку
        row_frame = tk.Frame(mode_buttons_frame)
        row_frame.pack(fill="x", pady=5)
        
        for i, (text, value) in enumerate(self.lang['modes']):
            rb = tk.Radiobutton(row_frame, text=text, variable=self.mode_var, 
                               value=value, font=("Arial", 10))
            rb.pack(side="left", padx=15)
    
    def setup_folders(self):
        # Очищаем фрейм
        for widget in self.folders_frame.winfo_children():
            widget.destroy()
        
        # Входная папка
        tk.Label(self.folders_frame, text=self.lang['input_dir'], 
                font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=8)
        
        self.input_dir_var = tk.StringVar()
        tk.Entry(self.folders_frame, textvariable=self.input_dir_var, 
                width=60, font=("Arial", 10)).grid(row=0, column=1, padx=10)
        
        tk.Button(self.folders_frame, text=self.lang['browse'], 
                 command=self.browse_input_dir, font=("Arial", 10)).grid(row=0, column=2)
        
        # Выходная папка
        tk.Label(self.folders_frame, text=self.lang['output_dir'], 
                font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=8)
        
        self.output_dir_var = tk.StringVar()
        tk.Entry(self.folders_frame, textvariable=self.output_dir_var, 
                width=60, font=("Arial", 10)).grid(row=1, column=1, padx=10)
        
        tk.Button(self.folders_frame, text=self.lang['browse'], 
                 command=self.browse_output_dir, font=("Arial", 10)).grid(row=1, column=2)
    
    def change_language(self, lang_code):
        self.current_lang = lang_code
        self.lang = LANGUAGES[lang_code]
        
        # Обновляем все тексты
        self.root.title(self.lang['title'])
        self.title_label.config(text=self.lang['title'])
        self.subtitle_label.config(text=self.lang['subtitle'])
        self.mode_frame.config(text=self.lang['mode_frame'])
        self.folders_frame.config(text=self.lang['folders_frame'])
        self.progress_frame.config(text=self.lang['progress_frame'])
        self.log_frame.config(text=self.lang['log_frame'])
        
        self.batch_button.config(text=self.lang['batch_process'])
        self.single_button.config(text=self.lang['single_file'])
        self.clear_button.config(text=self.lang['clear'])
        
        self.progress_var.set(self.lang['ready'])
        
        # Обновляем кнопки режимов
        self.setup_mode_buttons()
        
        # Обновляем папки
        self.setup_folders()
    
    def browse_input_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir_var.set(directory)
    
    def browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def update_progress(self, current, total, filename):
        if total > 0:
            percent = (current / total) * 100
            self.progress_bar['value'] = percent
            self.progress_var.set(self.lang['processing'].format(filename, current, total))
        self.root.update()
    
    def start_batch_process(self):
        input_dir = self.input_dir_var.get()
        output_dir = self.output_dir_var.get()
        mode = self.mode_var.get()
        
        if not input_dir:
            messagebox.showerror(self.lang['errors']['no_input'], 
                               self.lang['errors']['no_input'])
            return
        
        if not output_dir:
            messagebox.showerror(self.lang['errors']['no_output'], 
                               self.lang['errors']['no_output'])
            return
        
        self.log(f"Начата пакетная обработка: {mode}")
        self.log(f"Входная папка: {input_dir}")
        self.log(f"Выходная папка: {output_dir}")
        
        # Запуск в отдельном потоке
        thread = Thread(target=self.run_batch_process, args=(input_dir, output_dir, mode))
        thread.daemon = True
        thread.start()
    
    def run_batch_process(self, input_dir, output_dir, mode):
        self.progress_bar['value'] = 0
        
        def progress_callback(current, total, filename):
            self.update_progress(current, total, filename)
        
        success, message = batch_convert(input_dir, output_dir, mode, progress_callback)
        
        self.progress_bar['value'] = 100
        self.progress_var.set(message)
        self.log(message)
        
        if success:
            messagebox.showinfo(self.lang['success'], message)
        else:
            messagebox.showerror(self.lang['errors']['conversion_error'], message)
    
    def single_file(self):
        mode = self.mode_var.get()
        
        # Карта типов файлов для диалога открытия
        input_filetypes_map = {
            'wav2radp': [("WAV files", "*.wav")],
            'wav2p3d': [("WAV files", "*.wav")],
            'p3d2wav': [("P3D files", "*.p3d")],
            'p3d2radp': [("P3D files", "*.p3d")],
            'radp2p3d': [("RADP files", "*.radp")],
            'radp2wav': [("RADP files", "*.radp")],
            'extract': [("P3D files", "*.p3d")]
        }
        
        input_filetypes = input_filetypes_map.get(mode, [("All files", "*.*")])
        
        input_file = filedialog.askopenfilename(filetypes=input_filetypes)
        if not input_file:
            return
        
        # Карта расширений для СОХРАНЕНИЯ
        save_ext_map = {
            'wav2radp': '.radp',
            'wav2p3d': '.p3d',
            'p3d2wav': '.wav',
            'p3d2radp': '.radp',
            'radp2p3d': '.p3d',
            'radp2wav': '.wav',
            'extract': '.radp'
        }
        
        save_ext = save_ext_map.get(mode, '')
        
        # Получаем базовое имя без расширения
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        suggested_name = base_name + save_ext
        
        # Карта типов файлов для диалога сохранения
        save_filetypes_map = {
            'wav2radp': [("RADP files", "*.radp")],
            'wav2p3d': [("P3D files", "*.p3d")],
            'p3d2wav': [("WAV files", "*.wav")],
            'p3d2radp': [("RADP files", "*.radp")],
            'radp2p3d': [("P3D files", "*.p3d")],
            'radp2wav': [("WAV files", "*.wav")],
            'extract': [("RADP files", "*.radp")]
        }
        
        save_filetypes = save_filetypes_map.get(mode, [("All files", "*.*")])
        
        output_file = filedialog.asksaveasfilename(
            defaultextension=save_ext,
            initialfile=suggested_name,
            filetypes=save_filetypes
        )
        
        if not output_file:
            return
        
        self.log(f"Обработка одиночного файла: {os.path.basename(input_file)}")
        
        try:
            success = False
            
            if mode == 'wav2radp':
                success = encode_wav_to_radp(input_file, output_file)
                
            elif mode == 'wav2p3d':
                # Сначала в RADP, потом в P3D
                temp_dir = tempfile.gettempdir()
                temp_radp = os.path.join(temp_dir, f"temp_{base_name}.radp")
                
                if encode_wav_to_radp(input_file, temp_radp):
                    success = create_p3d_from_radp(temp_radp, output_file)
                    if os.path.exists(temp_radp):
                        os.remove(temp_radp)
                        
            elif mode == 'p3d2wav':
                success = p3d_to_wav(input_file, output_file)
                
            elif mode == 'p3d2radp':
                # Это просто извлечение RADP из P3D
                success = extract_radp_from_p3d(input_file, output_file)
                
            elif mode == 'radp2p3d':
                success = create_p3d_from_radp(input_file, output_file)
                
            elif mode == 'radp2wav':
                success = decode_radp_to_wav(input_file, output_file)
                
            elif mode == 'extract':
                success = extract_radp_from_p3d(input_file, output_file)
            
            if success:
                self.log(f"✓ Успешно создан: {os.path.basename(output_file)}")
                messagebox.showinfo(self.lang['success'], 
                                  f"Файл успешно создан:\n{output_file}")
            else:
                self.log(f"✗ Ошибка при создании файла")
                messagebox.showerror(self.lang['errors']['conversion_error'], 
                                   self.lang['errors']['conversion_error'])
        
        except Exception as e:
            self.log(f"✗ Исключение: {e}")
            messagebox.showerror("Error", f"Произошла ошибка:\n{e}")
    
    def clear_fields(self):
        self.input_dir_var.set("")
        self.output_dir_var.set("")
        self.progress_var.set(self.lang['ready'])
        self.progress_bar['value'] = 0
        self.log_text.delete(1.0, tk.END)
        self.log("Лог очищен")
    
    def show_credits(self, event=None):
        credit_window = tk.Toplevel(self.root)
        credit_window.title(self.lang['credits_title'])
        credit_window.geometry("500x400")
        
        tk.Label(credit_window, text=self.lang['credits_text'], 
                font=("Courier", 10), justify="left").pack(padx=20, pady=20)
        
        tk.Button(credit_window, text="Закрыть" if self.current_lang == 'ru' else "Close", 
                 command=credit_window.destroy).pack(pady=10)
    
    def run(self):
        self.root.mainloop()

def main():
    print("Prototype Radp Conv v1.0")
    print("Авторы: студия FreedomHellVOICE")
    print("Руководитель: Никита Шишкин")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # Командная строка
        pass
    else:
        # GUI режим
        app = PrototypeRadpConvGUI()
        app.run()

if __name__ == "__main__":
    main()