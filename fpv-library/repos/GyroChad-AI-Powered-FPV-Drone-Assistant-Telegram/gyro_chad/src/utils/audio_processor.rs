use std::path::PathBuf;
use tokio::process::Command;
use tokio::fs;

pub struct AudioProcessor;

impl AudioProcessor {
    pub fn new() -> Self {
        Self
    }

    pub async fn transcribe(&self, audio_path: PathBuf) -> Result<String, String> {
        if !audio_path.exists() {
            return Err(format!("Audio file not found: {:?}", audio_path));
        }

        let output = Command::new("whisper-ctranslate2")
            .arg(audio_path.to_str().unwrap())
            .arg("--model")
            .arg("base")
            .arg("--language")
            .arg("ru")
            .arg("--output_format")
            .arg("txt")
            .arg("--output_dir")
            .arg("/tmp")
            .output()
            .await;

        match output {
            Ok(result) => {
                if result.status.success() {
                    let stdout = String::from_utf8_lossy(&result.stdout);
                    let stderr = String::from_utf8_lossy(&result.stderr);
                    
                    let txt_path = audio_path.with_extension("txt");
                    let tmp_txt_path = PathBuf::from("/tmp").join(txt_path.file_name().unwrap());
                    
                    if tmp_txt_path.exists() {
                        let transcription = fs::read_to_string(&tmp_txt_path)
                            .await
                            .unwrap_or_else(|_| stderr.to_string());
                        
                        fs::remove_file(&tmp_txt_path).await.ok();
                        
                        log::info!("🎤 Transcription: {}", transcription);
                        Ok(transcription)
                    } else {
                        let combined = format!("{}\n{}", stdout, stderr);
                        log::info!("🎤 Whisper output: {}", combined);
                        Ok(combined)
                    }
                } else {
                    let error = String::from_utf8_lossy(&result.stderr);
                    Err(format!("Whisper failed: {}", error))
                }
            }
            Err(e) => {
                Err(format!("Whisper not installed or failed to execute: {}", e))
            }
        }
    }
}
