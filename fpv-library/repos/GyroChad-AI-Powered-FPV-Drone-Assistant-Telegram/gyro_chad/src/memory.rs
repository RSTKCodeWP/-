use moka::sync::Cache;
use std::collections::VecDeque;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

impl ChatMessage {
    pub fn user(content: String) -> Self {
        Self {
            role: "user".to_string(),
            content,
        }
    }

    pub fn assistant(content: String) -> Self {
        Self {
            role: "assistant".to_string(),
            content,
        }
    }
}

pub struct MemoryManager {
    cache: Cache<i64, VecDeque<ChatMessage>>,
    max_messages: usize,
}

impl MemoryManager {
    pub fn new(max_messages: usize) -> Self {
        Self {
            cache: Cache::new(1000),
            max_messages,
        }
    }

    pub fn add_message(&self, chat_id: i64, message: ChatMessage) {
        let mut history = self.cache.get(&chat_id).unwrap_or_else(|| VecDeque::new());
        
        history.push_back(message);
        
        while history.len() > self.max_messages {
            history.pop_front();
        }
        
        self.cache.insert(chat_id, history);
    }

    pub fn add_user_message(&self, chat_id: i64, content: String) {
        self.add_message(chat_id, ChatMessage::user(content));
    }

    pub fn add_assistant_message(&self, chat_id: i64, content: String) {
        self.add_message(chat_id, ChatMessage::assistant(content));
    }

    pub fn get_history(&self, chat_id: i64) -> Vec<ChatMessage> {
        self.cache
            .get(&chat_id)
            .map(|deque| deque.iter().cloned().collect())
            .unwrap_or_default()
    }

    pub fn clear_history(&self, chat_id: i64) {
        self.cache.invalidate(&chat_id);
    }

    pub fn format_history(&self, chat_id: i64) -> String {
        let history = self.get_history(chat_id);
        
        if history.is_empty() {
            return String::new();
        }

        history
            .iter()
            .map(|msg| format!("{}: {}", msg.role.to_uppercase(), msg.content))
            .collect::<Vec<_>>()
            .join("\n")
    }
}
