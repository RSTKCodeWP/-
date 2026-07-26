use std::path::Path;
use tokio::process::Command;
use tokio::fs;

pub async fn download_audio(url: &str, output_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    fs::create_dir_all(output_dir).await?;
    
    log::info!("🎬 Starting yt-dlp download...");
    
    let output = Command::new("yt-dlp")
        .arg("--extract-audio")
        .arg("--audio-format")
        .arg("wav")
        .arg("--audio-quality")
        .arg("0")
        .arg("--output")
        .arg(format!("{}/%(title)s.%(ext)s", output_dir.display()))
        .arg("--no-playlist")
        .arg("--ignore-errors")
        .arg(url)
        .output()
        .await?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("yt-dlp failed: {}", stderr).into());
    }
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    log::info!("yt-dlp output: {}", stdout);
    
    Ok(())
}

pub async fn download_playlist(url: &str, output_dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    fs::create_dir_all(output_dir).await?;
    
    log::info!("🎬 Starting yt-dlp playlist download...");
    
    let output = Command::new("yt-dlp")
        .arg("--extract-audio")
        .arg("--audio-format")
        .arg("wav")
        .arg("--audio-quality")
        .arg("0")
        .arg("--output")
        .arg(format!("{}/%(playlist_index)s-%(title)s.%(ext)s", output_dir.display()))
        .arg("--yes-playlist")
        .arg("--ignore-errors")
        .arg(url)
        .output()
        .await?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("yt-dlp failed: {}", stderr).into());
    }
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    log::info!("yt-dlp output: {}", stdout);
    
    Ok(())
}
