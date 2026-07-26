"""
Knowledge Base — статичная база знаний о железе.

Содержит проверенные факты о видеокартах, процессорах и архитектурах.
Используется для быстрой проверки без веб-поиска.

**Feature: anti-hallucination-v1**
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """Информация о видеокарте."""
    name: str
    vram_gb: int
    bus_width: int
    architecture: str
    release_year: int
    msrp_usd: Optional[int] = None
    tdp_watts: Optional[int] = None
    cuda_cores: Optional[int] = None  # NVIDIA
    stream_processors: Optional[int] = None  # AMD


@dataclass
class CPUInfo:
    """Информация о процессоре."""
    name: str
    cores: int
    threads: int
    architecture: str
    release_year: int
    socket: str
    tdp_watts: Optional[int] = None
    base_clock_ghz: Optional[float] = None
    boost_clock_ghz: Optional[float] = None
    has_igpu: bool = False
    cache_l3_mb: Optional[int] = None


@dataclass
class PlatformInfo:
    """Информация о платформе (сокет + чипсет)."""
    name: str
    socket: str
    chipsets: list[str]
    memory_type: str  # DDR4, DDR5, DDR4/DDR5
    pcie_version: str  # 4.0, 5.0
    release_year: int
    vendor: str  # Intel, AMD
    description: str
    recommended_for: str


@dataclass 
class RAMInfo:
    """Информация о стандартах памяти."""
    type: str  # DDR4, DDR5
    speed_range: str  # "3200-3600" MT/s
    recommended_speed: str
    channels: int
    typical_capacity_gb: list[int]  # [16, 32, 64]
    notes: str


@dataclass
class StorageInfo:
    """Информация о накопителях."""
    interface: str  # NVMe PCIe 4.0, NVMe PCIe 5.0, SATA
    max_speed_read: str  # "7000 MB/s"
    max_speed_write: str
    typical_capacity: list[int]  # GB
    notes: str


@dataclass
class SoftwareInfo:
    """Информация о софте для тюнинга/мониторинга."""
    name: str
    category: str  # os, tuning, monitoring, stress_test, drivers
    description: str
    url: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class TuningGuide:
    """Гайд по тюнингу компонента."""
    component: str  # cpu_amd, cpu_intel, gpu_nvidia, gpu_amd, ram_ddr5
    method: str
    steps: list[str]
    tools: list[str]
    warnings: list[str]


class KnowledgeBase:
    """
    База знаний о железе.
    
    Содержит проверенные данные для быстрой валидации
    без необходимости веб-поиска.
    """
    
    # Последнее обновление базы
    LAST_UPDATED = "2025-01-17"
    
    # =========================================================================
    # ПЛАТФОРМЫ 2025
    # =========================================================================
    
    PLATFORMS: dict[str, PlatformInfo] = {
        # Intel
        "lga1700": PlatformInfo(
            name="Intel LGA1700",
            socket="LGA1700",
            chipsets=["B660", "Z690", "B760", "Z790"],
            memory_type="DDR4/DDR5",
            pcie_version="4.0/5.0",
            release_year=2021,
            vendor="Intel",
            description="Платформа для Intel Core 12-14 поколения (Alder/Raptor Lake)",
            recommended_for="Игровые и рабочие сборки среднего бюджета"
        ),
        "lga1851": PlatformInfo(
            name="Intel LGA1851",
            socket="LGA1851",
            chipsets=["Z890", "B860"],
            memory_type="DDR5",
            pcie_version="5.0",
            release_year=2024,
            vendor="Intel",
            description="Новая платформа для Intel Core Ultra (Arrow Lake)",
            recommended_for="Хай-энд игры и продакшн, PCIe 5.0 для SSD/GPU"
        ),
        # AMD
        "am5": PlatformInfo(
            name="AMD AM5",
            socket="AM5",
            chipsets=["B650", "B650E", "X670", "X670E", "X870", "X870E"],
            memory_type="DDR5",
            pcie_version="5.0",
            release_year=2022,
            vendor="AMD",
            description="Платформа для Ryzen 7000/9000 (Zen 4/5), заявлена как долгоживущая",
            recommended_for="Игровые и универсальные системы, DDR5-6000 EXPO оптимально"
        ),
        "am4": PlatformInfo(
            name="AMD AM4",
            socket="AM4",
            chipsets=["B450", "B550", "X570"],
            memory_type="DDR4",
            pcie_version="4.0",
            release_year=2017,
            vendor="AMD",
            description="Платформа для Ryzen 1000-5000 (Zen-Zen 3), всё ещё актуальна для бюджета",
            recommended_for="Бюджетные сборки, апгрейд старых систем"
        ),
        "trx50": PlatformInfo(
            name="AMD TRX50",
            socket="sTR5",
            chipsets=["TRX50"],
            memory_type="DDR5",
            pcie_version="5.0",
            release_year=2023,
            vendor="AMD",
            description="HEDT платформа для Threadripper 7000/9000",
            recommended_for="Рендер, 3D, продакшн, рабочие станции"
        ),
    }
    
    # =========================================================================
    # ПРОЦЕССОРЫ 2025
    # =========================================================================
    
    INTEL_CPUS: dict[str, CPUInfo] = {
        # Core Ultra (Arrow Lake) - LGA1851
        "core ultra 9 285k": CPUInfo("Core Ultra 9 285K", 24, 24, "Arrow Lake", 2024, "LGA1851", 125, 3.7, 5.7, True, 36),
        "core ultra 7 265k": CPUInfo("Core Ultra 7 265K", 20, 20, "Arrow Lake", 2024, "LGA1851", 125, 3.9, 5.5, True, 30),
        "core ultra 5 245k": CPUInfo("Core Ultra 5 245K", 14, 14, "Arrow Lake", 2024, "LGA1851", 125, 4.2, 5.2, True, 24),
        # Raptor Lake Refresh - LGA1700
        "i9-14900k": CPUInfo("Core i9-14900K", 24, 32, "Raptor Lake", 2023, "LGA1700", 125, 3.2, 6.0, True, 36),
        "i9-14900kf": CPUInfo("Core i9-14900KF", 24, 32, "Raptor Lake", 2023, "LGA1700", 125, 3.2, 6.0, False, 36),
        "i7-14700k": CPUInfo("Core i7-14700K", 20, 28, "Raptor Lake", 2023, "LGA1700", 125, 3.4, 5.6, True, 33),
        "i7-14700kf": CPUInfo("Core i7-14700KF", 20, 28, "Raptor Lake", 2023, "LGA1700", 125, 3.4, 5.6, False, 33),
        "i5-14600k": CPUInfo("Core i5-14600K", 14, 20, "Raptor Lake", 2023, "LGA1700", 125, 3.5, 5.3, True, 24),
        "i5-14600kf": CPUInfo("Core i5-14600KF", 14, 20, "Raptor Lake", 2023, "LGA1700", 125, 3.5, 5.3, False, 24),
        "i5-14400": CPUInfo("Core i5-14400", 10, 16, "Raptor Lake", 2024, "LGA1700", 65, 2.5, 4.7, True, 20),
        "i5-12400": CPUInfo("Core i5-12400", 6, 12, "Alder Lake", 2022, "LGA1700", 65, 2.5, 4.4, True, 18),
    }
    
    AMD_CPUS: dict[str, CPUInfo] = {
        # Ryzen 9000 (Zen 5) - AM5
        "ryzen 9 9950x": CPUInfo("Ryzen 9 9950X", 16, 32, "Zen 5", 2024, "AM5", 170, 4.3, 5.7, False, 64),
        "ryzen 9 9900x": CPUInfo("Ryzen 9 9900X", 12, 24, "Zen 5", 2024, "AM5", 120, 4.4, 5.6, False, 64),
        "ryzen 7 9800x3d": CPUInfo("Ryzen 7 9800X3D", 8, 16, "Zen 5", 2024, "AM5", 120, 4.7, 5.2, False, 96),  # 3D V-Cache!
        "ryzen 7 9700x": CPUInfo("Ryzen 7 9700X", 8, 16, "Zen 5", 2024, "AM5", 65, 3.8, 5.5, False, 32),
        "ryzen 5 9600x": CPUInfo("Ryzen 5 9600X", 6, 12, "Zen 5", 2024, "AM5", 65, 3.9, 5.4, False, 32),
        # Ryzen 7000 (Zen 4) - AM5
        "ryzen 9 7950x": CPUInfo("Ryzen 9 7950X", 16, 32, "Zen 4", 2022, "AM5", 170, 4.5, 5.7, True, 64),
        "ryzen 9 7900x": CPUInfo("Ryzen 9 7900X", 12, 24, "Zen 4", 2022, "AM5", 170, 4.7, 5.6, True, 64),
        "ryzen 7 7800x3d": CPUInfo("Ryzen 7 7800X3D", 8, 16, "Zen 4", 2023, "AM5", 120, 4.2, 5.0, True, 96),  # 3D V-Cache!
        "ryzen 7 7700x": CPUInfo("Ryzen 7 7700X", 8, 16, "Zen 4", 2022, "AM5", 105, 4.5, 5.4, True, 32),
        "ryzen 5 7600x": CPUInfo("Ryzen 5 7600X", 6, 12, "Zen 4", 2022, "AM5", 105, 4.7, 5.3, True, 32),
        "ryzen 5 7600": CPUInfo("Ryzen 5 7600", 6, 12, "Zen 4", 2023, "AM5", 65, 3.8, 5.1, True, 32),
        # Ryzen 5000 (Zen 3) - AM4 (всё ещё актуальны для бюджета)
        "ryzen 7 5800x3d": CPUInfo("Ryzen 7 5800X3D", 8, 16, "Zen 3", 2022, "AM4", 105, 3.4, 4.5, False, 96),
        "ryzen 5 5600x": CPUInfo("Ryzen 5 5600X", 6, 12, "Zen 3", 2020, "AM4", 65, 3.7, 4.6, False, 32),
        "ryzen 5 5600": CPUInfo("Ryzen 5 5600", 6, 12, "Zen 3", 2022, "AM4", 65, 3.5, 4.4, False, 32),
        # Threadripper (HEDT)
        "threadripper 9980x": CPUInfo("Threadripper 9980X", 96, 192, "Zen 5", 2024, "sTR5", 350, 2.6, 5.0, False, 256),
        "threadripper 7980x": CPUInfo("Threadripper 7980X", 64, 128, "Zen 4", 2023, "sTR5", 350, 3.2, 5.1, False, 256),
    }
    
    # =========================================================================
    # ПАМЯТЬ 2025
    # =========================================================================
    
    RAM_STANDARDS: dict[str, RAMInfo] = {
        "ddr5": RAMInfo(
            type="DDR5",
            speed_range="4800-8000+ MT/s",
            recommended_speed="5600-6400 MT/s для игр, DDR5-6000 EXPO для Ryzen",
            channels=2,
            typical_capacity_gb=[16, 32, 64],
            notes="Стандарт 2025 для новых сборок. 32GB (2x16) — золотая середина для AAA и стриминга"
        ),
        "ddr4": RAMInfo(
            type="DDR4",
            speed_range="2133-3600 MT/s",
            recommended_speed="3200-3600 MT/s",
            channels=2,
            typical_capacity_gb=[16, 32],
            notes="Актуальна только для старых платформ (AM4, LGA1200, бюджетные LGA1700)"
        ),
    }
    
    # =========================================================================
    # НАКОПИТЕЛИ 2025
    # =========================================================================
    
    STORAGE_STANDARDS: dict[str, StorageInfo] = {
        "nvme_gen5": StorageInfo(
            interface="NVMe PCIe 5.0",
            max_speed_read="12000+ MB/s",
            max_speed_write="10000+ MB/s",
            typical_capacity=[1000, 2000, 4000],
            notes="Топовые SSD (Crucial T705, Samsung 990 Pro Gen5). Для 4K/8K монтажа, большие копирования. В играх разница с Gen4 минимальна"
        ),
        "nvme_gen4": StorageInfo(
            interface="NVMe PCIe 4.0",
            max_speed_read="7000 MB/s",
            max_speed_write="5500 MB/s",
            typical_capacity=[500, 1000, 2000],
            notes="Мейнстрим 2025. Оптимальный выбор цена/скорость для игр и работы"
        ),
        "nvme_gen3": StorageInfo(
            interface="NVMe PCIe 3.0",
            max_speed_read="3500 MB/s",
            max_speed_write="3000 MB/s",
            typical_capacity=[250, 500, 1000],
            notes="Бюджетный вариант, всё ещё быстрее SATA"
        ),
        "sata_ssd": StorageInfo(
            interface="SATA III",
            max_speed_read="550 MB/s",
            max_speed_write="520 MB/s",
            typical_capacity=[250, 500, 1000, 2000],
            notes="Для хранения, старых систем. Не рекомендуется как основной диск в 2025"
        ),
    }
    
    # =========================================================================
    # РЕКОМЕНДАЦИИ ПО СБОРКАМ 2025
    # =========================================================================
    
    BUILD_RECOMMENDATIONS = {
        "gaming_budget": {
            "name": "Бюджетный гейминг 2025",
            "cpu": ["Ryzen 5 5600", "i5-12400"],
            "platform": "AM4 или LGA1700 (DDR4)",
            "gpu": ["RTX 4060", "RX 7600"],
            "ram": "16-32GB DDR4-3200",
            "storage": "NVMe Gen3/Gen4 500GB-1TB",
            "psu": "550-650W 80+ Bronze",
        },
        "gaming_mid": {
            "name": "Средний гейминг 2025",
            "cpu": ["Ryzen 5 9600X", "Ryzen 7 7800X3D", "i5-14600K"],
            "platform": "AM5 или LGA1700 (DDR5)",
            "gpu": ["RTX 4070", "RTX 4070 Super", "RX 7800 XT"],
            "ram": "32GB DDR5-6000",
            "storage": "NVMe Gen4 1-2TB",
            "psu": "750W 80+ Gold ATX 3.0",
        },
        "gaming_high": {
            "name": "Хай-энд гейминг 2025",
            "cpu": ["Ryzen 7 9800X3D", "Core Ultra 9 285K"],
            "platform": "AM5 или LGA1851 (DDR5)",
            "gpu": ["RTX 4080 Super", "RTX 5080", "RX 7900 XTX"],
            "ram": "32-64GB DDR5-6400+",
            "storage": "NVMe Gen4/Gen5 2TB+",
            "psu": "850-1000W 80+ Gold/Platinum ATX 3.1",
        },
        "workstation": {
            "name": "Рабочая станция 2025",
            "cpu": ["Ryzen 9 9950X", "Threadripper 9980X"],
            "platform": "AM5 или TRX50",
            "gpu": ["RTX 4090", "RTX 5090"],
            "ram": "64-128GB DDR5 ECC",
            "storage": "NVMe Gen5 2-4TB + HDD для архива",
            "psu": "1000-1600W 80+ Platinum ATX 3.1",
        },
    }
    
    # =========================================================================
    # СТАНДАРТЫ И ИНТЕРФЕЙСЫ 2025
    # =========================================================================
    
    STANDARDS_2025 = {
        "psu": {
            "current": "ATX 3.1",
            "connector": "12V-2x6 (замена 12VHPWR)",
            "notes": "До 600W для GPU, улучшенный контакт, меньше риск оплавления",
            "recommended": "80+ Gold/Platinum для RTX 40/50 и RX 7000/8000",
        },
        "pcie": {
            "mainstream": "PCIe 4.0",
            "high_end": "PCIe 5.0",
            "notes": "PCIe 5.0 для SSD даёт 10-12 GB/s, но в играх разница минимальна",
        },
        "wifi": {
            "current": "Wi-Fi 7 (802.11be)",
            "previous": "Wi-Fi 6E (802.11ax)",
            "notes": "Wi-Fi 7 на топовых платах X870/Z890",
        },
        "usb": {
            "current": "USB4 (40 Гбит/с)",
            "common": "USB 3.2 Gen2 (10 Гбит/с)",
            "notes": "USB4 Type-C на новых платах",
        },
    }
    
    # =========================================================================
    # СОФТВЕРНАЯ БАЗА 2025 — ОС, ТЮНИНГ, МОНИТОРИНГ
    # =========================================================================
    
    OPERATING_SYSTEMS = {
        "windows_11": {
            "name": "Windows 11",
            "version": "24H2 / 25H1",
            "status": "Основная система 2025",
            "notes": "24H2 обязательна для Zen 5 / Arrow Lake (оптимизированный планировщик)",
            "optimization": "Chris Titus Tech WinUtil — лучший деблоатер",
            "gaming_tips": [
                "Отключи VBS (Virtualization-Based Security) для +5-10% FPS",
                "Отключи Memory Integrity (Изоляция ядра)",
                "Используй WinUtil: iwr -useb christitus.com/win | iex",
            ],
        },
        "windows_12": {
            "name": "Windows 12",
            "status": "НЕ ВЫШЛА",
            "notes": "Microsoft перенесла релиз на 2026/2027, вместо неё 25H1/25H2",
        },
        "linux_bazzite": {
            "name": "Bazzite",
            "base": "Fedora Atomic",
            "status": "Топ-1 для Linux Gaming",
            "notes": "SteamOS для любого ПК. Идеально для handhelds и HTPC",
        },
        "linux_nobara": {
            "name": "Nobara Project",
            "base": "Fedora",
            "author": "GloriousEggroll",
            "status": "Топ-2 для Linux Gaming",
            "notes": "Fedora с патчами для игр, кодеков и драйверов из коробки",
        },
    }
    
    SOFTWARE_TUNING = {
        # GPU/CPU тюнинг
        "nvidia_app": SoftwareInfo(
            "NVIDIA App", "tuning",
            "Замена GeForce Experience. Не требует логина, встроенный разгон, RTX HDR",
            notes="Старый GFE мертв, ставь NVIDIA App"
        ),
        "msi_afterburner": SoftwareInfo(
            "MSI Afterburner + RTSS", "tuning",
            "Золотой стандарт для мониторинга OSD и андервольта NVIDIA",
            notes="Для AMD лучше встроенный Adrenalin"
        ),
        "fancontrol": SoftwareInfo(
            "FanControl", "tuning",
            "Единственная прога для настройки вентиляторов. Миксует сенсоры",
            notes="Мастхэв для тишины"
        ),
    }
    
    SOFTWARE_MONITORING = {
        "hwinfo64": SoftwareInfo(
            "HWInfo64", "monitoring",
            "Библия сенсоров. Троттлинг VRM, реальное напряжение, WHEA Errors",
            notes="WHEA Errors != 0 = нестабильный разгон"
        ),
        "capframex": SoftwareInfo(
            "CapFrameX", "monitoring",
            "Лучший анализ плавности. 1% low, 0.1% low, статтеры",
            notes="Лучше любых оверлеев для анализа"
        ),
        "zentimings": SoftwareInfo(
            "ZenTimings", "monitoring",
            "Вторичные тайминги DDR5 для AMD",
        ),
        "asrock_timing": SoftwareInfo(
            "AsRock Timing Configurator", "monitoring",
            "Вторичные тайминги DDR5 для Intel",
        ),
    }
    
    SOFTWARE_STRESS_TEST = {
        "occt": SoftwareInfo(
            "OCCT", "stress_test",
            "Лучший комбайн 2025. CPU, память, 3D Adaptive (VRAM)",
            notes="Если крашится за час — система нестабильна"
        ),
        "testmem5": SoftwareInfo(
            "TestMem5 + Anta777 Extreme", "stress_test",
            "Единственный способ быстро найти ошибки DDR5",
            notes="3 цикла без ошибок = память ок"
        ),
        "cinebench": SoftwareInfo(
            "Cinebench 2024 / R23", "stress_test",
            "Проверка андервольта CPU и температур",
            notes="Не тест всей системы, только CPU!"
        ),
        "y_cruncher": SoftwareInfo(
            "Y-Cruncher", "stress_test",
            "Убийца нестабильных Curve Optimizer. Тесты VST и VT3",
            notes="Выявляет ошибки контроллера памяти за минуты"
        ),
        "corecycler": SoftwareInfo(
            "CoreCycler", "stress_test",
            "Скрипт поверх Prime95. Нагружает ядра по очереди",
            notes="Если ядро #2 крашится — ему отдельный CO"
        ),
    }
    
    SOFTWARE_DRIVERS = {
        "ddu": SoftwareInfo(
            "DDU (Display Driver Uninstaller)", "drivers",
            "Святая вода. Safe Mode + DDU при смене видеокарты",
            notes="Особенно при переходе NVIDIA <-> AMD"
        ),
        "nvcleanstall": SoftwareInfo(
            "NVCleanstall", "drivers",
            "Драйвер NVIDIA без телеметрии и мусора",
            notes="Если не хочешь NVIDIA App"
        ),
    }
    
    # =========================================================================
    # ГАЙДЫ ПО ТЮНИНГУ 2025
    # =========================================================================
    
    TUNING_GUIDES = {
        "cpu_amd_zen4_zen5": TuningGuide(
            component="CPU AMD Ryzen (Zen 4/5/X3D)",
            method="PBO2 + Curve Optimizer",
            steps=[
                "В BIOS: AMD Overclocking -> PBO -> Advanced",
                "Limits (PPT/TDC/EDC): Motherboard или сток для X3D",
                "Curve Optimizer: All Cores -> Negative",
                "Начинай с -15 или -20, удачные камни берут -30",
                "Тест: CoreCycler (не Cinebench!)",
                "Если ядро крашится — ему отдельный CO (Per Core)",
            ],
            tools=["CoreCycler", "HWInfo64", "OCCT"],
            warnings=[
                "Курва часто крашится в простое/браузере, не в бенчмарке",
                "Для X3D лучше сток лимиты",
            ]
        ),
        "cpu_intel_13_14_ultra": TuningGuide(
            component="CPU Intel (Core 13/14 Gen & Core Ultra)",
            method="AC/DC Loadline или VF Curve",
            steps=[
                "Способ 1 (Ленивый): AC Loadline / Lite Load",
                "Снижай Mode от дефолта (9-12) к 1-5",
                "Способ 2 (Правильный): VF Curve / SVID Offset",
                "Global Core SVID Offset: -0.050V, до -0.100V",
                "Проверяй в Cinebench: баллы не должны падать",
            ],
            tools=["HWInfo64", "Cinebench", "OCCT"],
            warnings=[
                "Intel жарит — андервольт обязателен против деградации",
                "Clock Stretching: частота высокая, FPS низкий = переборщил",
            ]
        ),
        "gpu_nvidia_rtx40_50": TuningGuide(
            component="GPU NVIDIA (RTX 40/50)",
            method="Андервольт курвой + разгон памяти",
            steps=[
                "MSI Afterburner -> Ctrl+F (кривая)",
                "Найди точку 950 mV, подними до нужной частоты (2700 MHz)",
                "Всё правее — опусти ниже или сделай Flatline",
                "Apply. Карта не возьмёт больше 0.95V",
                "Память: +500, тест, +1000, тест",
                "Если баллы перестали расти — откатывайся",
            ],
            tools=["MSI Afterburner", "Superposition 8K", "HWInfo64"],
            warnings=[
                "ECC Trap: переразгон памяти = FPS падает без артефактов",
                "GDDR6X/GDDR7 тратит такты на коррекцию ошибок",
            ]
        ),
        "gpu_amd_rx7000_9000": TuningGuide(
            component="GPU AMD Radeon (RX 7000/9000)",
            method="Min Frequency Trick + Undervolt",
            steps=[
                "Adrenalin -> Performance -> Tuning",
                "Max Frequency: например 2800 MHz",
                "Min Frequency: на 100 МГц меньше (2700)",
                "Undervolt: снижай по 10-20 мВ (1100->1080->1060)",
                "Power Limit: +15-20% если делаешь андервольт",
            ],
            tools=["AMD Adrenalin", "HWInfo64", "CapFrameX"],
            warnings=[
                "Min Frequency Trick убирает микрофризы",
                "Power Limit вправо даёт карте дышать в пиках",
            ]
        ),
        "ram_ddr5": TuningGuide(
            component="RAM DDR5",
            method="tREFI + вторички",
            steps=[
                "Первичные (CL, tRCD, tRP): дают мало, 6000 CL30 — база",
                "tREFI (главный!): сток ~10000, разгон 50000-65535",
                "tRFC: снижать аккуратно до 400-500 нс",
                "ОБЯЗАТЕЛЬНО: обдув памяти при tREFI 65k",
            ],
            tools=["ZenTimings", "TestMem5 + Anta777", "HWInfo64"],
            warnings=[
                "DDR5 чувствительна к температуре: >50-55°C = ошибки",
                "При tREFI 65k без обдува — BSOD от потери данных",
                "TestMem5 ошибка сразу = дикая нестабильность",
                "Ошибка через 40 мин = перегрев, ставь вентилятор",
            ]
        ),
    }
    
    # Чеклист после установки Windows
    WINDOWS_SETUP_CHECKLIST = [
        "1. Ставишь драйверы: Chipset, GPU, Audio",
        "2. Chris Titus WinUtil: iwr -useb christitus.com/win | iex",
        "3. Жмёшь Desktop твики, отключаешь телеметрию",
        "4. Ставишь FanControl, настраиваешь кривые",
        "5. В BIOS: XMP/EXPO и ReSize BAR",
        "6. (Опционально) Андервольт GPU в MSI Afterburner",
    ]
    
    # Чеклист стабильности
    STABILITY_CHECKLIST = {
        "ddr5": "TestMem5 + Anta777: ошибка сразу = нестабильность, через 40 мин = перегрев",
        "gpu": "Superposition 8K: лучше Furmark, тестирует память и шейдеры",
        "cpu": "OCCT / CoreCycler: час теста без крашей",
        "whea": "HWInfo64 -> WHEA Errors: если не 0 — разгон говно, откатывай",
    }
    
    # NVIDIA видеокарты (актуальные поколения)
    NVIDIA_GPUS: dict[str, GPUInfo] = {
        # RTX 50 series (Blackwell, анонсированы CES 2025)
        "rtx 5090": GPUInfo("RTX 5090", 32, 512, "Blackwell", 2025, 1999, 575, 21760),
        "rtx 5080": GPUInfo("RTX 5080", 16, 256, "Blackwell", 2025, 999, 360, 10752),
        "rtx 5070 ti": GPUInfo("RTX 5070 Ti", 16, 256, "Blackwell", 2025, 749, 300, 8960),
        "rtx 5070": GPUInfo("RTX 5070", 12, 192, "Blackwell", 2025, 549, 250, 6144),
        # RTX 40 series (Ada Lovelace)
        "rtx 4090": GPUInfo("RTX 4090", 24, 384, "Ada Lovelace", 2022, 1599, 450, 16384),
        "rtx 4080 super": GPUInfo("RTX 4080 Super", 16, 256, "Ada Lovelace", 2024, 999, 320, 10240),
        "rtx 4080": GPUInfo("RTX 4080", 16, 256, "Ada Lovelace", 2022, 1199, 320, 9728),
        "rtx 4070 ti super": GPUInfo("RTX 4070 Ti Super", 16, 256, "Ada Lovelace", 2024, 799, 285, 8448),
        "rtx 4070 ti": GPUInfo("RTX 4070 Ti", 12, 192, "Ada Lovelace", 2023, 799, 285, 7680),
        "rtx 4070 super": GPUInfo("RTX 4070 Super", 12, 192, "Ada Lovelace", 2024, 599, 220, 7168),
        "rtx 4070": GPUInfo("RTX 4070", 12, 192, "Ada Lovelace", 2023, 599, 200, 5888),
        "rtx 4060 ti": GPUInfo("RTX 4060 Ti", 8, 128, "Ada Lovelace", 2023, 399, 160, 4352),
        "rtx 4060": GPUInfo("RTX 4060", 8, 128, "Ada Lovelace", 2023, 299, 115, 3072),
        
        # RTX 30 series (Ampere)
        "rtx 3090 ti": GPUInfo("RTX 3090 Ti", 24, 384, "Ampere", 2022, 1999, 450, 10752),
        "rtx 3090": GPUInfo("RTX 3090", 24, 384, "Ampere", 2020, 1499, 350, 10496),
        "rtx 3080 ti": GPUInfo("RTX 3080 Ti", 12, 384, "Ampere", 2021, 1199, 350, 10240),
        "rtx 3080": GPUInfo("RTX 3080", 10, 320, "Ampere", 2020, 699, 320, 8704),
        "rtx 3070 ti": GPUInfo("RTX 3070 Ti", 8, 256, "Ampere", 2021, 599, 290, 6144),
        "rtx 3070": GPUInfo("RTX 3070", 8, 256, "Ampere", 2020, 499, 220, 5888),
        "rtx 3060 ti": GPUInfo("RTX 3060 Ti", 8, 256, "Ampere", 2020, 399, 200, 4864),
        "rtx 3060": GPUInfo("RTX 3060", 12, 192, "Ampere", 2021, 329, 170, 3584),
        "rtx 3050": GPUInfo("RTX 3050", 8, 128, "Ampere", 2022, 249, 130, 2560),
    }
    
    # AMD видеокарты
    AMD_GPUS: dict[str, GPUInfo] = {
        # RX 7000 series (RDNA 3)
        "rx 7900 xtx": GPUInfo("RX 7900 XTX", 24, 384, "RDNA 3", 2022, 999, 355, stream_processors=6144),
        "rx 7900 xt": GPUInfo("RX 7900 XT", 20, 320, "RDNA 3", 2022, 899, 315, stream_processors=5376),
        "rx 7900 gre": GPUInfo("RX 7900 GRE", 16, 256, "RDNA 3", 2024, 549, 260, stream_processors=5120),
        "rx 7800 xt": GPUInfo("RX 7800 XT", 16, 256, "RDNA 3", 2023, 499, 263, stream_processors=3840),
        "rx 7700 xt": GPUInfo("RX 7700 XT", 12, 192, "RDNA 3", 2023, 449, 245, stream_processors=3456),
        "rx 7600 xt": GPUInfo("RX 7600 XT", 16, 128, "RDNA 3", 2024, 329, 190, stream_processors=2048),
        "rx 7600": GPUInfo("RX 7600", 8, 128, "RDNA 3", 2023, 269, 165, stream_processors=2048),
        
        # RX 9000 series (RDNA 4, анонсированы CES 2025)
        "rx 9070 xt": GPUInfo("RX 9070 XT", 16, 256, "RDNA 4", 2025, 599, 250, stream_processors=4096),
        "rx 9070": GPUInfo("RX 9070", 12, 192, "RDNA 4", 2025, 499, 220, stream_processors=3584),
        
        # RX 6000 series (RDNA 2)
        "rx 6950 xt": GPUInfo("RX 6950 XT", 16, 256, "RDNA 2", 2022, 1099, 335, stream_processors=5120),
        "rx 6900 xt": GPUInfo("RX 6900 XT", 16, 256, "RDNA 2", 2020, 999, 300, stream_processors=5120),
        "rx 6800 xt": GPUInfo("RX 6800 XT", 16, 256, "RDNA 2", 2020, 649, 300, stream_processors=4608),
        "rx 6800": GPUInfo("RX 6800", 16, 256, "RDNA 2", 2020, 579, 250, stream_processors=3840),
        "rx 6750 xt": GPUInfo("RX 6750 XT", 12, 192, "RDNA 2", 2022, 549, 250, stream_processors=2560),
        "rx 6700 xt": GPUInfo("RX 6700 XT", 12, 192, "RDNA 2", 2021, 479, 230, stream_processors=2560),
        "rx 6650 xt": GPUInfo("RX 6650 XT", 8, 128, "RDNA 2", 2022, 399, 180, stream_processors=2048),
        "rx 6600 xt": GPUInfo("RX 6600 XT", 8, 128, "RDNA 2", 2021, 379, 160, stream_processors=2048),
        "rx 6600": GPUInfo("RX 6600", 8, 128, "RDNA 2", 2021, 329, 132, stream_processors=1792),
    }
    
    # Intel Arc
    INTEL_GPUS: dict[str, GPUInfo] = {
        "arc a770": GPUInfo("Arc A770", 16, 256, "Alchemist", 2022, 349, 225),
        "arc a750": GPUInfo("Arc A750", 8, 256, "Alchemist", 2022, 289, 225),
        "arc a580": GPUInfo("Arc A580", 8, 192, "Alchemist", 2023, 179, 185),
        "arc a380": GPUInfo("Arc A380", 6, 96, "Alchemist", 2022, 139, 75),
    }
    
    # Архитектуры и их годы
    ARCHITECTURES = {
        # NVIDIA
        "kepler": {"vendor": "NVIDIA", "year": 2012, "process": "28nm"},
        "maxwell": {"vendor": "NVIDIA", "year": 2014, "process": "28nm"},
        "pascal": {"vendor": "NVIDIA", "year": 2016, "process": "16nm"},
        "turing": {"vendor": "NVIDIA", "year": 2018, "process": "12nm"},
        "ampere": {"vendor": "NVIDIA", "year": 2020, "process": "8nm"},
        "ada lovelace": {"vendor": "NVIDIA", "year": 2022, "process": "4nm"},
        "hopper": {"vendor": "NVIDIA", "year": 2022, "process": "4nm"},  # Datacenter
        "blackwell": {"vendor": "NVIDIA", "year": 2025, "process": "4nm"},  # RTX 50 series
        
        # AMD GPU
        "gcn": {"vendor": "AMD", "year": 2012, "process": "28nm"},
        "rdna": {"vendor": "AMD", "year": 2019, "process": "7nm"},
        "rdna 2": {"vendor": "AMD", "year": 2020, "process": "7nm"},
        "rdna 3": {"vendor": "AMD", "year": 2022, "process": "5nm"},
        "rdna 4": {"vendor": "AMD", "year": 2025, "process": "4nm"},
        
        # AMD CPU
        "zen": {"vendor": "AMD", "year": 2017, "process": "14nm"},
        "zen+": {"vendor": "AMD", "year": 2018, "process": "12nm"},
        "zen 2": {"vendor": "AMD", "year": 2019, "process": "7nm"},
        "zen 3": {"vendor": "AMD", "year": 2020, "process": "7nm"},
        "zen 4": {"vendor": "AMD", "year": 2022, "process": "5nm"},
        "zen 5": {"vendor": "AMD", "year": 2024, "process": "4nm"},
        
        # Intel
        "skylake": {"vendor": "Intel", "year": 2015, "process": "14nm"},
        "coffee lake": {"vendor": "Intel", "year": 2017, "process": "14nm"},
        "alder lake": {"vendor": "Intel", "year": 2021, "process": "Intel 7"},
        "raptor lake": {"vendor": "Intel", "year": 2022, "process": "Intel 7"},
        "meteor lake": {"vendor": "Intel", "year": 2023, "process": "Intel 4"},
        "arrow lake": {"vendor": "Intel", "year": 2024, "process": "Intel 20A"},
    }
    
    def __init__(self):
        # Объединяем все GPU в один словарь
        self.all_gpus = {
            **self.NVIDIA_GPUS,
            **self.AMD_GPUS,
            **self.INTEL_GPUS,
        }
        # Объединяем все CPU
        self.all_cpus = {
            **self.INTEL_CPUS,
            **self.AMD_CPUS,
        }
    
    def get_gpu(self, name: str) -> Optional[GPUInfo]:
        """
        Получить информацию о видеокарте.
        
        Args:
            name: Название (например "RTX 4070", "RX 7800 XT")
            
        Returns:
            GPUInfo или None если не найдено
        """
        key = name.lower().strip()
        return self.all_gpus.get(key)
    
    def get_architecture(self, name: str) -> Optional[dict]:
        """
        Получить информацию об архитектуре.
        
        Args:
            name: Название архитектуры
            
        Returns:
            Словарь с информацией или None
        """
        key = name.lower().strip()
        return self.ARCHITECTURES.get(key)
    
    def is_valid_gpu(self, name: str) -> bool:
        """Проверяет, существует ли такая видеокарта."""
        return self.get_gpu(name) is not None
    
    def format_gpu_info(self, gpu: GPUInfo) -> str:
        """Форматирует информацию о GPU для ответа."""
        parts = [
            f"{gpu.name}:",
            f"• VRAM: {gpu.vram_gb}GB",
            f"• Шина: {gpu.bus_width}-bit",
            f"• Архитектура: {gpu.architecture}",
            f"• Год: {gpu.release_year}",
        ]
        
        if gpu.tdp_watts:
            parts.append(f"• TDP: {gpu.tdp_watts}W")
        
        if gpu.cuda_cores:
            parts.append(f"• CUDA: {gpu.cuda_cores}")
        elif gpu.stream_processors:
            parts.append(f"• SP: {gpu.stream_processors}")
        
        if gpu.msrp_usd:
            parts.append(f"• MSRP: ${gpu.msrp_usd}")
        
        return "\n".join(parts)
    
    def search_gpu(self, query: str) -> list[GPUInfo]:
        """
        Поиск видеокарт по запросу.
        
        Args:
            query: Поисковый запрос (часть названия)
            
        Returns:
            Список подходящих GPU
        """
        query_lower = query.lower()
        results = []
        
        for key, gpu in self.all_gpus.items():
            if query_lower in key or query_lower in gpu.name.lower():
                results.append(gpu)
        
        return results
    
    def get_generation_gpus(self, architecture: str) -> list[GPUInfo]:
        """Получить все GPU определённой архитектуры."""
        arch_lower = architecture.lower()
        return [
            gpu for gpu in self.all_gpus.values()
            if gpu.architecture.lower() == arch_lower
        ]
    
    def compare_gpus(self, gpu1_name: str, gpu2_name: str) -> Optional[str]:
        """
        Сравнить две видеокарты.
        
        Returns:
            Строка со сравнением или None если карты не найдены
        """
        gpu1 = self.get_gpu(gpu1_name)
        gpu2 = self.get_gpu(gpu2_name)
        
        if not gpu1 or not gpu2:
            return None
        
        lines = [f"Сравнение {gpu1.name} vs {gpu2.name}:", ""]
        
        # VRAM
        vram_winner = gpu1.name if gpu1.vram_gb > gpu2.vram_gb else gpu2.name
        lines.append(f"VRAM: {gpu1.vram_gb}GB vs {gpu2.vram_gb}GB → {vram_winner}")
        
        # Шина
        bus_winner = gpu1.name if gpu1.bus_width > gpu2.bus_width else gpu2.name
        lines.append(f"Шина: {gpu1.bus_width}-bit vs {gpu2.bus_width}-bit → {bus_winner}")
        
        # Архитектура
        lines.append(f"Архитектура: {gpu1.architecture} vs {gpu2.architecture}")
        
        # TDP
        if gpu1.tdp_watts and gpu2.tdp_watts:
            tdp_winner = gpu1.name if gpu1.tdp_watts < gpu2.tdp_watts else gpu2.name
            lines.append(f"TDP: {gpu1.tdp_watts}W vs {gpu2.tdp_watts}W → {tdp_winner} (меньше = лучше)")
        
        return "\n".join(lines)
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ CPU
    # =========================================================================
    
    def get_cpu(self, name: str) -> Optional[CPUInfo]:
        """Получить информацию о процессоре."""
        key = name.lower().strip()
        return self.all_cpus.get(key)
    
    def is_valid_cpu(self, name: str) -> bool:
        """Проверяет, существует ли такой процессор."""
        return self.get_cpu(name) is not None
    
    def format_cpu_info(self, cpu: CPUInfo) -> str:
        """Форматирует информацию о CPU для ответа."""
        parts = [
            f"{cpu.name}:",
            f"• Ядра/Потоки: {cpu.cores}/{cpu.threads}",
            f"• Архитектура: {cpu.architecture}",
            f"• Сокет: {cpu.socket}",
            f"• Год: {cpu.release_year}",
        ]
        
        if cpu.boost_clock_ghz:
            parts.append(f"• Частота: {cpu.base_clock_ghz}-{cpu.boost_clock_ghz} GHz")
        
        if cpu.tdp_watts:
            parts.append(f"• TDP: {cpu.tdp_watts}W")
        
        if cpu.cache_l3_mb:
            parts.append(f"• L3 кэш: {cpu.cache_l3_mb}MB")
        
        if cpu.has_igpu:
            parts.append("• Встроенная графика: Да")
        
        return "\n".join(parts)
    
    def get_cpus_by_socket(self, socket: str) -> list[CPUInfo]:
        """Получить все CPU для определённого сокета."""
        socket_lower = socket.lower()
        return [
            cpu for cpu in self.all_cpus.values()
            if cpu.socket.lower() == socket_lower
        ]
    
    def get_gaming_cpu_recommendations(self) -> list[str]:
        """Топ CPU для гейминга 2025."""
        return [
            "Ryzen 7 9800X3D — лучший для игр (3D V-Cache)",
            "Ryzen 7 7800X3D — отличный выбор, дешевле 9800X3D",
            "Core Ultra 9 285K — топ Intel для игр и продакшна",
            "Ryzen 5 9600X — лучший бюджетный для игр",
            "i5-14600K — универсальный Intel среднего класса",
        ]
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ ПЛАТФОРМ
    # =========================================================================
    
    def get_platform(self, name: str) -> Optional[PlatformInfo]:
        """Получить информацию о платформе."""
        key = name.lower().strip()
        return self.PLATFORMS.get(key)
    
    def format_platform_info(self, platform: PlatformInfo) -> str:
        """Форматирует информацию о платформе."""
        return (
            f"{platform.name}:\n"
            f"• Сокет: {platform.socket}\n"
            f"• Чипсеты: {', '.join(platform.chipsets)}\n"
            f"• Память: {platform.memory_type}\n"
            f"• PCIe: {platform.pcie_version}\n"
            f"• {platform.description}\n"
            f"• Рекомендуется для: {platform.recommended_for}"
        )
    
    def get_current_platforms(self) -> list[str]:
        """Актуальные платформы 2025."""
        return [
            "AM5 (AMD) — Ryzen 7000/9000, DDR5, PCIe 5.0, долгоживущая",
            "LGA1851 (Intel) — Core Ultra, DDR5, PCIe 5.0, хай-энд",
            "LGA1700 (Intel) — Core 12-14 Gen, DDR4/DDR5, массовый сегмент",
        ]
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ СБОРОК
    # =========================================================================
    
    def get_build_recommendation(self, tier: str) -> Optional[dict]:
        """Получить рекомендацию по сборке."""
        return self.BUILD_RECOMMENDATIONS.get(tier)
    
    def format_build_recommendation(self, tier: str) -> Optional[str]:
        """Форматирует рекомендацию по сборке."""
        build = self.get_build_recommendation(tier)
        if not build:
            return None
        
        lines = [f"🖥️ {build['name']}:", ""]
        lines.append(f"CPU: {', '.join(build['cpu'])}")
        lines.append(f"Платформа: {build['platform']}")
        lines.append(f"GPU: {', '.join(build['gpu'])}")
        lines.append(f"RAM: {build['ram']}")
        lines.append(f"SSD: {build['storage']}")
        lines.append(f"БП: {build['psu']}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ СТАНДАРТОВ
    # =========================================================================
    
    def get_ram_info(self, ram_type: str) -> Optional[RAMInfo]:
        """Получить информацию о типе памяти."""
        return self.RAM_STANDARDS.get(ram_type.lower())
    
    def get_storage_info(self, interface: str) -> Optional[StorageInfo]:
        """Получить информацию о типе накопителя."""
        return self.STORAGE_STANDARDS.get(interface.lower())
    
    def get_2025_summary(self) -> str:
        """Краткая сводка по железу 2025."""
        return """
