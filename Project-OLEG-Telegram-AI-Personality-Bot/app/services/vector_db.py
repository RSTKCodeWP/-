"""Модуль для работы с векторной базой данных (RAG)."""

import logging
import warnings
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from typing import List, Dict, Optional, Tuple, Any
import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import httpx


@dataclass
class RAGFactMetadata:
    """
    Metadata schema for RAG facts in ChromaDB.
    
    **Feature: shield-economy-v65**
    **Validates: Requirements 11.1, 11.2, 11.3**
    
    This dataclass ensures consistent serialization and deserialization
    of RAG fact metadata, preserving all fields including Unicode characters.
    """
    chat_id: int
    user_id: int
    username: str
    topic_id: int  # -1 if not in topic
    message_id: int
    created_at: str  # ISO 8601 format
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata to a dictionary for ChromaDB storage.
        
        All fields are preserved exactly as stored, including Unicode
        characters in username and other string fields.
        
        Returns:
            Dictionary with all metadata fields
        """
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "topic_id": self.topic_id,
            "message_id": self.message_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGFactMetadata":
        """
        Deserialize metadata from a dictionary.
        
        Handles missing fields gracefully with sensible defaults.
        Preserves Unicode characters exactly as stored.
        
        Args:
            data: Dictionary containing metadata fields
            
        Returns:
            RAGFactMetadata instance with all fields populated
        """
        return cls(
            chat_id=data["chat_id"],
            user_id=data["user_id"],
            username=data.get("username", ""),
            topic_id=data.get("topic_id", -1),
            message_id=data.get("message_id", 0),
            created_at=data["created_at"],
        )

# Подавляем ошибки телеметрии chromadb
warnings.filterwarnings("ignore", message=".*telemetry.*")
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


class OllamaEmbeddingFunction(EmbeddingFunction):
    """
    Кастомная embedding function для ChromaDB через Ollama API.
    Использует nomic-embed-text или другую модель из настроек.
    """
    
    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._available = None
    
    def _check_available(self) -> bool:
        """Проверяет доступность Ollama."""
        if self._available is not None:
            return self._available
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                self._available = response.status_code == 200
        except Exception:
            self._available = False
        return self._available
    
    def __call__(self, input: Documents) -> Embeddings:
        """Генерирует embeddings через Ollama API (batch mode)."""
        if not self._check_available():
            logger.warning(f"Ollama недоступен, используем fallback embeddings")
            # Возвращаем нулевые embeddings как fallback
            return [[0.0] * 768 for _ in input]
        
        try:
            # Ollama поддерживает batch embeddings — отправляем все тексты за один запрос
            # Увеличенный таймаут до 60 секунд для стабильности
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": input}  # Передаём список текстов
                )
                if response.status_code == 200:
                    data = response.json()
                    # Ollama возвращает embeddings в поле "embeddings" (список списков)
                    embeddings = data.get("embeddings", [])
                    if embeddings and len(embeddings) == len(input):
                        return embeddings
                    else:
                        logger.warning(f"Ollama вернул {len(embeddings)} embeddings для {len(input)} текстов")
                        # Дополняем нулевыми если не хватает
                        while len(embeddings) < len(input):
                            embeddings.append([0.0] * 768)
                        return embeddings
                else:
                    logger.warning(f"Ollama embed error: {response.status_code}")
                    return [[0.0] * 768 for _ in input]
        except Exception as e:
            logger.error(f"Ошибка при получении embeddings: {e}")
            # Fallback — нулевые embeddings
            return [[0.0] * 768 for _ in input]


# Глобальный экземпляр embedding function
_ollama_embedding_fn: Optional[OllamaEmbeddingFunction] = None


def get_ollama_embedding_function() -> OllamaEmbeddingFunction:
    """Получает или создаёт Ollama embedding function."""
    global _ollama_embedding_fn
    if _ollama_embedding_fn is None:
        from app.config import settings
        _ollama_embedding_fn = OllamaEmbeddingFunction(
            model=settings.embedding_model,
            base_url=settings.ollama_base_url
        )
        logger.info(f"Ollama embedding function: model={settings.embedding_model}")
    return _ollama_embedding_fn


class VectorDB:
    """Класс для работы с векторной базой данных ChromaDB."""
    
    def __init__(self):
        self.client = None
        self.collections = {}
        self.init_db()
    
    def init_db(self):
        """Инициализирует соединение с ChromaDB."""
        try:
            from app.config import settings
            
            # Если указан хост - подключаемся к серверу через HTTP
            if settings.chromadb_host:
                self.client = chromadb.HttpClient(
                    host=settings.chromadb_host,
                    port=settings.chromadb_port,
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info(f"ChromaDB подключена к серверу {settings.chromadb_host}:{settings.chromadb_port}")
            else:
                # Используем PersistentClient для локального хранения
                self.client = chromadb.PersistentClient(
                    path=settings.chromadb_persist_dir,
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info(f"ChromaDB инициализирована локально (путь: {settings.chromadb_persist_dir})")
        except Exception as e:
            logger.error(f"Ошибка при инициализации ChromaDB: {e}")
            self.client = None  # Не падаем, просто отключаем
    
    def get_or_create_collection(self, name: str):
        """Получает или создает коллекцию с Ollama embeddings."""
        try:
            # Используем Ollama embedding function вместо дефолтной
            embedding_fn = get_ollama_embedding_function()
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=embedding_fn
            )
            return self.collections[name]
        except Exception as e:
            logger.error(f"Ошибка при получении коллекции {name}: {e}")
            # Пробуем без кастомных embeddings как fallback
            try:
                logger.warning(f"Fallback: создаём коллекцию {name} с дефолтными embeddings")
                self.collections[name] = self.client.get_or_create_collection(name)
                return self.collections[name]
            except Exception as e2:
                logger.error(f"Не удалось создать коллекцию {name}: {e2}")
                raise
    
    def add_fact(self, collection_name: str, fact_text: str, metadata: Dict = None, doc_id: str = None):
        """
        Добавляет факт в коллекцию.
        
        Args:
            collection_name: Название коллекции
            fact_text: Текст факта для хранения
            metadata: Метаданные (чат, пользователь и т.д.)
            doc_id: Уникальный ID документа (если не указан, генерируется автоматически)
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        if not doc_id:
            # Генерируем ID на основе текущего времени
            doc_id = f"fact_{int(datetime.now().timestamp() * 1000000)}"
        
        if not metadata:
            metadata = {"created_at": datetime.now().isoformat()}
        
        try:
            collection.add(
                documents=[fact_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.info(f"Факт добавлен в коллекцию {collection_name}: {fact_text[:100]}...")
        except Exception as e:
            logger.error(f"Ошибка при добавлении факта: {e}")
            raise
    
    def search_facts(self, collection_name: str, query: str, n_results: int = 5, model: str = None, where: Dict = None) -> List[Dict]:
        """
        Ищет релевантные факты в коллекции.
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            n_results: Количество результатов для возврата
            model: Модель для использования (не используется в ChromaDB, для совместимости)
            where: Фильтр по метаданным (например, {"chat_id": 123})
            
        Returns:
            Список словарей с найденными фактами
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Сначала пробуем поиск по тегам (более точный для технических терминов)
            # Извлекаем ключевые слова из запроса
            query_lower = query.lower()
            query_terms = query_lower.split()
            
            # Ищем факты где теги содержат любой из терминов запроса
            tag_matched_facts = []
            
            # Стоп-слова которые не должны триггерить поиск по тегам
            stop_words = {
                'вот', 'уже', 'это', 'как', 'что', 'для', 'или', 'при', 'без', 'под',
                'над', 'про', 'так', 'там', 'тут', 'где', 'кто', 'чем', 'чего', 'его',
                'она', 'они', 'оно', 'мой', 'твой', 'наш', 'ваш', 'все', 'всё', 'был',
                'быть', 'есть', 'нет', 'да', 'ну', 'же', 'бы', 'ли', 'не', 'ни',
                'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was',
                'давай', 'олег', 'привет', 'пока', 'спасибо', 'плиз', 'пожалуйста',
                'можно', 'нужно', 'надо', 'хочу', 'могу', 'буду', 'будет', 'если',
                'когда', 'потом', 'сейчас', 'ещё', 'еще', 'очень', 'просто', 'только',
                'конца', 'конец', 'начало', 'ярлыками', 'ярлык', 'доделаем', 'сделаем'
            }
            
            if where and where.get("source") == "default_knowledge":
                try:
                    # Фильтруем термины: убираем стоп-слова и короткие
                    filtered_terms = [t for t in query_terms if len(t) >= 4 and t not in stop_words]
                    
                    # Если после фильтрации не осталось терминов — пропускаем tag search
                    if not filtered_terms:
                        logger.debug(f"[TAG SEARCH] Пропущен: нет значимых терминов в запросе")
                    else:
                        # Получаем все факты и фильтруем по тегам
                        all_results = collection.get(where=where, limit=500)
                        logger.debug(f"[TAG SEARCH] Получено {len(all_results['ids']) if all_results and all_results['ids'] else 0} фактов для фильтрации")
                        logger.debug(f"[TAG SEARCH] Ищем термины: {filtered_terms}")
                        
                        if all_results and all_results['ids']:
                            for i, doc_id in enumerate(all_results['ids']):
                                metadata = all_results['metadatas'][i] if all_results['metadatas'] else {}
                                tags = metadata.get('tags', '').lower()
                                
                                # Проверяем совпадение ТОЛЬКО по тегам (не по тексту!)
                                for term in filtered_terms:
                                    if term in tags:
                                        tag_matched_facts.append({
                                            'text': all_results['documents'][i],
                                            'metadata': metadata,
                                            'distance': 0.1,  # Высокий приоритет для tag match
                                            'match_type': 'tag'
                                        })
                                        logger.debug(f"[TAG MATCH] Термин '{term}' найден в тегах: {tags[:60]}...")
                                        break
                        
                        if tag_matched_facts:
                            logger.info(f"[TAG SEARCH] Найдено {len(tag_matched_facts)} фактов по тегам")
                except Exception as e:
                    logger.warning(f"Tag search failed: {e}")
            
            # Затем делаем embedding поиск
            query_params = {
                "query_texts": [query],
                "n_results": n_results * 2  # Берём больше для объединения
            }
            if where:
                query_params["where"] = where
            
            results = collection.query(**query_params)
            
            embedding_facts = []
            for i in range(len(results['documents'][0])):
                fact = {
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if results['distances'] and len(results['distances'][0]) > i else None,
                    'match_type': 'embedding'
                }
                embedding_facts.append(fact)
            
            # Объединяем результаты: сначала tag matches, потом embedding matches
            # Убираем дубликаты по тексту
            seen_texts = set()
            combined_facts = []
            
            # Сначала добавляем tag matches (они более точные)
            for fact in tag_matched_facts:
                if fact['text'] not in seen_texts:
                    seen_texts.add(fact['text'])
                    combined_facts.append(fact)
            
            # Затем добавляем embedding matches
            for fact in embedding_facts:
                if fact['text'] not in seen_texts:
                    seen_texts.add(fact['text'])
                    combined_facts.append(fact)
            
            # Ограничиваем количество результатов
            final_facts = combined_facts[:n_results]
            
            logger.debug(f"Найдено {len(final_facts)} фактов по запросу: {query[:50]}... (tag: {len(tag_matched_facts)}, emb: {len(embedding_facts)})")
            return final_facts
        except Exception as e:
            logger.error(f"Ошибка при поиске фактов: {e}")
            return []
    
    def search_cross_topic(self, collection_name: str, query: str, chat_id: int, n_results: int = 5) -> List[Dict]:
        """
        Ищет релевантные факты из всех топиков чата (cross-topic retrieval).
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            chat_id: ID чата для фильтрации
            n_results: Количество результатов для возврата
            
        Returns:
            Список словарей с найденными фактами из всех топиков чата
        """
        # Фильтруем только по chat_id, не по topic_id - это даёт cross-topic retrieval
        return self.search_facts(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            where={"chat_id": chat_id}
        )
    
    def store_message(self, collection_name: str, text: str, chat_id: int, topic_id: Optional[int], 
                      user_id: int, username: Optional[str], message_id: int) -> None:
        """
        Сохраняет сообщение в RAG с привязкой к chat_id и topic_id.
        
        Args:
            collection_name: Название коллекции
            text: Текст сообщения
            chat_id: ID чата
            topic_id: ID топика (None если не в топике)
            user_id: ID пользователя
            username: Username пользователя
            message_id: ID сообщения в Telegram
        """
        metadata = {
            "chat_id": chat_id,
            "topic_id": topic_id if topic_id is not None else -1,
            "user_id": user_id,
            "username": username or "",
            "message_id": message_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        doc_id = f"msg_{chat_id}_{message_id}"
        
        self.add_fact(
            collection_name=collection_name,
            fact_text=text,
            metadata=metadata,
            doc_id=doc_id
        )
    
    def get_all_facts(self, collection_name: str) -> List[Dict]:
        """
        Получает все факты из коллекции.
        
        Args:
            collection_name: Название коллекции
            
        Returns:
            Список всех фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            results = collection.get()
            
            facts = []
            for i in range(len(results['documents'])):
                fact = {
                    'id': results['ids'][i],
                    'text': results['documents'][i],
                    'metadata': results['metadatas'][i] if results['metadatas'] else {}
                }
                facts.append(fact)
            
            return facts
        except Exception as e:
            logger.error(f"Ошибка при получении всех фактов: {e}")
            return []
    
    def delete_fact(self, collection_name: str, doc_id: str):
        """
        Удаляет факт по ID.
        
        Args:
            collection_name: Название коллекции
            doc_id: ID документа для удаления
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            collection.delete(ids=[doc_id])
            logger.info(f"Факт {doc_id} удален из коллекции {collection_name}")
        except Exception as e:
            logger.error(f"Ошибка при удалении факта {doc_id}: {e}")
    
    # =========================================================================
    # Temporal Memory Methods (Shield & Economy v6.5)
    # =========================================================================
    
    def add_fact_with_timestamp(
        self,
        collection_name: str,
        fact_text: str,
        metadata: Dict,
        created_at: Optional[datetime] = None
    ) -> str:
        """
        Добавляет факт с обязательной временной меткой в ISO 8601.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 4.1**
        
        Args:
            collection_name: Название коллекции
            fact_text: Текст факта
            metadata: Метаданные (chat_id, user_id, etc.)
            created_at: Время создания (по умолчанию - текущее время)
            
        Returns:
            ID созданного документа
        """
        if created_at is None:
            created_at = datetime.now()
        
        # Ensure created_at is in ISO 8601 format
        metadata["created_at"] = created_at.isoformat()
        
        # Generate unique doc_id
        doc_id = f"fact_{int(datetime.now().timestamp() * 1000000)}"
        
        self.add_fact(
            collection_name=collection_name,
            fact_text=fact_text,
            metadata=metadata,
            doc_id=doc_id
        )
        
        return doc_id
    
    def search_facts_with_age(
        self,
        collection_name: str,
        query: str,
        chat_id: int,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Ищет факты и добавляет информацию о возрасте каждого факта.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 4.3, 4.4**
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            chat_id: ID чата для фильтрации
            n_results: Количество результатов
            
        Returns:
            Список фактов с полем age_days
        """
        facts = self.search_facts(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            where={"chat_id": chat_id}
        )
        
        now = datetime.now()
        
        for fact in facts:
            metadata = fact.get('metadata', {})
            created_at_str = metadata.get('created_at') or metadata.get('timestamp')
            
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    age_days = (now - created_at).days
                    fact['age_days'] = age_days
                except (ValueError, TypeError):
                    fact['age_days'] = -1  # Unknown age
            else:
                fact['age_days'] = -1
        
        # Sort by recency (newer facts first) for prioritization
        facts.sort(key=lambda f: f.get('age_days', 999))
        
        return facts
    
    # =========================================================================
    # Memory Management Methods (Shield & Economy v6.5)
    # =========================================================================
    
    def delete_all_chat_facts(
        self,
        collection_name: str,
        chat_id: int
    ) -> int:
        """
        Удаляет все факты для указанного чата.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 5.1, 5.4**
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Get all facts for this chat
            results = collection.get(where={"chat_id": chat_id})
            
            if not results['ids']:
                return 0
            
            count = len(results['ids'])
            collection.delete(ids=results['ids'])
            
            logger.info(f"Удалено {count} фактов для чата {chat_id}")
            return count
            
        except Exception as e:
            logger.error(f"Ошибка при удалении фактов чата {chat_id}: {e}")
            return 0
    
    def delete_old_facts(
        self,
        collection_name: str,
        chat_id: int,
        older_than_days: int = 90
    ) -> int:
        """
        Удаляет факты старше указанного количества дней.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 5.2, 5.4**
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            older_than_days: Удалять факты старше этого количества дней
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Get all facts for this chat
            results = collection.get(where={"chat_id": chat_id})
            
            if not results['ids']:
                return 0
            
            now = datetime.now()
            ids_to_delete = []
            
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                created_at_str = metadata.get('created_at') or metadata.get('timestamp')
                
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        age_days = (now - created_at).days
                        
                        if age_days >= older_than_days:
                            ids_to_delete.append(doc_id)
                    except (ValueError, TypeError):
                        pass  # Skip facts with invalid timestamps
            
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Удалено {len(ids_to_delete)} старых фактов для чата {chat_id}")
            
            return len(ids_to_delete)
            
        except Exception as e:
            logger.error(f"Ошибка при удалении старых фактов чата {chat_id}: {e}")
            return 0
    
    def delete_user_facts(
        self,
        collection_name: str,
        chat_id: int,
        user_id: int
    ) -> int:
        """
        Удаляет все факты указанного пользователя в чате.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 5.3, 5.4**
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # ChromaDB supports $and for multiple conditions
            results = collection.get(
                where={
                    "$and": [
                        {"chat_id": chat_id},
                        {"user_id": user_id}
                    ]
                }
            )
            
            if not results['ids']:
                return 0
            
            count = len(results['ids'])
            collection.delete(ids=results['ids'])
            
            logger.info(f"Удалено {count} фактов пользователя {user_id} в чате {chat_id}")
            return count
            
        except Exception as e:
            logger.error(f"Ошибка при удалении фактов пользователя {user_id}: {e}")
            return 0

    def delete_low_importance_facts(
        self,
        collection_name: str,
        chat_id: int,
        max_importance: int = 4
    ) -> int:
        """
        Удаляет факты с низким приоритетом (importance <= max_importance).
        
        Полезно для периодической очистки памяти от малозначимых фактов.
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            max_importance: Максимальный importance для удаления (включительно)
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Получаем все факты чата
            results = collection.get(where={"chat_id": chat_id})
            
            if not results['ids']:
                return 0
            
            ids_to_delete = []
            
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                importance = metadata.get('importance', 5)
                
                # Удаляем факты с низким приоритетом
                if isinstance(importance, (int, float)) and importance <= max_importance:
                    ids_to_delete.append(doc_id)
            
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Удалено {len(ids_to_delete)} низкоприоритетных фактов (importance <= {max_importance}) для чата {chat_id}")
            
            return len(ids_to_delete)
            
        except Exception as e:
            logger.error(f"Ошибка при удалении низкоприоритетных фактов чата {chat_id}: {e}")
            return 0

    def cleanup_memory(
        self,
        collection_name: str,
        chat_id: int,
        older_than_days: int = 90,
        low_importance_threshold: int = 4
    ) -> dict:
        """
        Комплексная очистка памяти: удаляет старые и низкоприоритетные факты.
        
        Рекомендуется запускать периодически (например, раз в неделю).
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            older_than_days: Удалять факты старше этого количества дней
            low_importance_threshold: Удалять факты с importance <= этого значения
            
        Returns:
            Словарь с количеством удалённых фактов по категориям
        """
        old_deleted = self.delete_old_facts(collection_name, chat_id, older_than_days)
        low_importance_deleted = self.delete_low_importance_facts(collection_name, chat_id, low_importance_threshold)
        
        total = old_deleted + low_importance_deleted
        if total > 0:
            logger.info(f"Очистка памяти чата {chat_id}: удалено {old_deleted} старых + {low_importance_deleted} низкоприоритетных = {total} фактов")
        
        return {
            "old_facts_deleted": old_deleted,
            "low_importance_deleted": low_importance_deleted,
            "total_deleted": total
        }

    # =========================================================================
    # Default Knowledge Management
    # =========================================================================
    
    def load_default_knowledge(
        self,
        collection_name: str,
        knowledge_file: Optional[str] = None
    ) -> dict:
        """
        Загружает начальную базу знаний из JSON файла в RAG.
        
        Эти знания являются "дефолтными" для бота и восстанавливаются
        при вайпе базы данных.
        
        Args:
            collection_name: Название коллекции для загрузки
            knowledge_file: Путь к JSON файлу (по умолчанию app/data/default_knowledge.json)
            
        Returns:
            Словарь со статистикой загрузки
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        # Определяем путь к файлу знаний
        if knowledge_file is None:
            # Ищем относительно корня проекта
            base_paths = [
                Path(__file__).parent.parent / "data" / "default_knowledge.json",
                Path("app/data/default_knowledge.json"),
                Path("./app/data/default_knowledge.json"),
            ]
            
            knowledge_path = None
            for path in base_paths:
                if path.exists():
                    knowledge_path = path
                    break
            
            if knowledge_path is None:
                logger.warning("Файл default_knowledge.json не найден")
                return {"loaded": 0, "categories": 0, "error": "file_not_found"}
        else:
            knowledge_path = Path(knowledge_file)
            if not knowledge_path.exists():
                logger.warning(f"Файл знаний не найден: {knowledge_path}")
                return {"loaded": 0, "categories": 0, "error": "file_not_found"}
        
        try:
            with open(knowledge_path, "r", encoding="utf-8") as f:
                knowledge_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return {"loaded": 0, "categories": 0, "error": f"json_error: {e}"}
        
        collection = self.get_or_create_collection(collection_name)
        
        loaded_count = 0
        categories_count = 0
        version = knowledge_data.get("version", "unknown")
        
        categories = knowledge_data.get("categories", {})
        
        # Собираем все факты для batch загрузки
        all_documents = []
        all_metadatas = []
        all_ids = []
        
        for category_name, category_data in categories.items():
            categories_count += 1
            facts = category_data.get("facts", [])
            
            for i, fact in enumerate(facts):
                fact_text = fact.get("text", "")
                if not fact_text:
                    continue
                
                # Формируем метаданные
                metadata = {
                    "source": "default_knowledge",
                    "category": category_name,
                    "importance": fact.get("importance", 5),
                    "tags": ",".join(fact.get("tags", [])),
                    "version": version,
                    "created_at": datetime.now().isoformat(),
                    # Системные факты не привязаны к конкретному чату
                    "chat_id": 0,
                    "user_id": 0,
                    "topic_id": -1,
                }
                
                # Уникальный ID для дефолтных знаний
                doc_id = f"default_{category_name}_{i}"
                
                all_documents.append(fact_text)
                all_metadatas.append(metadata)
                all_ids.append(doc_id)
        
        # Batch загрузка — добавляем все факты за один раз
        # Это НАМНОГО быстрее чем по одному (один вызов embeddings вместо 400+)
        logger.info(f"Подготовлено {len(all_documents)} фактов из {categories_count} категорий для загрузки (v{version})")
        
        if all_documents:
            try:
                # Загружаем батчами по 50 фактов (ChromaDB лимит)
                batch_size = 50
                for batch_start in range(0, len(all_documents), batch_size):
                    batch_end = min(batch_start + batch_size, len(all_documents))
                    batch_docs = all_documents[batch_start:batch_end]
                    batch_metas = all_metadatas[batch_start:batch_end]
                    batch_ids = all_ids[batch_start:batch_end]
                    
                    try:
                        collection.add(
                            documents=batch_docs,
                            metadatas=batch_metas,
                            ids=batch_ids
                        )
                        loaded_count += len(batch_docs)
                        logger.info(f"Загружено {loaded_count}/{len(all_documents)} фактов...")
                    except Exception as e:
                        # Если batch не удался, пробуем по одному
                        logger.warning(f"Batch загрузка не удалась, пробуем по одному: {e}")
                        for j, (doc, meta, doc_id) in enumerate(zip(batch_docs, batch_metas, batch_ids)):
                            try:
                                collection.add(
                                    documents=[doc],
                                    metadatas=[meta],
                                    ids=[doc_id]
                                )
                                loaded_count += 1
                            except Exception as e2:
                                logger.error(f"Ошибка загрузки факта {doc_id}: {e2}")
            except Exception as e:
                logger.error(f"Критическая ошибка при batch загрузке: {e}")
        
        logger.info(f"Загружено {loaded_count} фактов из {categories_count} категорий (версия: {version})")
        
        return {
            "loaded": loaded_count,
            "categories": categories_count,
            "version": version,
            "collection": collection_name
        }
    
    def get_default_knowledge_stats(self, collection_name: str) -> dict:
        """
        Получает статистику по загруженным дефолтным знаниям.
        
        Returns:
            Словарь со статистикой по категориям
        """
        if not self.client:
            return {"error": "ChromaDB не инициализирована"}
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Получаем все дефолтные знания
            results = collection.get(
                where={"source": "default_knowledge"}
            )
            
            if not results['ids']:
                return {"total": 0, "categories": {}}
            
            # Группируем по категориям
            categories = {}
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                category = metadata.get('category', 'unknown')
                
                if category not in categories:
                    categories[category] = 0
                categories[category] += 1
            
            return {
                "total": len(results['ids']),
                "categories": categories,
                "version": results['metadatas'][0].get('version', 'unknown') if results['metadatas'] else 'unknown'
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"error": str(e)}
    
    def clear_default_knowledge(self, collection_name: str) -> int:
        """
        Удаляет все дефолтные знания из коллекции.
        
        Returns:
            Количество удалённых фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            results = collection.get(
                where={"source": "default_knowledge"}
            )
            
            if not results['ids']:
                return 0
            
            count = len(results['ids'])
            collection.delete(ids=results['ids'])
            
            logger.info(f"Удалено {count} дефолтных знаний")
            return count
            
        except Exception as e:
            logger.error(f"Ошибка удаления дефолтных знаний: {e}")
            return 0
    
    def search_with_default_knowledge(
        self,
        collection_name: str,
        query: str,
        chat_id: Optional[int] = None,
        n_results: int = 5,
        include_defaults: bool = True
    ) -> List[Dict]:
        """
        Поиск с учётом дефолтных знаний.
        
        Сначала ищет в контексте чата, затем дополняет дефолтными знаниями.
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            chat_id: ID чата (None для поиска только в дефолтных)
            n_results: Количество результатов
            include_defaults: Включать ли дефолтные знания
            
        Returns:
            Список фактов с приоритетом контекста чата
        """
        results = []
        
        # 1. Ищем в контексте чата (если указан)
        if chat_id is not None:
            chat_results = self.search_facts(
                collection_name=collection_name,
                query=query,
                n_results=n_results,
                where={"chat_id": chat_id}
            )
            for r in chat_results:
                r['source_type'] = 'chat'
            results.extend(chat_results)
        
        # 2. Дополняем дефолтными знаниями
        if include_defaults and len(results) < n_results:
            remaining = n_results - len(results)
            default_results = self.search_facts(
                collection_name=collection_name,
                query=query,
                n_results=remaining,
                where={"source": "default_knowledge"}
            )
            for r in default_results:
                r['source_type'] = 'default'
            results.extend(default_results)
        
        return results[:n_results]


# Глобальный экземпляр векторной БД
vector_db = VectorDB()