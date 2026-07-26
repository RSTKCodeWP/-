use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub telegram_token: String,
    pub ollama_url: String,
    pub bot_username: String,
    pub qdrant_url: String,
    pub embedding_model: String,
    pub vision_model: String,
    pub llm_model: String,
    pub max_history_messages: usize,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        dotenv::dotenv().ok();

        let telegram_token = env::var("TELOXIDE_TOKEN")
            .map_err(|_| "TELOXIDE_TOKEN not set in environment")?;
        
        let ollama_url = env::var("OLLAMA_URL")
            .unwrap_or_else(|_| "http://localhost:11434".to_string());
        
        let bot_username = env::var("BOT_USERNAME")
            .map_err(|_| "BOT_USERNAME not set in environment")?;

        let qdrant_url = env::var("QDRANT_URL")
            .unwrap_or_else(|_| "http://localhost:6334".to_string());

        let embedding_model = env::var("EMBEDDING_MODEL")
            .unwrap_or_else(|_| "nomic-embed-text".to_string());

        let vision_model = env::var("VISION_MODEL")
            .unwrap_or_else(|_| "llava".to_string());

        let llm_model = env::var("LLM_MODEL")
            .unwrap_or_else(|_| "llama3".to_string());

        let max_history_messages = env::var("MAX_HISTORY_MESSAGES")
            .unwrap_or_else(|_| "10".to_string())
            .parse()
            .unwrap_or(10);

        Ok(Config {
            telegram_token,
            ollama_url,
            bot_username,
            qdrant_url,
            embedding_model,
            vision_model,
            llm_model,
            max_history_messages,
        })
    }
}
