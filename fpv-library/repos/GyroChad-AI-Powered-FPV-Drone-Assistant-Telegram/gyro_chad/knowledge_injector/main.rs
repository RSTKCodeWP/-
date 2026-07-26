mod youtube_parser;
mod batch_whisper;
mod text_chunker;
mod qdrant_loader;

use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "knowledge_injector")]
#[command(about = "CLI tool for downloading, transcribing, and injecting knowledge into Qdrant", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Download {
        #[arg(short, long)]
        url: String,
        
        #[arg(short, long, default_value = "raw_audio")]
        output_dir: PathBuf,
    },
    
    Transcribe {
        #[arg(short, long, default_value = "raw_audio")]
        input_dir: PathBuf,
        
        #[arg(short, long, default_value = "raw_texts")]
        output_dir: PathBuf,
    },
    
    Inject {
        #[arg(short, long, default_value = "raw_texts")]
        input_dir: PathBuf,
        
        #[arg(short, long, default_value = "http://localhost:11434")]
        ollama_url: String,
        
        #[arg(short, long, default_value = "http://localhost:6333")]
        qdrant_url: String,
    },
    
    Full {
        #[arg(short, long)]
        url: String,
        
        #[arg(short, long, default_value = "http://localhost:11434")]
        ollama_url: String,
        
        #[arg(short, long, default_value = "http://localhost:6333")]
        qdrant_url: String,
    },
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();
    
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Download { url, output_dir } => {
            log::info!("📥 Downloading from: {}", url);
            youtube_parser::download_audio(&url, &output_dir).await?;
            log::info!("✅ Download complete");
        }
        
        Commands::Transcribe { input_dir, output_dir } => {
            log::info!("🎤 Transcribing audio files from: {:?}", input_dir);
            batch_whisper::transcribe_all(&input_dir, &output_dir).await?;
            log::info!("✅ Transcription complete");
        }
        
        Commands::Inject { input_dir, ollama_url, qdrant_url } => {
            log::info!("🚀 Injecting knowledge from: {:?}", input_dir);
            qdrant_loader::inject_knowledge(&input_dir, &ollama_url, &qdrant_url).await?;
            log::info!("✅ Knowledge injection complete");
        }
        
        Commands::Full { url, ollama_url, qdrant_url } => {
            log::info!("🔄 Running full pipeline for: {}", url);
            
            let audio_dir = PathBuf::from("raw_audio");
            let text_dir = PathBuf::from("raw_texts");
            
            youtube_parser::download_audio(&url, &audio_dir).await?;
            log::info!("✅ Download complete");
            
            batch_whisper::transcribe_all(&audio_dir, &text_dir).await?;
            log::info!("✅ Transcription complete");
            
            qdrant_loader::inject_knowledge(&text_dir, &ollama_url, &qdrant_url).await?;
            log::info!("✅ Knowledge injection complete");
            
            log::info!("🎉 Full pipeline finished successfully");
        }
    }
    
    Ok(())
}
