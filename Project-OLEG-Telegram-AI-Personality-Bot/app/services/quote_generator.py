"""
Quote Generator Service - QuotAI style with transparent background.
"""

import logging
import random
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class QuoteTheme(Enum):
    DARK = "dark"
    LIGHT = "light"
    AUTO = "auto"


@dataclass
class QuoteStyle:
    theme: QuoteTheme = QuoteTheme.DARK
    gradient: Optional[Tuple[str, str]] = None
    font_family: str = "DejaVuSans"
    avatar_style: str = "circle"


@dataclass
class QuoteImage:
    image_data: bytes
    format: str
    width: int
    height: int


@dataclass
class MessageData:
    text: str
    username: str
    avatar_url: Optional[str] = None
    avatar_data: Optional[bytes] = None
    timestamp: Optional[str] = None
    media_data: Optional[bytes] = None  # Photo/sticker data


# QuotAI style colors
COLORS = {
    "bubble": (47, 50, 55),               # Dark gray bubble
    "text": (255, 255, 255),              # White text
    "username_colors": [
        (111, 201, 255),   # Light blue
        (255, 179, 102),   # Orange  
        (178, 132, 255),   # Purple
        (102, 255, 179),   # Green
        (255, 102, 153),   # Pink
        (255, 230, 102),   # Yellow
        (102, 255, 255),   # Cyan
        (255, 153, 204),   # Light pink
    ],
}

# Render at 2x resolution for better quality, then downscale for Telegram
RENDER_SCALE = 2  # 2x supersampling for crisp text
MAX_IMAGE_WIDTH = 512 * RENDER_SCALE  # 1024px render width
MAX_IMAGE_HEIGHT = 512 * RENDER_SCALE  # 1024px render height
MAX_CHAIN_MESSAGES = 10


