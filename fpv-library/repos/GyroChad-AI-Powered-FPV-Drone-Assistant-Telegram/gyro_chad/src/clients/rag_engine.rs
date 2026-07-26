use crate::clients::ollama_client::OllamaClient;
use crate::clients::qdrant_client::QdrantClient;
use crate::memory::MemoryManager;
use std::path::Path;

pub struct RagEngine {
    ollama_client: OllamaClient,
    qdrant_client: QdrantClient,
    memory_manager: MemoryManager,
}

impl RagEngine {
    pub fn new(ollama_client: OllamaClient, qdrant_client: QdrantClient, memory_manager: MemoryManager) -> Self {
        Self {
            ollama_client,
            qdrant_client,
            memory_manager,
        }
    }

    pub async fn query_with_context(&self, chat_id: i64, user_query: String) -> Result<String, String> {
        self.memory_manager.add_user_message(chat_id, user_query.clone());

        let query_embedding = self.ollama_client
            .generate_embedding(user_query.clone())
            .await
            .map_err(|e| format!("Failed to generate query embedding: {}", e))?;

        let search_results = self.qdrant_client
            .search_similar(query_embedding, 3)
            .await
            .map_err(|e| format!("Failed to search Qdrant: {}", e))?;

        let context = if search_results.is_empty() {
            log::warn!("No context found in Qdrant");
            String::from("(База знаний пуста)")
        } else {
            search_results
                .iter()
                .enumerate()
                .map(|(i, (text, score))| format!("[{}] (relevance: {:.2}) {}", i + 1, score, text))
                .collect::<Vec<_>>()
                .join("\n\n")
        };

        let history = self.memory_manager.format_history(chat_id);
        let history_section = if history.is_empty() {
            String::new()
        } else {
            format!("\n\nИСТОРИЯ ДИАЛОГА:\n{}\n", history)
        };

        let augmented_prompt = format!(
            r#"Ты GyroChad — эксперт по FPV-дронам. Отвечай на основе контекста и истории диалога.

КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{}{}
ТЕКУЩИЙ ВОПРОС:
{}

ОТВЕТ:"#,
            context, history_section, user_query
        );

        log::info!("RAG: {} chunks, history: {} msgs", search_results.len(), self.memory_manager.get_history(chat_id).len());

        let response = self.ollama_client.generate(augmented_prompt).await?;
        
        self.memory_manager.add_assistant_message(chat_id, response.clone());

        Ok(response)
    }

    pub async fn query_with_vision(&self, chat_id: i64, image_path: &Path, user_prompt: Option<String>) -> Result<String, String> {
        let prompt = user_prompt.unwrap_or_else(|| 
            "Проанализируй этот скриншот настроек FPV-дрона. Опиши что видишь и дай рекомендации.".to_string()
        );

        self.memory_manager.add_user_message(chat_id, format!("[IMAGE] {}", prompt));

        let response = self.ollama_client
            .generate_with_vision(prompt, image_path)
            .await?;

        self.memory_manager.add_assistant_message(chat_id, response.clone());

        Ok(response)
    }

    pub fn clear_memory(&self, chat_id: i64) {
        self.memory_manager.clear_history(chat_id);
    }
}
