"""
Top 10 Chart Generator for multi-player growth visualization.

Generates comprehensive charts showing all top 10 players' growth history
with different colors for each player.

Requirements: 7.1 - Generate multi-line chart for top 10 players
"""

import io
import os
import logging
import requests
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class TopChartGenerator:
    """
    Generates multi-line charts for top 10 players visualization.
    
    Creates comprehensive charts showing growth history of all top players
    with distinct colors for each player.
    Uses 4x supersampling for high-quality anti-aliasing.
    """
    
    # Target Output Dimensions
    TARGET_WIDTH = 1600
    TARGET_HEIGHT = 1000
    
    # Supersampling Scale Factor
    SCALE = 4
    
    # Internal Render Dimensions
    WIDTH = TARGET_WIDTH * SCALE
    HEIGHT = TARGET_HEIGHT * SCALE
    
    PADDING = 80 * SCALE
    LEGEND_WIDTH = 350 * SCALE
    
    # Colors for top 10 players (vibrant and distinct)
    PLAYER_COLORS = [
        (255, 215, 0),    # Gold - 1st place
        (192, 192, 192),  # Silver - 2nd place
        (205, 127, 50),   # Bronze - 3rd place
        (255, 99, 71),    # Tomato red
        (50, 205, 50),    # Lime green
        (30, 144, 255),   # Dodger blue
        (255, 20, 147),   # Deep pink
        (138, 43, 226),   # Blue violet
        (255, 140, 0),    # Dark orange
        (0, 255, 255),    # Cyan
    ]
    
    # Background and grid colors
    BG_COLOR = (25, 25, 30)
    GRID_COLOR = (60, 60, 65)
    TEXT_COLOR = (220, 220, 220)
    AXIS_COLOR = (180, 180, 180)
    TITLE_COLOR = (255, 255, 255)
    
    def __init__(self):
        """Initialize the chart generator."""
        self._ensure_font_exists()
    
    def _ensure_font_exists(self):
        """Download Roboto font if not present to ensure consistent rendering on Linux."""
        font_dir = "assets/fonts"
        font_path = os.path.join(font_dir, "Roboto-Regular.ttf")
        
        if os.path.exists(font_path):
            return
            
        try:
            os.makedirs(font_dir, exist_ok=True)
            logger.info("Downloading Roboto font for charts...")
            url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(response.content)
                logger.info("Font downloaded successfully.")
            else:
                logger.warning(f"Failed to download font: {response.status_code}")
        except Exception as e:
            logger.warning(f"Error downloading font: {e}")

    def generate_top10_chart(self, top10_players: List) -> Optional[bytes]:
        """
        Generate a multi-line chart showing growth history for all top 10 players.
        
        Args:
            top10_players: List of GameStat objects (top 10 by size)
            
        Returns:
            PNG image as bytes, or None if insufficient data
        """
        if not top10_players:
            return None
        
        # Filter players with sufficient history
        players_with_history = [
            p for p in top10_players 
            if p.grow_history and len(p.grow_history) >= 2
        ]
        
        if not players_with_history:
            logger.info("No players with sufficient growth history")
            return None
        
        # Create high-res image for supersampling
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Load font - prioritize bundled font, then system fonts
        font = None
        font_small = None
        font_title = None
        using_emoji_font = False
        
        # Font sizes scaled by supersampling factor
        size_normal = 24 * self.SCALE
        size_small = 20 * self.SCALE
        size_title = 36 * self.SCALE
        
        font_candidates = [
            "assets/fonts/Roboto-Regular.ttf", # Bundled font (highest priority)
            "seguiemj.ttf", # Windows Emoji
            "arial.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        
        for font_name in font_candidates:
            try:
                font = ImageFont.truetype(font_name, size_normal)
                font_small = ImageFont.truetype(font_name, size_small)
                font_title = ImageFont.truetype(font_name, size_title)
                if "seguiemj" in font_name.lower():
                    using_emoji_font = True
                break
            except Exception:
                continue
        
        if font is None:
            # Fallback to default
            try:
                font = ImageFont.load_default(size=size_normal)
                font_small = ImageFont.load_default(size=size_small)
                font_title = ImageFont.load_default(size=size_title)
            except TypeError:
                font = ImageFont.load_default()
                font_small = font
                font_title = font
            
        # Helper to clean text if no emoji support
        import re
        def clean_text_for_chart(text: str) -> str:
            if using_emoji_font:
                return text
            # Keep basic unicode but strip complex emojis if needed
            # For Roboto, it handles Cyrillic well.
            return re.sub(r'[^\u0000-\uFFFF]', '', text)
        
        # Calculate chart area
        chart_left = self.PADDING + (80 * self.SCALE)
        chart_right = self.WIDTH - self.PADDING - self.LEGEND_WIDTH
        chart_top = self.PADDING + (60 * self.SCALE)
        chart_bottom = self.HEIGHT - self.PADDING - (50 * self.SCALE)
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top
        
        # Draw title
        title = "📈 ГРАФИК РОСТА ТОП-10 ИГРОКОВ"
        try:
            title_bbox = draw.textbbox((0, 0), title, font=font_title)
            title_width = title_bbox[2] - title_bbox[0]
        except AttributeError:
             title_width = draw.textlength(title, font=font_title)

        draw.text(
            ((self.WIDTH - self.LEGEND_WIDTH - title_width) // 2, 30 * self.SCALE),
            title,
            fill=self.TITLE_COLOR,
            font=font_title
        )
        
        # Find global min/max for Y-axis scaling
        all_sizes = []
        max_history_length = 0
        for player in players_with_history:
            sizes = [entry.get("size", 0) for entry in player.grow_history]
            all_sizes.extend(sizes)
            max_history_length = max(max_history_length, len(player.grow_history))
        
        if not all_sizes:
            return None
        
        min_size = min(all_sizes)
        max_size = max(all_sizes)
        size_range = max_size - min_size if max_size != min_size else 1
        
        # Draw grid lines (horizontal)
        num_grid_lines = 5
        for i in range(num_grid_lines + 1):
            y = chart_top + (chart_height * i) // num_grid_lines
            draw.line([(chart_left, y), (chart_right, y)], fill=self.GRID_COLOR, width=2 * self.SCALE)
            
            # Y-axis label
            size_value = max_size - (size_range * i) // num_grid_lines
            label = f"{size_value}"
            draw.text((self.PADDING, y - (12 * self.SCALE)), label, fill=self.TEXT_COLOR, font=font_small)
        
        # Draw vertical grid lines
        num_vertical_lines = min(7, max_history_length)
        for i in range(num_vertical_lines):
            x = chart_left + (chart_width * i) // (num_vertical_lines - 1) if num_vertical_lines > 1 else chart_left
            draw.line([(x, chart_top), (x, chart_bottom)], fill=self.GRID_COLOR, width=2 * self.SCALE)
        
        # Draw axes
        draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=self.AXIS_COLOR, width=3 * self.SCALE)
        draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=self.AXIS_COLOR, width=3 * self.SCALE)
        
        # Draw Y-axis label
        y_label = "Размер (см)"
        draw.text((20 * self.SCALE, chart_top + chart_height // 2 - (40 * self.SCALE)), y_label, fill=self.TEXT_COLOR, font=font)
        
        # Draw X-axis label
        x_label = "История (дни)"
        try:
            x_label_bbox = draw.textbbox((0, 0), x_label, font=font)
            x_label_width = x_label_bbox[2] - x_label_bbox[0]
        except AttributeError:
            x_label_width = draw.textlength(x_label, font=font)

        draw.text(
            (chart_left + (chart_width - x_label_width) // 2, chart_bottom + (20 * self.SCALE)),
            x_label,
            fill=self.TEXT_COLOR,
            font=font
        )
        
        # Draw each player's line
        legend_y = chart_top
        for idx, player in enumerate(players_with_history[:10]):  # Limit to 10
            color = self.PLAYER_COLORS[idx % len(self.PLAYER_COLORS)]
            
            history = player.grow_history
            sizes = [entry.get("size", 0) for entry in history]
            
            if len(sizes) < 2:
                continue
            
            points = []
            num_points = len(sizes)
            for i, size in enumerate(sizes):
                x = chart_left + (i * chart_width) // (num_points - 1) if num_points > 1 else chart_left
                normalized = (size - min_size) / size_range
                y = chart_bottom - int(normalized * chart_height)
                points.append((x, y))
            
            # Draw line with anti-aliasing simulation (width scaled)
            if len(points) >= 2:
                # Use joint="curve" if Pillow version supports it (recent versions do)
                try:
                    draw.line(points, fill=color, width=4 * self.SCALE, joint="curve")
                except TypeError:
                    draw.line(points, fill=color, width=4 * self.SCALE)
            
            # Draw points
            point_radius = 6 * self.SCALE
            for x, y in points:
                draw.ellipse(
                    [(x - point_radius, y - point_radius), 
                     (x + point_radius, y + point_radius)],
                    fill=color,
                    outline=(255, 255, 255),
                    width=2 * self.SCALE
                )
            
            # Draw legend entry
            legend_x = chart_right + (30 * self.SCALE)
            legend_entry_y = legend_y + (idx * 50 * self.SCALE)
            
            # Color box
            draw.rectangle(
                [(legend_x, legend_entry_y), (legend_x + (30 * self.SCALE), legend_entry_y + (30 * self.SCALE))],
                fill=color,
                outline=(255, 255, 255),
                width=2 * self.SCALE
            )
            
            # Player name
            name = player.username or str(player.tg_user_id)
            try:
                name = clean_text_for_chart(name)
            except Exception:
                pass
            
            if len(name) > 12:
                name = name[:12] + "..."
            
            medal = ""
            rank = idx + 1
            if using_emoji_font:
                if rank == 1: medal = "🥇 "
                elif rank == 2: medal = "🥈 "
                elif rank == 3: medal = "🥉 "
                else: medal = f"{rank}. "
            else:
                if rank == 1: medal = "#1 "
                elif rank == 2: medal = "#2 "
                elif rank == 3: medal = "#3 "
                else: medal = f"{rank}. "
            
            legend_text = f"{medal}{name}"
            draw.text(
                (legend_x + (40 * self.SCALE), legend_entry_y),
                legend_text,
                fill=self.TEXT_COLOR,
                font=font_small
            )
            
            size_text = f"{player.size_cm}см"
            draw.text(
                (legend_x + (40 * self.SCALE), legend_entry_y + (25 * self.SCALE)),
                size_text,
                fill=color,
                font=font_small
            )
        
        # Downsample for anti-aliasing
        # Resize back to target dimensions using LANCZOS filter
        final_image = image.resize((self.TARGET_WIDTH, self.TARGET_HEIGHT), resample=Image.Resampling.LANCZOS)
        
        # Convert to bytes
        buffer = io.BytesIO()
        final_image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance
top_chart_generator = TopChartGenerator()
