"""
Модуль для генерации QR-кодов для email-адресов
"""

import qrcode
from io import BytesIO
from PIL import Image


class QRGenerator:
    """Класс для генерации QR-кодов"""
    
    @staticmethod
    def generate_qr_for_email(email: str) -> BytesIO:
        """
        Генерирует QR-код для email-адреса
        
        Args:
            email: Email-адрес для кодирования
        
        Returns:
            BytesIO объект с изображением QR-кода
        """
        # Создаем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        qr.add_data(email)
        qr.make(fit=True)
        
        # Создаем изображение
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Сохраняем в BytesIO
        bio = BytesIO()
        bio.name = 'qr_code.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        
        return bio
    
    @staticmethod
    def generate_fancy_qr(email: str, with_logo: bool = False) -> BytesIO:
        """
        Генерирует более красивый QR-код
        
        Args:
            email: Email-адрес для кодирования
            with_logo: Добавить логотип в центр (опционально)
        
        Returns:
            BytesIO объект с изображением QR-кода
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        
        qr.add_data(email)
        qr.make(fit=True)
        
        # Создаем изображение с цветом
        img = qr.make_image(fill_color="#2196F3", back_color="white").convert('RGB')
        
        bio = BytesIO()
        bio.name = 'qr_code_fancy.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        
        return bio
