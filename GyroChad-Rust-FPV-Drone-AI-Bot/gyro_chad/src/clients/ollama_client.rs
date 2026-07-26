use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use std::path::Path;
use tokio::fs;

#[derive(Serialize)]
struct OllamaRequest {
    model: String,
    prompt: String,
    stream: bool,
}

#[derive(Deserialize)]
struct OllamaResponse {
    response: String,
}

#[derive(Serialize)]
struct OllamaEmbeddingRequest {
    model: String,
    prompt: String,
}

#[derive(Deserialize)]
struct OllamaEmbeddingResponse {
    embedding: Vec<f32>,
}

#[derive(Serialize)]
struct OllamaVisionRequest {
    model: String,
    prompt: String,
    images: Vec<String>,
    stream: bool,
}

pub struct OllamaClient {
    client: Client,
    base_url: String,
    embedding_model: String,
    llm_model: String,
    vision_model: String,
}

impl OllamaClient {
    pub fn new(base_url: String, embedding_model: String, llm_model: String, vision_model: String) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(120))
            .build()
            .expect("Failed to build HTTP client");

        Self { 
            client, 
            base_url, 
            embedding_model,
            llm_model,
            vision_model,
        }
    }

    pub async fn generate(&self, prompt: String) -> Result<String, String> {
        let url = format!("{}/api/generate", self.base_url);
        
        let request_body = OllamaRequest {
            model: self.llm_model.clone(),
            prompt,
            stream: false,
        };

        let response = self.client
            .post(&url)
            .json(&request_body)
            .send()
            .await
            .map_err(|e| format!("Ollama request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Ollama returned status: {}", response.status()));
        }

        let ollama_response: OllamaResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse Ollama response: {}", e))?;

        Ok(ollama_response.response)
    }

    pub async fn generate_with_vision(&self, prompt: String, image_path: &Path) -> Result<String, String> {
        let image_bytes = fs::read(image_path)
            .await
            .map_err(|e| format!("Failed to read image: {}", e))?;
        
        let base64_image = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &image_bytes);
        
        let url = format!("{}/api/generate", self.base_url);
        
        let request_body = OllamaVisionRequest {
            model: self.vision_model.clone(),
            prompt,
            images: vec![base64_image],
            stream: false,
        };

        let response = self.client
            .post(&url)
            .json(&request_body)
            .send()
            .await
            .map_err(|e| format!("Ollama vision request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Ollama vision returned status: {}", response.status()));
        }

        let ollama_response: OllamaResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse vision response: {}", e))?;

        Ok(ollama_response.response)
    }

    pub async fn generate_embedding(&self, text: String) -> Result<Vec<f32>, String> {
        let url = format!("{}/api/embeddings", self.base_url);
        
        let request_body = OllamaEmbeddingRequest {
            model: self.embedding_model.clone(),
            prompt: text,
        };

        let response = self.client
            .post(&url)
            .json(&request_body)
            .send()
            .await
            .map_err(|e| format!("Ollama embedding request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(format!("Ollama embedding returned status: {}", response.status()));
        }

        let embedding_response: OllamaEmbeddingResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse embedding response: {}", e))?;

        Ok(embedding_response.embedding)
    }
}
