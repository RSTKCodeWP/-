"""Alert management service."""

from typing import List, Dict
from ..database.repository import DatabaseRepository
from ..utils.logger import setup_logger

logger = setup_logger('alerts')


class AlertManager:
    """Менеджер ценовых уведомлений."""
    
    def __init__(self, db: DatabaseRepository):
        self.db = db
        
    def add_alert(self, user_id: int, pair: str, condition: str, target: float):
        """Добавить новое уведомление."""
        alert = self.db.add_alert(user_id, pair, condition, target)
        logger.info(f"Alert added for user {user_id}: {pair} {condition} {target}")
        return alert
            
    def get_alerts(self, user_id: int) -> List[Dict]:
        """Получить все уведомления пользователя."""
        alerts = self.db.get_alerts(user_id)
        return [alert.to_dict() for alert in alerts]
    
    def get_all_alerts(self) -> List[Dict]:
        """Получить все уведомления всех пользователей."""
        alerts = self.db.get_all_alerts()
        return [(alert.user_id, alert.to_dict()) for alert in alerts]
            
    def remove_alert(self, user_id: int, index: int):
        """Удалить уведомление по индексу."""
        alerts = self.db.get_alerts(user_id)
        if 0 <= index < len(alerts):
            self.db.remove_alert(alerts[index].id)
            logger.info(f"Alert removed for user {user_id}, index: {index}")
                    
    def check_alerts(self, user_id: int, pair: str, current_price: float) -> List[Dict]:
        """Проверить уведомления и вернуть сработавшие."""
        triggered = []
        alerts = self.db.get_alerts(user_id)
        alerts_to_remove = []
        
        for alert in alerts:
            if alert.pair == pair.upper():
                should_trigger = False
                
                if alert.condition == 'above' and current_price >= alert.target:
                    should_trigger = True
                elif alert.condition == 'below' and current_price <= alert.target:
                    should_trigger = True
                
                if should_trigger:
                    triggered.append(alert.to_dict())
                    alerts_to_remove.append(alert.id)
                    logger.info(f"Alert triggered: {pair} {alert.condition} {alert.target}")
        
        if alerts_to_remove:
            self.db.remove_alerts(alerts_to_remove)
        
        return triggered
