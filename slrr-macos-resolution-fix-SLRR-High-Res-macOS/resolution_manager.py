#!/usr/bin/env python3
"""
SLRR Resolution Manager for macOS
Поддержка высоких разрешений через windowed mode
"""
import os
import struct
import shutil
from datetime import datetime

GAME_DIR = "/Users/kirill/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Street Legal Racing Redline"
OPTIONS_FILE = f"{GAME_DIR}/save/game/options"

# Безопасные разрешения для Mac (проверено предыдущим агентом)
SAFE_RESOLUTIONS = {
    "800x600": (800, 600),
    "1024x768": (1024, 768),
    "1280x800": (1280, 800),  # Максимальное стабильное
}

# Экспериментальные (могут крашить)
EXPERIMENTAL_RESOLUTIONS = {
    "1440x900": (1440, 900),
    "1680x1050": (1680, 1050),
    "1920x1080": (1920, 1080),
    "2560x1440": (2560, 1440),
    "2560x1600": (2560, 1600),
}

def backup_options():
    """Создает backup файла настроек"""
    if not os.path.exists(OPTIONS_FILE):
        print("⚠️  Файл options не найден. Запустите игру сначала.")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{OPTIONS_FILE}.backup_{timestamp}"
    shutil.copy2(OPTIONS_FILE, backup_file)
    print(f"✅ Backup создан: {os.path.basename(backup_file)}")
    return True

def restore_latest_backup():
    """Восстанавливает последний backup"""
    save_dir = os.path.dirname(OPTIONS_FILE)
    backups = sorted([f for f in os.listdir(save_dir) if f.startswith("options.backup_")])
    
    if not backups:
        print("❌ Backup файлы не найдены")
        return False
    
    latest = backups[-1]
    shutil.copy2(f"{save_dir}/{latest}", OPTIONS_FILE)
    print(f"✅ Восстановлен backup: {latest}")
    return True

def set_resolution(width, height, windowed=True):
    """Устанавливает разрешение в файле options"""
    if not os.path.exists(OPTIONS_FILE):
        print("❌ Файл options не найден. Запустите игру и создайте карьеру.")
        return False
    
    # Читаем файл
    with open(OPTIONS_FILE, 'rb') as f:
        data = bytearray(f.read())
    
    # Проверяем сигнатуру
    if data[0:4] != b'SDAT':
        print("❌ Неверный формат файла options")
        return False
    
    # Патчим разрешение (little-endian)
    # Offset 0x14: ширина (4 байта)
    # Offset 0x18: высота (4 байта)
    struct.pack_into('<I', data, 0x14, width)
    struct.pack_into('<I', data, 0x18, height)
    
    # Windowed mode flag (offset 0x10, 4 байта)
    # 0 = fullscreen, 1 = windowed
    if windowed:
        struct.pack_into('<I', data, 0x10, 1)
    
    # Записываем обратно
    with open(OPTIONS_FILE, 'wb') as f:
        f.write(data)
    
    mode = "windowed" if windowed else "fullscreen"
    print(f"✅ Установлено: {width}x{height} ({mode})")
    return True

def get_current_resolution():
    """Читает текущее разрешение"""
    if not os.path.exists(OPTIONS_FILE):
        return None
    
    with open(OPTIONS_FILE, 'rb') as f:
        data = f.read()
    
    if data[0:4] != b'SDAT':
        return None
    
    width = struct.unpack_from('<I', data, 0x14)[0]
    height = struct.unpack_from('<I', data, 0x18)[0]
    windowed = struct.unpack_from('<I', data, 0x10)[0]
    
    return (width, height, bool(windowed))

def interactive_menu():
    """Интерактивное меню"""
    print("\n" + "="*50)
    print("🎮 SLRR Resolution Manager для macOS")
    print("="*50)
    
    current = get_current_resolution()
    if current:
        w, h, windowed = current
        mode = "windowed" if windowed else "fullscreen"
        print(f"\n📺 Текущее: {w}x{h} ({mode})")
    else:
        print("\n⚠️  Файл options не найден")
    
    print("\n🟢 БЕЗОПАСНЫЕ РАЗРЕШЕНИЯ (стабильные):")
    for i, (name, res) in enumerate(SAFE_RESOLUTIONS.items(), 1):
        print(f"  {i}. {name}")
    
    print("\n🟡 ЭКСПЕРИМЕНТАЛЬНЫЕ (могут крашить):")
    offset = len(SAFE_RESOLUTIONS)
    for i, (name, res) in enumerate(EXPERIMENTAL_RESOLUTIONS.items(), offset + 1):
        print(f"  {i}. {name}")
    
    print(f"\n  {offset + len(EXPERIMENTAL_RESOLUTIONS) + 1}. Свое разрешение")
    print(f"  {offset + len(EXPERIMENTAL_RESOLUTIONS) + 2}. Восстановить backup")
    print("  0. Выход")
    
    try:
        choice = int(input("\nВыбор: "))
    except ValueError:
        print("❌ Неверный ввод")
        return
    
    if choice == 0:
        return
    
    all_resolutions = {**SAFE_RESOLUTIONS, **EXPERIMENTAL_RESOLUTIONS}
    res_list = list(all_resolutions.items())
    
    if 1 <= choice <= len(res_list):
        backup_options()
        name, (w, h) = res_list[choice - 1]
        
        if choice > len(SAFE_RESOLUTIONS):
            print("\n⚠️  ВНИМАНИЕ: Экспериментальное разрешение!")
            print("   Игра может крашнуться. Backup создан.")
            confirm = input("   Продолжить? (y/n): ")
            if confirm.lower() != 'y':
                return
        
        set_resolution(w, h, windowed=True)
        print("\n✅ Готово! Запускайте игру.")
        
    elif choice == len(res_list) + 1:
        try:
            w = int(input("Ширина: "))
            h = int(input("Высота: "))
            backup_options()
            set_resolution(w, h, windowed=True)
            print("\n⚠️  Кастомное разрешение установлено. Тестируйте осторожно!")
        except ValueError:
            print("❌ Неверный ввод")
    
    elif choice == len(res_list) + 2:
        restore_latest_backup()
    
    else:
        print("❌ Неверный выбор")

if __name__ == "__main__":
    interactive_menu()
