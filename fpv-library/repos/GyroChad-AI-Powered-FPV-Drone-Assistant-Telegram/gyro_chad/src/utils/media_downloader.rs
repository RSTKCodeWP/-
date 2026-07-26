use teloxide::Bot;
use teloxide::types::File as TgFile;
use teloxide::net::Download;
use tokio::fs;
use std::path::PathBuf;
use chrono::Utc;

pub struct MediaDownloader {
    media_dir: PathBuf,
}

impl MediaDownloader {
    pub fn new() -> Self {
        let media_dir = PathBuf::from("temp_media");
        Self { media_dir }
    }

    pub async fn ensure_media_dir(&self) -> Result<(), String> {
        fs::create_dir_all(&self.media_dir)
            .await
            .map_err(|e| format!("Failed to create media directory: {}", e))
    }

    pub async fn download_file(
        &self,
        bot: &Bot,
        file: &TgFile,
        extension: &str,
    ) -> Result<PathBuf, String> {
        self.ensure_media_dir().await?;

        let timestamp = Utc::now().timestamp_millis();
        let filename = format!("{}_{}.{}", timestamp, &file.id, extension);
        let file_path = self.media_dir.join(&filename);

        let mut output_file = fs::File::create(&file_path)
            .await
            .map_err(|e| format!("Failed to create file: {}", e))?;

        bot.download_file(&file.path, &mut output_file)
            .await
            .map_err(|e| format!("Failed to download file: {}", e))?;

        log::info!("Downloaded file: {:?}", file_path);
        Ok(file_path)
    }
}
