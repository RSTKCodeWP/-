"""Report generation service for CoinFlow bot."""

import io
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from ..utils.logger import setup_logger

logger = setup_logger('report_service')


class ReportService:
    """Service for generating analytical reports."""
    
    def __init__(self, db, converter, portfolio_service, chart_generator):
        """
        Initialize report service.
        
        Args:
            db: Database repository
            converter: Currency converter service
            portfolio_service: Portfolio service
            chart_generator: Chart generator service
        """
        self.db = db
        self.converter = converter
        self.portfolio_service = portfolio_service
        self.chart_generator = chart_generator
    
    async def generate_weekly_digest(self, user_id: int, lang: str = 'en') -> Dict:
        """
        Generate weekly market digest for user.
        
        Args:
            user_id: User ID
            lang: Language code
        
        Returns:
            Dict with report data and image
        """
        try:
            # Get user's portfolio
            portfolio_items = self.db.get_portfolio_items(user_id)
            
            # Get user's favorites
            favorites = self.db.get_user_favorites(user_id)
            
            # Combine assets to track
            assets_to_track = set()
            
            # From portfolio
            for item in portfolio_items:
                if item.asset_type == 'crypto':
                    assets_to_track.add(item.asset_symbol)
            
            # From favorites (only crypto)
            crypto_favs = ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOGE', 'DOT', 'MATIC', 'AVAX']
            for fav in favorites:
                if fav.currency in crypto_favs:
                    assets_to_track.add(fav.currency)
            
            # Default tracking if user has no assets
            if not assets_to_track:
                assets_to_track = {'BTC', 'ETH', 'BNB'}
            
            # Get price changes for tracked assets
            performance_data = []
            for asset in assets_to_track:
                try:
                    # Get current price
                    current_rate = self.converter.get_rate(asset, 'USD')
                    if not current_rate:
                        continue
                    
                    # Calculate 7-day change (simplified - in real app would use historical data)
                    # For now, using a placeholder calculation
                    change_7d = 0.0  # Would need historical price tracking
                    
                    performance_data.append({
                        'asset': asset,
                        'current_price': current_rate,
                        'change_7d': change_7d,
                        'change_pct': change_7d
                    })
                except Exception as e:
                    logger.error(f"Error getting data for {asset}: {e}")
                    continue
            
            # Sort by performance
            performance_data.sort(key=lambda x: x['change_pct'], reverse=True)
            
            # Generate chart
            chart_image = self._create_performance_chart(performance_data, lang)
            
            # Create text report
            report_text = self._format_weekly_report(performance_data, lang)
            
            return {
                'text': report_text,
                'image': chart_image,
                'assets_tracked': len(performance_data)
            }
            
        except Exception as e:
            logger.error(f"Error generating weekly digest: {e}")
            return None
    
    def _create_performance_chart(self, data: List[Dict], lang: str) -> bytes:
        """Create performance chart."""
        try:
            fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
            
            if not data:
                ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=16)
                ax.axis('off')
            else:
                assets = [d['asset'] for d in data]
                changes = [d['change_pct'] for d in data]
                
                colors = ['green' if c >= 0 else 'red' for c in changes]
                
                ax.barh(assets, changes, color=colors, alpha=0.7)
                ax.axvline(0, color='black', linewidth=0.8, linestyle='--')
                ax.set_xlabel('7-Day Change (%)', fontsize=12)
                ax.set_title('Weekly Performance Overview', fontsize=14, fontweight='bold')
                ax.grid(axis='x', alpha=0.3)
            
            plt.tight_layout()
            
            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf.getvalue()
            
        except Exception as e:
            logger.error(f"Error creating performance chart: {e}")
            return None
    
    def _format_weekly_report(self, data: List[Dict], lang: str) -> str:
        """Format weekly report text."""
        if lang == 'ru':
            title = "📊 **Еженедельный отчет**\n\n"
            date_range = f"📅 Период: {(datetime.now() - timedelta(days=7)).strftime('%d.%m')} - {datetime.now().strftime('%d.%m.%Y')}\n\n"
        else:
            title = "📊 **Weekly Market Digest**\n\n"
            date_range = f"📅 Period: {(datetime.now() - timedelta(days=7)).strftime('%d.%m')} - {datetime.now().strftime('%d.%m.%Y')}\n\n"
        
        if not data:
            return title + date_range + ("Нет данных для отображения" if lang == 'ru' else "No data to display")
        
        # Best performers
        best = data[:3]
        worst = data[-3:]
        
        if lang == 'ru':
            text = title + date_range
            text += "🏆 **Лучшие:**\n"
            for item in best:
                emoji = "📈" if item['change_pct'] >= 0 else "📉"
                text += f"{emoji} {item['asset']}: ${item['current_price']:.2f} ({item['change_pct']:+.1f}%)\n"
            
            text += "\n📉 **Худшие:**\n"
            for item in worst:
                emoji = "📈" if item['change_pct'] >= 0 else "📉"
                text += f"{emoji} {item['asset']}: ${item['current_price']:.2f} ({item['change_pct']:+.1f}%)\n"
        else:
            text = title + date_range
            text += "🏆 **Top Performers:**\n"
            for item in best:
                emoji = "📈" if item['change_pct'] >= 0 else "📉"
                text += f"{emoji} {item['asset']}: ${item['current_price']:.2f} ({item['change_pct']:+.1f}%)\n"
            
            text += "\n📉 **Worst Performers:**\n"
            for item in worst:
                emoji = "📈" if item['change_pct'] >= 0 else "📉"
                text += f"{emoji} {item['asset']}: ${item['current_price']:.2f} ({item['change_pct']:+.1f}%)\n"
        
        text += f"\n📊 Total assets tracked: {len(data)}"
        
        return text
    
    async def generate_portfolio_report(self, user_id: int, lang: str = 'en') -> Dict:
        """Generate detailed portfolio performance report."""
        try:
            summary = await self.portfolio_service.get_portfolio_summary(user_id)
            
            if not summary or summary['total_value_usd'] == 0:
                return None
            
            # Create report
            if lang == 'ru':
                text = "💼 **Отчет по портфелю**\n\n"
                text += f"💰 Общая стоимость: ${summary['total_value_usd']:.2f}\n"
                text += f"📊 Активов: {summary['total_items']}\n\n"
                text += "📈 **Распределение:**\n"
            else:
                text = "💼 **Portfolio Report**\n\n"
                text += f"💰 Total Value: ${summary['total_value_usd']:.2f}\n"
                text += f"📊 Assets: {summary['total_items']}\n\n"
                text += "📈 **Distribution:**\n"
            
            for asset_type, value in summary.get('by_type_value', {}).items():
                pct = (value / summary['total_value_usd'] * 100) if summary['total_value_usd'] > 0 else 0
                text += f"• {asset_type.title()}: ${value:.2f} ({pct:.1f}%)\n"
            
            return {
                'text': text,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error generating portfolio report: {e}")
            return None
    
    def format_report_message(self, report_data: Dict, report_type: str, lang: str = 'en') -> str:
        """Format report as Telegram message."""
        if not report_data:
            return "📊 No data available for report" if lang == 'en' else "📊 Нет данных для отчета"
        
        if report_type == 'weekly':
            return report_data['text']
        elif report_type == 'portfolio':
            return report_data['text']
        else:
            return report_data.get('text', '')
