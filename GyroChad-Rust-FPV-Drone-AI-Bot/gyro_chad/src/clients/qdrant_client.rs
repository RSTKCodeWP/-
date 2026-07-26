use qdrant_client::{Qdrant, Payload};
use qdrant_client::qdrant::{
    CreateCollectionBuilder, Distance, VectorParamsBuilder,
    SearchPointsBuilder, ScoredPoint, PointStruct, UpsertPointsBuilder,
};
use serde_json::json;
use uuid::Uuid;

const COLLECTION_NAME: &str = "fpv_knowledge";
const VECTOR_SIZE: u64 = 768;

pub struct QdrantClient {
    client: Qdrant,
}

impl QdrantClient {
    pub async fn new(url: String) -> Result<Self, String> {
        let client = Qdrant::from_url(&url)
            .build()
            .map_err(|e| format!("Failed to connect to Qdrant: {}", e))?;

        Ok(Self { client })
    }

    pub async fn init_collection(&self) -> Result<(), String> {
        let exists = self.client
            .collection_exists(COLLECTION_NAME)
            .await
            .map_err(|e| format!("Failed to check collection: {}", e))?;

        if !exists {
            self.client
                .create_collection(
                    CreateCollectionBuilder::new(COLLECTION_NAME)
                        .vectors_config(VectorParamsBuilder::new(VECTOR_SIZE, Distance::Cosine))
                )
                .await
                .map_err(|e| format!("Failed to create collection: {}", e))?;

            log::info!("✅ Created Qdrant collection: {}", COLLECTION_NAME);
        } else {
            log::info!("✅ Qdrant collection already exists: {}", COLLECTION_NAME);
        }

        Ok(())
    }

    pub async fn search_similar(
        &self,
        query_vector: Vec<f32>,
        limit: u64,
    ) -> Result<Vec<(String, f32)>, String> {
        let search_result = self.client
            .search_points(
                SearchPointsBuilder::new(COLLECTION_NAME, query_vector, limit)
                    .with_payload(true)
            )
            .await
            .map_err(|e| format!("Qdrant search failed: {}", e))?;

        let results: Vec<(String, f32)> = search_result
            .result
            .into_iter()
            .filter_map(|point: ScoredPoint| {
                let payload = point.payload;
                payload.get("text")
                    .and_then(|v| v.as_str())
                    .map(|text| (text.to_string(), point.score))
            })
            .collect();

        Ok(results)
    }

    pub async fn get_collection_info(&self) -> Result<u64, String> {
        let info = self.client
            .collection_info(COLLECTION_NAME)
            .await
            .map_err(|e| format!("Failed to get collection info: {}", e))?;

        Ok(info.result.and_then(|r| r.points_count).unwrap_or(0))
    }

    pub async fn batch_upsert(
        &self,
        texts: Vec<String>,
        vectors: Vec<Vec<f32>>,
        metadata: Vec<serde_json::Value>,
    ) -> Result<usize, String> {
        if texts.len() != vectors.len() || texts.len() != metadata.len() {
            return Err("Mismatched lengths: texts, vectors, and metadata must have same length".to_string());
        }

        let points: Vec<PointStruct> = texts
            .into_iter()
            .zip(vectors.into_iter())
            .zip(metadata.into_iter())
            .map(|((text, vector), meta)| {
                let mut payload_json = meta;
                payload_json["text"] = json!(text);
                
                PointStruct::new(
                    Uuid::new_v4().to_string(),
                    vector,
                    Payload::try_from(payload_json).unwrap_or_default(),
                )
            })
            .collect();

        let total_points = points.len();

        self.client
            .upsert_points_chunked(
                UpsertPointsBuilder::new(COLLECTION_NAME, points).wait(true),
                100,
            )
            .await
            .map_err(|e| format!("Batch upsert failed: {}", e))?;

        Ok(total_points)
    }
}
