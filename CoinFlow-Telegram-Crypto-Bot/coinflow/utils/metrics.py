"""Metrics tracking for CoinFlow bot."""

from typing import Dict, Set
from datetime import datetime


class Metrics:
    """Track bot usage metrics."""
    
    def __init__(self):
        self.conversions_count = 0
        self.charts_generated = 0
        self.predictions_made = 0
        self.alerts_triggered = 0
        self.comparisons_made = 0
        self.calculations_made = 0
        self.stock_queries = 0
        self.cs2_queries = 0
        self.active_users: Set[int] = set()
        self.start_time = datetime.now()
    
    def log_conversion(self, user_id: int):
        """Log a currency conversion."""
        self.conversions_count += 1
        self.active_users.add(user_id)
    
    def log_chart(self, user_id: int):
        """Log a chart generation."""
        self.charts_generated += 1
        self.active_users.add(user_id)
    
    def log_prediction(self, user_id: int):
        """Log a prediction generation."""
        self.predictions_made += 1
        self.active_users.add(user_id)
    
    def log_alert(self, user_id: int):
        """Log an alert trigger."""
        self.alerts_triggered += 1
        self.active_users.add(user_id)
    
    def log_comparison(self, user_id: int):
        """Log a rate comparison."""
        self.comparisons_made += 1
        self.active_users.add(user_id)
    
    def log_calculation(self, user_id: int):
        """Log a calculation."""
        self.calculations_made += 1
        self.active_users.add(user_id)
    
    def log_stock_query(self, user_id: int):
        """Log a stock query."""
        self.stock_queries += 1
        self.active_users.add(user_id)
    
    def log_cs2_query(self, user_id: int):
        """Log a CS2 item query."""
        self.cs2_queries += 1
        self.active_users.add(user_id)
    
    def get_stats(self) -> Dict:
        """Get current metrics."""
        uptime = datetime.now() - self.start_time
        return {
            'conversions': self.conversions_count,
            'charts': self.charts_generated,
            'predictions': self.predictions_made,
            'alerts': self.alerts_triggered,
            'comparisons': self.comparisons_made,
            'calculations': self.calculations_made,
            'stock_queries': self.stock_queries,
            'cs2_queries': self.cs2_queries,
            'active_users': len(self.active_users),
            'uptime_hours': round(uptime.total_seconds() / 3600, 2)
        }
    
    def get_stats_text(self) -> str:
        """Get formatted stats text."""
        stats = self.get_stats()
        return (
            f"📊 **Bot Statistics**\n\n"
            f"💱 Conversions: {stats['conversions']}\n"
            f"📈 Charts: {stats['charts']}\n"
            f"🔮 Predictions: {stats['predictions']}\n"
            f"⚖️ Comparisons: {stats['comparisons']}\n"
            f"🧮 Calculations: {stats['calculations']}\n"
            f"📊 Stock queries: {stats['stock_queries']}\n"
            f"🎮 CS2 queries: {stats['cs2_queries']}\n"
            f"🔔 Alerts triggered: {stats['alerts']}\n"
            f"👥 Active users: {stats['active_users']}\n"
            f"⏱️ Uptime: {stats['uptime_hours']} hours"
        )
