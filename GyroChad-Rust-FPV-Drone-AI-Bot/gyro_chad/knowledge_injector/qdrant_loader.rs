use std::path::Path;
use tokio::fs;
use walkdir::WalkDir;
use serde_json::json;

use gyro_chad::clients::ollama_client::OllamaClient;
use gyro_chad::clients::qdrant_client::QdrantClient;
use crate::text_chunker::TextChunker;

pub async fn inject_knowledge(
    input_dir: &Path,
    ollama_url: &str,
    qdrant_url: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let ollama_client = OllamaClient::new(
        ollama_url.to_string(),
        "nomic-embed-text".to_string(),
        "llama3".to_string(),
        "llava".to_string(),
    );
    
    let qdrant_client = QdrantClient::new(qdrant_url.to_string()).await?;
    qdrant_client.init_collection().await?;
    
    let text_files: Vec<_> = WalkDir::new(input_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .filter(|e| {
            e.path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| ext == "txt")
                .unwrap_or(false)
        })
        .collect();
    
    if text_files.is_empty() {
        log::warn!("⚠️  No text files found in {:?}", input_dir);
        return Ok(());
    }
    
    log::info!("📂 Found {} text files", text_files.len());
    
    let chunker = TextChunker::default();
    let mut all_chunks = Vec::new();
    let mut all_vectors = Vec::new();
    let mut all_metadata = Vec::new();
    
    for (idx, entry) in text_files.iter().enumerate() {
        let file_path = entry.path();
        let filename = file_path.file_name().unwrap().to_str().unwrap();
        
        log::info!("📄 Processing [{}/{}]: {}", idx + 1, text_files.len(), filename);
        
        let content = fs::read_to_string(file_path).await?;
        let chunks = chunker.chunk(&content);
        
        log::info!("  ✂️  Split into {} chunks", chunks.len());
        
        for (chunk_idx, chunk) in chunks.iter().enumerate() {
            match ollama_client.generate_embedding(chunk.clone()).await {
                Ok(vector) => {
                    all_chunks.push(chunk.clone());
                    all_vectors.push(vector);
                    all_metadata.push(json!({
                        "source": filename,
                        "chunk_index": chunk_idx,
                        "total_chunks": chunks.len(),
                    }));
                }
                Err(e) => {
                    log::error!("  ❌ Failed to generate embedding for chunk {}: {}", chunk_idx, e);
                }
            }
        }
        
        log::info!("  ✅ Vectorized {} chunks", chunks.len());
    }
    
    if all_chunks.is_empty() {
        log::warn!("⚠️  No chunks to upload");
        return Ok(());
    }
    
    log::info!("🚀 Uploading {} vectors to Qdrant...", all_chunks.len());
    
    let uploaded = qdrant_client
        .batch_upsert(all_chunks, all_vectors, all_metadata)
        .await?;
    
    log::info!("✅ Successfully uploaded {} vectors", uploaded);
    
    let total_points = qdrant_client.get_collection_info().await?;
    log::info!("📊 Total vectors in collection: {}", total_points);
    
    Ok(())
}
