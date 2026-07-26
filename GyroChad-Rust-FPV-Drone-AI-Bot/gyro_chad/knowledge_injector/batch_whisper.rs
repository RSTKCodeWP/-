use std::path::{Path, PathBuf};
use tokio::process::Command;
use tokio::fs;
use walkdir::WalkDir;

pub async fn transcribe_all(input_dir: &Path, output_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    fs::create_dir_all(output_dir).await?;
    
    let audio_files: Vec<PathBuf> = WalkDir::new(input_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .filter(|e| {
            e.path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| matches!(ext, "wav" | "ogg" | "mp3" | "m4a"))
                .unwrap_or(false)
        })
        .map(|e| e.path().to_path_buf())
        .collect();
    
    if audio_files.is_empty() {
        log::warn!("⚠️  No audio files found in {:?}", input_dir);
        return Ok(());
    }
    
    log::info!("📂 Found {} audio files", audio_files.len());
    
    for (idx, audio_path) in audio_files.iter().enumerate() {
        log::info!("🎤 Transcribing [{}/{}]: {:?}", idx + 1, audio_files.len(), audio_path.file_name().unwrap());
        
        match transcribe_single(audio_path, output_dir).await {
            Ok(text) => {
                log::info!("✅ Transcribed: {} chars", text.len());
            }
            Err(e) => {
                log::error!("❌ Failed to transcribe {:?}: {}", audio_path, e);
            }
        }
    }
    
    Ok(())
}

async fn transcribe_single(audio_path: &Path, output_dir: &Path) -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("whisper-ctranslate2")
        .arg(audio_path.to_str().unwrap())
        .arg("--model")
        .arg("base")
        .arg("--language")
        .arg("ru")
        .arg("--output_format")
        .arg("txt")
        .arg("--output_dir")
        .arg(output_dir.to_str().unwrap())
        .output()
        .await?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Whisper failed: {}", stderr).into());
    }
    
    let txt_filename = audio_path.file_stem().unwrap().to_str().unwrap();
    let txt_path = output_dir.join(format!("{}.txt", txt_filename));
    
    if txt_path.exists() {
        let transcription = fs::read_to_string(&txt_path).await?;
        Ok(transcription)
    } else {
        Err("Transcription file not found".into())
    }
}