🖥️ БАЗА ПО ПК-ЖЕЛЕЗУ 2025:

ПЛАТФОРМЫ:
• Intel LGA1851 + Core Ultra — хай-энд, DDR5, PCIe 5.0
• Intel LGA1700 + Core 12-14 — массовый сегмент, DDR4/DDR5
• AMD AM5 + Ryzen 7000/9000 — универсал, DDR5-6000 EXPO, долгоживущая

ВИДЕОКАРТЫ:
• NVIDIA RTX 50 (Blackwell) — флагманы, DLSS 4, до 32GB GDDR7
• NVIDIA RTX 40 (Ada) — мейнстрим, 4070/4070 Ti/4060
• AMD RX 9000 (RDNA 4) — новые, FSR 4, улучшенные RT
• AMD RX 7000 (RDNA 3) — средний сегмент

ПАМЯТЬ:
• DDR5 — стандарт 2025, 32GB (2x16) 5600-6400 MT/s
• DDR4 — только для старых платформ

НАКОПИТЕЛИ:
• NVMe Gen4 — мейнстрим, 7000 MB/s
• NVMe Gen5 — топ, 12000+ MB/s, для продакшна

БП:
• ATX 3.1 с 12V-2x6 — новый стандарт для RTX 40/50
• 80+ Gold/Platinum рекомендуется
"""
    
    # =========================================================================
    # МЕТОДЫ ДЛЯ СОФТА И ТЮНИНГА
    # =========================================================================
    
    def get_os_info(self, os_name: str) -> Optional[dict]:
        """Получить информацию об ОС."""
        key = os_name.lower().replace(" ", "_").replace("-", "_")
        # Пробуем разные варианты ключа
        for k in [key, f"windows_{key}", f"linux_{key}"]:
            if k in self.OPERATING_SYSTEMS:
                return self.OPERATING_SYSTEMS[k]
        return None
    
    def get_tuning_software(self, category: Optional[str] = None) -> list[SoftwareInfo]:
        """Получить список софта для тюнинга."""
        all_software = {
            **self.SOFTWARE_TUNING,
            **self.SOFTWARE_MONITORING,
            **self.SOFTWARE_STRESS_TEST,
            **self.SOFTWARE_DRIVERS,
        }
        
        if category:
            return [s for s in all_software.values() if s.category == category]
        return list(all_software.values())
    
    def get_tuning_guide(self, component: str) -> Optional[TuningGuide]:
        """Получить гайд по тюнингу компонента."""
        component_lower = component.lower()
        
        # Маппинг запросов к ключам
        mappings = {
            "amd": "cpu_amd_zen4_zen5",
            "ryzen": "cpu_amd_zen4_zen5",
            "zen": "cpu_amd_zen4_zen5",
            "intel": "cpu_intel_13_14_ultra",
            "core": "cpu_intel_13_14_ultra",
            "nvidia": "gpu_nvidia_rtx40_50",
            "rtx": "gpu_nvidia_rtx40_50",
            "radeon": "gpu_amd_rx7000_9000",
            "rx": "gpu_amd_rx7000_9000",
            "ddr5": "ram_ddr5",
            "ram": "ram_ddr5",
            "память": "ram_ddr5",
        }
        
        for keyword, guide_key in mappings.items():
            if keyword in component_lower:
                return self.TUNING_GUIDES.get(guide_key)
        
        return self.TUNING_GUIDES.get(component_lower)
    
    def format_tuning_guide(self, guide: TuningGuide) -> str:
        """Форматирует гайд по тюнингу."""
        lines = [f"🔧 {guide.component}", f"Метод: {guide.method}", ""]
        
        lines.append("Шаги:")
        for step in guide.steps:
            lines.append(f"  {step}")
        
        lines.append("")
        lines.append(f"Инструменты: {', '.join(guide.tools)}")
        
        if guide.warnings:
            lines.append("")
            lines.append("⚠️ Важно:")
            for warn in guide.warnings:
                lines.append(f"  • {warn}")
        
        return "\n".join(lines)
    
    def get_windows_setup_checklist(self) -> str:
        """Чеклист после установки Windows."""
        lines = ["📋 После установки Windows:", ""]
        lines.extend(self.WINDOWS_SETUP_CHECKLIST)
        return "\n".join(lines)
    
    def get_stability_checklist(self) -> str:
        """Чеклист проверки стабильности."""
        lines = ["✅ Проверка стабильности:", ""]
        for component, check in self.STABILITY_CHECKLIST.items():
            lines.append(f"• {component.upper()}: {check}")
        return "\n".join(lines)
    
    def get_software_summary(self) -> str:
        """Краткая сводка по софту 2025."""
        return """
