mod config;
mod clients;
mod handlers;
mod utils;
mod memory;

use teloxide::prelude::*;
use config::Config;
use clients::ollama_client::OllamaClient;
use clients::qdrant_client::QdrantClient;
use clients::rag_engine::RagEngine;
use handlers::telegram_handler::handle_message;
use memory::MemoryManager;

#[tokio::main]
async fn main() {
    env_logger::init();

    log::info!("🚀 GyroChad starting...");

    let config = Config::from_env().expect("Failed to load configuration");
    let bot = Bot::new(&config.telegram_token);
    
    let ollama_client = OllamaClient::new(
        config.ollama_url.clone(),
        config.embedding_model.clone(),
        config.llm_model.clone(),
        config.vision_model.clone(),
    );
    
    let qdrant_client = QdrantClient::new(config.qdrant_url.clone())
        .await
        .expect("Failed to connect to Qdrant");
    
    qdrant_client.init_collection()
        .await
        .expect("Failed to initialize Qdrant collection");
    
    let points_count = qdrant_client.get_collection_info()
        .await
        .unwrap_or(0);
    
    let memory_manager = MemoryManager::new(config.max_history_messages);
    
    let rag_engine = RagEngine::new(ollama_client, qdrant_client, memory_manager);

    log::info!("✅ Bot initialized. Username: @{}", config.bot_username);
    log::info!("🔗 Ollama endpoint: {}", config.ollama_url);
    log::info!("🔗 Qdrant endpoint: {}", config.qdrant_url);
    log::info!("📊 Knowledge base: {} vectors", points_count);

    let handler = Update::filter_message().endpoint(
        |bot: Bot, msg: Message| async move {
            let config = Config::from_env().expect("Config error");
            let ollama_client = OllamaClient::new(
                config.ollama_url.clone(),
                config.embedding_model.clone(),
                config.llm_model.clone(),
                config.vision_model.clone(),
            );
            let qdrant_client = QdrantClient::new(config.qdrant_url.clone())
                .await
                .expect("Qdrant connection failed");
            let memory_manager = MemoryManager::new(config.max_history_messages);
            let rag_engine = RagEngine::new(ollama_client, qdrant_client, memory_manager);
            
            handle_message(bot, msg, rag_engine, config).await
        }
    );

    Dispatcher::builder(bot, handler)
        .enable_ctrlc_handler()
        .build()
        .dispatch()
        .await;
}