class QuoteGeneratorService:
    
    def __init__(self):
        self._load_fonts()
    
    def _load_fonts(self):
        font_paths = [
            "fonts/", "/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/TTF/",
            "/Library/Fonts/", "/System/Library/Fonts/", "C:/Windows/Fonts/",
        ]
        fonts = [("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"), ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf")]
        
        def find(name):
            import os
            for p in font_paths:
                if os.path.exists(os.path.join(p, name)):
                    return os.path.join(p, name)
            return None
        
        for reg, bold in fonts:
            rp = find(reg)
            if rp:
                try:
                    # Scaled fonts for 2x rendering
                    self.text_font = ImageFont.truetype(rp, 40)  # 20 * 2
                    self.text_font_small = ImageFont.truetype(rp, 34)  # 17 * 2
                    self.username_font = ImageFont.truetype(find(bold) or rp, 36)  # 18 * 2
                    return
                except:
                    pass
        
        self.text_font = self.text_font_small = self.username_font = ImageFont.load_default()

    def _get_username_color(self, username: str) -> Tuple[int, int, int]:
        import hashlib
        h = int(hashlib.md5(username.encode()).hexdigest()[:8], 16)
        return COLORS["username_colors"][h % len(COLORS["username_colors"])]
    
    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        words = text.split()
        lines, current = [], []
        
        for word in words:
            test = ' '.join(current + [word])
            try:
                w = font.getbbox(test)[2]
            except:
                w = len(test) * 8
            
            if w <= max_width:
                current.append(word)
            else:
                if current:
                    lines.append(' '.join(current))
                current = [word]
        
        if current:
            lines.append(' '.join(current))
        return lines or ['']

    def _draw_rounded_rect(self, draw, coords, radius, fill):
        x1, y1, x2, y2 = coords
        # Main body
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        # Corners
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)

    def _draw_avatar(self, img, x, y, size, username, avatar_data=None):
        if avatar_data:
            try:
                av = Image.open(BytesIO(avatar_data)).convert('RGBA')
                av = av.resize((size, size), Image.Resampling.LANCZOS)
                
                mask = Image.new('L', (size, size), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
                av.putalpha(mask)
                
                img.paste(av, (x, y), av)
                return
            except Exception as e:
                logger.debug(f"Avatar load failed: {e}")
        
        # Placeholder
        draw = ImageDraw.Draw(img)
        color = self._get_username_color(username)
        draw.ellipse([x, y, x + size, y + size], fill=color)
        
        initial = username[0].upper() if username else "?"
        try:
            bbox = self.username_font.getbbox(initial)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except:
            tw, th = 10, 10
        draw.text((x + (size - tw) // 2, y + (size - th) // 2 - 2), initial, font=self.username_font, fill=(255, 255, 255))

    async def render_quote(
        self,
        text: str,
        username: str,
        avatar_url: Optional[str] = None,
        style: Optional[QuoteStyle] = None,
        timestamp: Optional[str] = None,
        avatar_data: Optional[bytes] = None,
        custom_title: Optional[str] = None,
        full_name: Optional[str] = None,
        media_data: Optional[bytes] = None,
    ) -> QuoteImage:
        """Render QuotAI-style quote with transparent background."""
        
        # All sizes scaled by RENDER_SCALE for high-res output
        padding = 24  # 12 * 2
        avatar_size = 84  # 42 * 2
        bubble_padding = 24  # 12 * 2
        bubble_radius = 36  # 18 * 2
        gap = 20  # 10 * 2
        
        max_text_w = MAX_IMAGE_WIDTH - padding - avatar_size - gap - bubble_padding * 2 - padding
        lines = self._wrap_text(text, self.text_font, max_text_w) if text else []
        
        display_name = full_name or username or "Anonymous"
        try:
            name_h = self.username_font.getbbox(display_name)[3]
            line_h = self.text_font.getbbox("Ayg")[3] + 6  # 3 * 2
        except:
            name_h, line_h = 36, 46  # 18 * 2, 23 * 2
        
        # Calculate media height
        media_h = 0
        media_img = None
        if media_data:
            try:
                media_img = Image.open(BytesIO(media_data)).convert('RGBA')
                # Scale to fit bubble width
                max_media_w = max_text_w
                ratio = min(max_media_w / media_img.width, 400 / media_img.height)  # 200 * 2
                new_w = int(media_img.width * ratio)
                new_h = int(media_img.height * ratio)
                media_img = media_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                media_h = new_h + 16  # 8 * 2
            except:
                media_img = None
        
        text_h = len(lines) * line_h if lines else 0
        content_h = name_h + 12 + media_h + text_h  # 6 * 2
        bubble_h = content_h + bubble_padding * 2
        
        img_h = max(padding * 2 + bubble_h, padding * 2 + avatar_size)
        img_w = MAX_IMAGE_WIDTH
        
        # Transparent background (RGBA)
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Avatar
        avatar_x = padding
        avatar_y = padding
        self._draw_avatar(img, avatar_x, avatar_y, avatar_size, username, avatar_data)
        
        # Bubble
        bubble_x = avatar_x + avatar_size + gap
        bubble_y = padding
        bubble_w = img_w - bubble_x - padding
        
        self._draw_rounded_rect(draw, (bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h), bubble_radius, COLORS["bubble"])
        
        # Username
        username_color = self._get_username_color(username)
        draw.text((bubble_x + bubble_padding, bubble_y + bubble_padding), display_name, font=self.username_font, fill=username_color)
        
        content_y = bubble_y + bubble_padding + name_h + 12  # 6 * 2
        
        # Media
        if media_img:
            img.paste(media_img, (bubble_x + bubble_padding, content_y), media_img if media_img.mode == 'RGBA' else None)
            content_y += media_h
        
        # Text
        for line in lines:
            draw.text((bubble_x + bubble_padding, content_y), line, font=self.text_font, fill=COLORS["text"])
            content_y += line_h
        
        # Downscale from 2x to final 512px max for Telegram stickers
        # This gives us crisp text through supersampling
        final_w = img_w // RENDER_SCALE
        final_h = img_h // RENDER_SCALE
        img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
        
        # Save as WebP with transparency
        output = BytesIO()
        img.save(output, format='WEBP', quality=95)
        output.seek(0)
        
        return QuoteImage(image_data=output.getvalue(), format='webp', width=final_w, height=final_h)

    async def render_quote_chain(self, messages: List[MessageData], style: Optional[QuoteStyle] = None) -> QuoteImage:
        if len(messages) > MAX_CHAIN_MESSAGES:
            messages = messages[:MAX_CHAIN_MESSAGES]
        if not messages:
            return await self.render_quote("(empty)", "System", style=style)
        
        # All sizes scaled by RENDER_SCALE for high-res output
        padding = 20  # 10 * 2
        avatar_size = 72  # 36 * 2
        bubble_padding = 20  # 10 * 2
        bubble_radius = 32  # 16 * 2
        gap = 16  # 8 * 2
        msg_gap = 12  # 6 * 2
        
        max_text_w = MAX_IMAGE_WIDTH - padding - avatar_size - gap - bubble_padding * 2 - padding
        
        total_h = padding * 2
        msg_data = []
        
        for msg in messages:
            lines = self._wrap_text(msg.text, self.text_font_small, max_text_w) if msg.text else []
            try:
                name_h = self.username_font.getbbox(msg.username)[3]
                line_h = self.text_font_small.getbbox("Ayg")[3] + 4  # 2 * 2
            except:
                name_h, line_h = 32, 40  # 16 * 2, 20 * 2
            
            # Media
            media_h = 0
            media_img = None
            if msg.media_data:
                try:
                    media_img = Image.open(BytesIO(msg.media_data)).convert('RGBA')
                    ratio = min(max_text_w / media_img.width, 300 / media_img.height)  # 150 * 2
                    media_img = media_img.resize((int(media_img.width * ratio), int(media_img.height * ratio)), Image.Resampling.LANCZOS)
                    media_h = media_img.height + 12  # 6 * 2
                except:
                    media_img = None
            
            text_h = len(lines) * line_h if lines else 0
            bubble_h = bubble_padding * 2 + name_h + 8 + media_h + text_h  # 4 * 2
            
            msg_data.append({
                'msg': msg, 'lines': lines, 'bubble_h': bubble_h,
                'name_h': name_h, 'line_h': line_h, 'media_img': media_img, 'media_h': media_h
            })
            total_h += max(bubble_h, avatar_size) + msg_gap
        
        total_h -= msg_gap
        
        img = Image.new('RGBA', (MAX_IMAGE_WIDTH, min(MAX_IMAGE_HEIGHT, total_h)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        y = padding
        for data in msg_data:
            msg = data['msg']
            
            # Avatar
            self._draw_avatar(img, padding, y, avatar_size, msg.username, msg.avatar_data)
            
            # Bubble
            bubble_x = padding + avatar_size + gap
            bubble_w = MAX_IMAGE_WIDTH - bubble_x - padding
            self._draw_rounded_rect(draw, (bubble_x, y, bubble_x + bubble_w, y + data['bubble_h']), bubble_radius, COLORS["bubble"])
            
            # Username
            draw.text((bubble_x + bubble_padding, y + bubble_padding), msg.username, font=self.username_font, fill=self._get_username_color(msg.username))
            
            content_y = y + bubble_padding + data['name_h'] + 8  # 4 * 2
            
            # Media
            if data['media_img']:
                img.paste(data['media_img'], (bubble_x + bubble_padding, content_y), data['media_img'] if data['media_img'].mode == 'RGBA' else None)
                content_y += data['media_h']
            
            # Text
            for line in data['lines']:
                draw.text((bubble_x + bubble_padding, content_y), line, font=self.text_font_small, fill=COLORS["text"])
                content_y += data['line_h']
            
            y += max(data['bubble_h'], avatar_size) + msg_gap
        
        # Downscale from 2x to final size for Telegram stickers
        final_w = img.width // RENDER_SCALE
        final_h = img.height // RENDER_SCALE
        img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
        
        output = BytesIO()
        img.save(output, format='WEBP', quality=95)
        output.seek(0)
        
        return QuoteImage(image_data=output.getvalue(), format='webp', width=final_w, height=final_h)

    async def render_roast_quote(self, text: str, username: str, avatar_url: Optional[str] = None, 
                                  style: Optional[QuoteStyle] = None, avatar_data: Optional[bytes] = None,
                                  media_data: Optional[bytes] = None) -> QuoteImage:
        comment = await self.generate_roast_comment(text or "[медиа]")
        
        messages = [
            MessageData(text=text, username=username, avatar_data=avatar_data, media_data=media_data),
            MessageData(text=comment, username="Олег 🔥"),
        ]
        return await self.render_quote_chain(messages, style)

    async def generate_roast_comment(self, text: str) -> str:
        try:
            from app.services.ollama_client import _ollama_chat
            
            messages = [
                {"role": "system", "content": "Ты Олег — грубоватый ироничный бот. Коротко и по делу."},
                {"role": "user", "content": f"Дай короткий едкий комментарий к: '{text}'. Максимум 1-2 предложения."}
            ]
            
            comment = await _ollama_chat(messages, temperature=0.8)
            return comment[:150] if len(comment) > 150 else comment
        except:
            return random.choice(["Ну такое.", "Классика.", "Охуенно сказано.", "Записал.", "Мудрость веков."])

    async def queue_render_task(self, chat_id, text, username, **kwargs):
        try:
            from app.worker import enqueue_quote_render_task
            from app.config import settings
            if not settings.worker_enabled or not settings.redis_enabled:
                return None
            return await enqueue_quote_render_task(text=text, username=username, chat_id=chat_id, **kwargs)
        except:
            return None


quote_generator_service = QuoteGeneratorService()
