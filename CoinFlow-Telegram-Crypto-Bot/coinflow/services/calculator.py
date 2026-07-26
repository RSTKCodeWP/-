"""Calculator service with currency conversion support."""

import re
from typing import Optional
from ..utils.safe_calculator import SafeCalculator
from ..utils.logger import setup_logger

logger = setup_logger('calculator')


class Calculator:
    """Калькулятор с поддержкой конвертации валют."""
    
    def __init__(self, converter):
        self.converter = converter
        self.safe_calc = SafeCalculator()
        
    def calculate(self, expression: str, user_id: int = None) -> Optional[str]:
        """
        Вычислить выражение или конвертировать валюту.
        
        Args:
            expression: Mathematical expression or currency conversion
            user_id: User ID for currency conversion
        
        Returns:
            Result string or None if invalid
        """
        try:
            # Проверка на конвертацию валют
            match = re.match(
                r'([\d.]+)\s*([A-Z]{3})\s*(?:to|in|->|в)\s*([A-Z]{3})', 
                expression, 
                re.IGNORECASE
            )
            if match:
                amount = float(match.group(1))
                from_curr = match.group(2).upper()
                to_curr = match.group(3).upper()
                
                result = self.converter.convert(amount, from_curr, to_curr, user_id)
                if result:
                    logger.info(f"Conversion: {amount} {from_curr} = {result:.2f} {to_curr}")
                    return f"{amount} {from_curr} = {result:.2f} {to_curr}"
                return None
            
            # Обычное вычисление с безопасным калькулятором
            result = self.safe_calc.evaluate(expression)
            if result is not None:
                formatted = self.safe_calc.format_result(result)
                logger.info(f"Calculation: {expression} = {formatted}")
                return f"{expression} = {formatted}"
            
            return None
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return None
