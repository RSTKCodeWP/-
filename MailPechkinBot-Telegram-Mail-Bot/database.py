"""
Модуль для работы с базой данных SQLite
Хранит информацию о пользователях и их временных email-адресах
"""

import sqlite3
from typing import Optional
from contextlib import contextmanager


class Database:
    """Класс для работы с базой данных пользователей"""
    
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для работы с соединением БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        """Инициализирует базу данных и создает таблицы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    domain TEXT DEFAULT '1secmail.com',
                    provider TEXT DEFAULT '1SecMail',
                    auth_token TEXT,
                    auth_password TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    subject TEXT,
                    from_email TEXT,
                    date TEXT,
                    body TEXT,
                    is_favorite BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    auto_check BOOLEAN DEFAULT 0,
                    check_interval INTEGER DEFAULT 5,
                    preferred_domain TEXT DEFAULT '1secmail.com',
                    preferred_provider TEXT DEFAULT 'Mail.tm',
                    language TEXT DEFAULT 'ru',
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_emails_user_id 
                ON user_emails(user_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_emails_active 
                ON user_emails(user_id, is_active)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_history_user 
                ON message_history(user_id, created_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_history_favorite 
                ON message_history(user_id, is_favorite)
            """)
            
            conn.commit()
    
    def add_user(self, user_id: int, username: str = None, 
                 first_name: str = None, last_name: str = None):
        """Добавляет нового пользователя в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, last_name))
            conn.commit()
    
    def set_user_email(self, user_id: int, email: str, provider: str = "1SecMail", 
                      auth_token: str = None, auth_password: str = None):
        """
        Устанавливает новый активный email для пользователя
        Деактивирует предыдущий email
        
        Args:
            user_id: ID пользователя
            email: Email-адрес
            provider: Название провайдера, который создал email
            auth_token: Токен авторизации (для Mail.tm, TempMail.lol)
            auth_password: Пароль (для Mail.tm)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Деактивируем все предыдущие email-адреса пользователя
            cursor.execute("""
                UPDATE user_emails 
                SET is_active = 0 
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            
            # Добавляем новый активный email с информацией о провайдере и токенами
            domain = email.split("@")[1] if "@" in email else "unknown"
            cursor.execute("""
                INSERT INTO user_emails (user_id, email, is_active, domain, provider, auth_token, auth_password)
                VALUES (?, ?, 1, ?, ?, ?, ?)
            """, (user_id, email, domain, provider, auth_token, auth_password))
            
            conn.commit()
    
    def get_user_email(self, user_id: int) -> Optional[str]:
        """Получает текущий активный email пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email FROM user_emails
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            
            row = cursor.fetchone()
            return row["email"] if row else None
    
    def get_user_email_with_provider(self, user_id: int) -> Optional[tuple]:
        """Получает текущий активный email пользователя вместе с провайдером
        
        Returns:
            Кортеж (email, provider) или None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, provider FROM user_emails
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            
            row = cursor.fetchone()
            return (row["email"], row["provider"]) if row else None
    
    def get_user_email_full_info(self, user_id: int) -> Optional[dict]:
        """Получает полную информацию об активном email включая токены
        
        Returns:
            Словарь с email, provider, auth_token, auth_password или None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, provider, auth_token, auth_password FROM user_emails
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_user_email(self, user_id: int):
        """Удаляет (деактивирует) текущий активный email пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_emails 
                SET is_active = 0 
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            conn.commit()
    
    def get_user_email_history(self, user_id: int, limit: int = 10) -> list:
        """Получает историю email-адресов пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT email, created_at, is_active
                FROM user_emails
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_active_emails(self, user_id: int) -> list:
        """Получает все активные email-адреса пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, domain, created_at FROM user_emails
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def add_message_to_history(self, user_id: int, email: str, message_id: int, 
                               subject: str, from_email: str, date: str, body: str):
        """Добавляет письмо в историю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO message_history 
                (user_id, email, message_id, subject, from_email, date, body)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, email, message_id, subject, from_email, date, body))
            conn.commit()
    
    def get_message_history(self, user_id: int, limit: int = 20) -> list:
        """Получает историю писем пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM message_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def toggle_favorite(self, user_id: int, message_id: int) -> bool:
        """Переключает статус избранного для письма"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE message_history 
                SET is_favorite = NOT is_favorite
                WHERE user_id = ? AND message_id = ?
            """, (user_id, message_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_favorites(self, user_id: int) -> list:
        """Получает избранные письма пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM message_history
                WHERE user_id = ? AND is_favorite = 1
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_settings(self, user_id: int) -> dict:
        """Получает настройки пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM user_settings WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                # Создаем настройки по умолчанию
                cursor.execute("""
                    INSERT INTO user_settings (user_id) VALUES (?)
                """, (user_id,))
                conn.commit()
                return {
                    "user_id": user_id,
                    "auto_check": 0,
                    "check_interval": 5,
                    "preferred_domain": "1secmail.com",
                    "preferred_provider": "Mail.tm",
                    "language": "ru"
                }
    
    def update_user_settings(self, user_id: int, **kwargs):
        """Обновляет настройки пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            cursor.execute(f"""
                UPDATE user_settings SET {fields}
                WHERE user_id = ?
            """, values)
            conn.commit()
    
    def get_user_preferred_provider(self, user_id: int) -> Optional[str]:
        """Получает предпочитаемый провайдер пользователя из настроек"""
        settings = self.get_user_settings(user_id)
        return settings.get("preferred_provider")
    
    def set_user_preferred_provider(self, user_id: int, provider: str):
        """Устанавливает предпочитаемый провайдер для пользователя"""
        self.update_user_settings(user_id, preferred_provider=provider)
    
    def get_users_with_auto_check(self) -> list:
        """Получает всех пользователей с включенной автопроверкой"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.user_id, ue.email, us.check_interval
                FROM users u
                JOIN user_settings us ON u.user_id = us.user_id
                JOIN user_emails ue ON u.user_id = ue.user_id
                WHERE us.auto_check = 1 AND ue.is_active = 1
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> dict:
        """Получает статистику использования бота"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as total_users FROM users")
            total_users = cursor.fetchone()["total_users"]
            
            cursor.execute("SELECT COUNT(*) as total_emails FROM user_emails")
            total_emails = cursor.fetchone()["total_emails"]
            
            cursor.execute("""
                SELECT COUNT(*) as active_emails 
                FROM user_emails 
                WHERE is_active = 1
            """)
            active_emails = cursor.fetchone()["active_emails"]
            
            cursor.execute("SELECT COUNT(*) as total_messages FROM message_history")
            total_messages = cursor.fetchone()["total_messages"]
            
            return {
                "total_users": total_users,
                "total_emails": total_emails,
                "active_emails": active_emails,
                "total_messages": total_messages
            }