🛠️ СОФТВЕРНАЯ БАЗА 2025:

ОС:
• Windows 11 24H2/25H1 — основная, обязательна для Zen 5/Arrow Lake
• Windows 12 — НЕ ВЫШЛА, перенесена на 2026/2027
• Linux Gaming: Bazzite (SteamOS для ПК), Nobara (Fedora с патчами)

ТЮНИНГ:
• NVIDIA App — замена GeForce Experience, без логина
• MSI Afterburner + RTSS — андервольт и OSD для NVIDIA
• FanControl — настройка вентиляторов

МОНИТОРИНГ:
• HWInfo64 — все сенсоры, WHEA Errors
• CapFrameX — анализ плавности, 1% low

СТРЕСС-ТЕСТЫ:
• OCCT — лучший комбайн 2025
• TestMem5 + Anta777 — тест DDR5
• Y-Cruncher — убийца нестабильных CO

ДРАЙВЕРЫ:
• DDU — чистка при смене видеокарты
• NVCleanstall — драйвер NVIDIA без мусора

МЕТА 2025:
Классический разгон мёртв. Мета — андервольт и кривые.
Железо выжато на 99% по частотам, но с запасом по вольтажу.
Убираешь лишний вольтаж = ниже температуры = выше буст.
"""


# Глобальный экземпляр
knowledge_base = KnowledgeBase()
