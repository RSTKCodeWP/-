"""
Fact Checker Service — проверка ответов LLM на галлюцинации.

Анализирует ответ модели и сверяет с результатами поиска,
выявляя потенциальные выдумки.

**Feature: anti-hallucination-v1**
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.services.web_search import SearchResponse

logger = logging.getLogger(__name__)


@dataclass
class FactCheckResult:
    """Результат проверки фактов."""
    is_reliable: bool
    confidence: float  # 0.0 - 1.0
    warnings: list[str]
    hallucinated_items: list[str]  # Потенциально выдуманные факты
    verified_items: list[str]  # Подтверждённые факты


class FactChecker:
    """
    Проверяет ответы LLM на соответствие результатам поиска.
    
    Выявляет:
    - Несуществующие модели железа
    - Неверные характеристики
    - Выдуманные даты релизов
    """
    
    # Паттерны для извлечения упоминаний железа из текста
    HARDWARE_PATTERNS = [
        # NVIDIA
        r'\b(RTX|GTX)\s*(\d{3,4})\s*(Ti|Super|SUPER)?\b',
        r'\bGeForce\s*(RTX|GTX)?\s*(\d{3,4})\s*(Ti|Super)?\b',
        # AMD GPU
        r'\bRX\s*(\d{3,4})\s*(XT|XTX)?\b',
        r'\bRadeon\s*(RX)?\s*(\d{3,4})\s*(XT|XTX)?\b',
        # Intel GPU
        r'\bArc\s*(A\d{3,4})\b',
        # CPU Intel
        r'\b(Core\s*)?(i[3579])-?(\d{4,5}[A-Z]*)\b',
        # CPU AMD
        r'\bRyzen\s*(\d)\s*(\d{4}[A-Z]*)\b',
        # Архитектуры
        r'\b(Kepler|Maxwell|Pascal|Turing|Ampere|Ada|Lovelace|Hopper)\b',
        r'\b(Zen|Zen\s*[234]|Zen\s*4c|Zen\s*5)\b',
        r'\b(RDNA|RDNA\s*[23])\b',
    ]
    
    # Известные несуществующие модели (галлюцинации LLM)
    KNOWN_HALLUCINATIONS = {
        # Несуществующие RTX (выдуманные варианты)
        "rtx 4090 ti", "rtx 4080 ti super", "rtx 5060",
        "rtx 5050", "rtx 5040",
        # Несуществующие RX (AMD пропустила 8000 серию, сразу выпустила 9000)
        "rx 8900", "rx 8800", "rx 8700", "rx 8600", "rx 8500", "rx 8000",
        "rx 9000", "rx 9900", "rx 9080", "rx 9090",  # Таких нет, есть только 9070/9070 XT
        # Несуществующие архитектуры
        "zen 6", "zen6",
        # Выдуманные Intel
        "arc a880", "arc a890",
    }
    
    # Актуальные модели (для быстрой проверки без поиска)
    KNOWN_VALID_MODELS = {
        # NVIDIA RTX 50 series (Blackwell, анонсированы январь 2025)
        "rtx 5090", "rtx 5080", "rtx 5070 ti", "rtx 5070",
        # NVIDIA RTX 40 series (Ada Lovelace)
        "rtx 4090", "rtx 4080 super", "rtx 4080", "rtx 4070 ti super",
        "rtx 4070 ti", "rtx 4070 super", "rtx 4070", "rtx 4060 ti", "rtx 4060",
        # NVIDIA RTX 30 series (Ampere)
        "rtx 3090 ti", "rtx 3090", "rtx 3080 ti", "rtx 3080", "rtx 3070 ti",
        "rtx 3070", "rtx 3060 ti", "rtx 3060", "rtx 3050",
        # AMD RX 9000 series (RDNA 4, анонсированы CES 2025)
        "rx 9070 xt", "rx 9070",
        # AMD RX 7000 series (RDNA 3)
        "rx 7900 xtx", "rx 7900 xt", "rx 7900 gre", "rx 7800 xt", "rx 7700 xt",
        "rx 7600 xt", "rx 7600",
        # AMD RX 6000 series (RDNA 2)
        "rx 6950 xt", "rx 6900 xt", "rx 6800 xt", "rx 6800", "rx 6750 xt",
        "rx 6700 xt", "rx 6650 xt", "rx 6600 xt", "rx 6600", "rx 6500 xt",
        # Intel Arc
        "arc a770", "arc a750", "arc a580", "arc a380",
    }
    
    # Актуальные CPU
    KNOWN_VALID_CPUS = {
        # Intel Core Ultra (Arrow Lake)
        "core ultra 9 285k", "core ultra 7 265k", "core ultra 5 245k",
        # Intel Raptor Lake
        "i9-14900k", "i9-14900kf", "i7-14700k", "i7-14700kf",
        "i5-14600k", "i5-14600kf", "i5-14400", "i5-12400",
        # AMD Ryzen 9000 (Zen 5)
        "ryzen 9 9950x", "ryzen 9 9900x", "ryzen 7 9800x3d",
        "ryzen 7 9700x", "ryzen 5 9600x",
        # AMD Ryzen 7000 (Zen 4)
        "ryzen 9 7950x", "ryzen 9 7900x", "ryzen 7 7800x3d",
        "ryzen 7 7700x", "ryzen 5 7600x", "ryzen 5 7600",
        # AMD Ryzen 5000 (Zen 3) - всё ещё актуальны
        "ryzen 7 5800x3d", "ryzen 5 5600x", "ryzen 5 5600",
        # Threadripper
        "threadripper 9980x", "threadripper 7980x",
    }
    
    # Актуальные платформы
    KNOWN_VALID_PLATFORMS = {
        "am5", "am4", "lga1700", "lga1851", "trx50", "str5",
        "b650", "b650e", "x670", "x670e", "x870", "x870e",
        "b660", "z690", "b760", "z790", "z890", "b860",
        "b450", "b550", "x570",
    }
    
    def __init__(self):
        pass
    
    def check_response(
        self, 
        response: str, 
        search_results: Optional[SearchResponse] = None
    ) -> FactCheckResult:
        """
        Проверяет ответ LLM на потенциальные галлюцинации.
        
        Args:
            response: Ответ модели
            search_results: Результаты поиска для сверки (опционально)
            
        Returns:
            FactCheckResult с оценкой надёжности
        """
        warnings = []
        hallucinated = []
        verified = []
        confidence = 1.0
        
        response_lower = response.lower()
        
        # 1. Проверяем на известные галлюцинации
        for hallucination in self.KNOWN_HALLUCINATIONS:
            if hallucination in response_lower:
                hallucinated.append(hallucination.upper())
                confidence -= 0.3
                logger.warning(f"[FACT CHECK] Known hallucination detected: {hallucination}")
        
        # 2. Извлекаем упоминания железа
        mentioned_hardware = self._extract_hardware_mentions(response)
        
        # 3. Проверяем каждое упоминание
        for hw in mentioned_hardware:
            hw_lower = hw.lower()
            
            # Проверяем в известных валидных
            if hw_lower in self.KNOWN_VALID_MODELS:
                verified.append(hw)
                continue
            
            # Проверяем в результатах поиска
            if search_results and self._is_in_search_results(hw, search_results):
                verified.append(hw)
                continue
            
            # Не нашли подтверждения — подозрительно
            if not self._looks_like_valid_model(hw):
                hallucinated.append(hw)
                confidence -= 0.2
                warnings.append(f"Не удалось подтвердить: {hw}")
        
        # 4. Проверяем на противоречия с поиском
        if search_results:
            contradictions = self._find_contradictions(response, search_results)
            for contradiction in contradictions:
                warnings.append(contradiction)
                confidence -= 0.15
        
        # Нормализуем confidence
        confidence = max(0.0, min(1.0, confidence))
        
        return FactCheckResult(
            is_reliable=confidence >= 0.6 and len(hallucinated) == 0,
            confidence=confidence,
            warnings=warnings,
            hallucinated_items=hallucinated,
            verified_items=verified
        )
    
    def _extract_hardware_mentions(self, text: str) -> list[str]:
        """Извлекает упоминания железа из текста."""
        mentions = []
        
        for pattern in self.HARDWARE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Собираем группы в строку
                    hw_name = " ".join(str(g) for g in match if g).strip()
                else:
                    hw_name = match
                
                if hw_name and len(hw_name) > 2:
                    mentions.append(hw_name)
        
        return list(set(mentions))
    
    def _is_in_search_results(self, hardware: str, search_results: SearchResponse) -> bool:
        """Проверяет, упоминается ли железо в результатах поиска."""
        hw_lower = hardware.lower()
        
        for result in search_results.results:
            text = f"{result.title} {result.snippet}".lower()
            if hw_lower in text:
                return True
        
        return False
    
    def _looks_like_valid_model(self, hardware: str) -> bool:
        """
        Эвристическая проверка — похоже ли на реальную модель.
        
        Проверяет базовые паттерны номенклатуры.
        """
        hw_lower = hardware.lower()
        
        # RTX/GTX должны иметь 4 цифры
        if "rtx" in hw_lower or "gtx" in hw_lower:
            numbers = re.findall(r'\d+', hw_lower)
            if numbers:
                num = int(numbers[0])
                # RTX: 2060-5090, GTX: 1050-1660
                if 2060 <= num <= 5090 or 1050 <= num <= 1660:
                    return True
        
        # RX должны иметь 4 цифры
        if "rx" in hw_lower:
            numbers = re.findall(r'\d+', hw_lower)
            if numbers:
                num = int(numbers[0])
                # RX: 5000-9070 (включая RDNA 4)
                if 5000 <= num <= 9070:
                    return True
        
        return False
    
    def _find_contradictions(
        self, 
        response: str, 
        search_results: SearchResponse
    ) -> list[str]:
        """Ищет противоречия между ответом и результатами поиска."""
        contradictions = []
        
        # Извлекаем числовые характеристики из ответа
        # Например: "8GB VRAM", "256-bit", "7nm"
        response_specs = self._extract_specs(response)
        search_text = " ".join(f"{r.title} {r.snippet}" for r in search_results.results)
        search_specs = self._extract_specs(search_text)
        
        # Сравниваем ключевые характеристики
        for spec_type, response_value in response_specs.items():
            if spec_type in search_specs:
                search_value = search_specs[spec_type]
                if response_value != search_value:
                    contradictions.append(
                        f"Возможное расхождение в {spec_type}: "
                        f"ответ={response_value}, поиск={search_value}"
                    )
        
        return contradictions
    
    def _extract_specs(self, text: str) -> dict[str, str]:
        """Извлекает технические характеристики из текста."""
        specs = {}
        
        # VRAM
        vram_match = re.search(r'(\d+)\s*(?:GB|ГБ)\s*(?:VRAM|видеопамят)', text, re.IGNORECASE)
        if vram_match:
            specs['vram'] = vram_match.group(1) + "GB"
        
        # Шина памяти
        bus_match = re.search(r'(\d+)-?(?:bit|бит)', text, re.IGNORECASE)
        if bus_match:
            specs['bus'] = bus_match.group(1) + "-bit"
        
        # Техпроцесс
        nm_match = re.search(r'(\d+)\s*(?:nm|нм)', text, re.IGNORECASE)
        if nm_match:
            specs['process'] = nm_match.group(1) + "nm"
        
        return specs
    
    def format_warnings(self, result: FactCheckResult) -> str:
        """
        Форматирует предупреждения для добавления к ответу.
        
        Returns:
            Строка с предупреждениями или пустая строка
        """
        if result.is_reliable and not result.warnings:
            return ""
        
        parts = []
        
        if result.hallucinated_items:
            parts.append(
                f"⚠️ Не уверен насчёт: {', '.join(result.hallucinated_items)}"
            )
        
        if result.confidence < 0.5:
            parts.append("⚠️ Инфа может быть неточной, лучше перепроверь")
        
        return "\n".join(parts)


# Глобальный экземпляр
fact_checker = FactChecker()
