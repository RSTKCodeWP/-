use teloxide::{prelude::*, types::{ChatKind, MediaKind, MessageKind}};
use crate::clients::rag_engine::RagEngine;
use crate::utils::media_downloader::MediaDownloader;
use crate::utils::audio_processor::AudioProcessor;
use crate::utils::blackbox_parser::BlackboxParser;
use crate::config::Config;

pub async fn handle_message(
    bot: Bot,
    msg: Message,
    rag_engine: RagEngine,
    config: Config,
) -> ResponseResult<()> {
    let downloader = MediaDownloader::new();
    let audio_processor = AudioProcessor::new();
    let blackbox_parser = BlackboxParser::new();

    let should_process = match msg.chat.kind {
        ChatKind::Private(_) => true,
        ChatKind::Public(_) => {
            if let Some(reply) = msg.reply_to_message() {
                reply.from().map(|u| u.username.as_deref() == Some(&config.bot_username)).unwrap_or(false)
            } else if let Some(text) = msg.text() {
                text.contains(&format!("@{}", config.bot_username))
            } else {
                false
            }
        }
    };

    if !should_process {
        return Ok(());
    }

    match &msg.kind {
        MessageKind::Common(common_msg) => {
            match &common_msg.media_kind {
                MediaKind::Text(text_media) => {
                    let user_text = text_media.text.clone();
                    let chat_id = msg.chat.id.0;
                    log::info!("Received text from chat {}: {}", chat_id, user_text);

                    match rag_engine.query_with_context(chat_id, user_text).await {
                        Ok(response) => {
                            bot.send_message(msg.chat.id, response).await?;
                        }
                        Err(e) => {
                            log::error!("RAG error: {}", e);
                            bot.send_message(
                                msg.chat.id,
                                "⚠️ System unavailable. Check Ollama/Qdrant services"
                            ).await?;
                        }
                    }
                }
                MediaKind::Voice(voice_media) => {
                    let chat_id = msg.chat.id.0;
                    log::info!("Received voice message: {:?}", voice_media.voice.file.id);
                    let file = bot.get_file(&voice_media.voice.file.id).await?;
                    
                    match downloader.download_file(&bot, &file, "ogg").await {
                        Ok(audio_path) => {
                            match audio_processor.transcribe(audio_path).await {
                                Ok(transcription) => {
                                    log::info!("Transcription: {}", transcription);
                                    match rag_engine.query_with_context(chat_id, transcription).await {
                                        Ok(response) => {
                                            bot.send_message(msg.chat.id, response).await?;
                                        }
                                        Err(e) => {
                                            log::error!("RAG error: {}", e);
                                            bot.send_message(msg.chat.id, "⚠️ Failed to process query").await?;
                                        }
                                    }
                                }
                                Err(e) => {
                                    log::error!("Transcription error: {}", e);
                                    bot.send_message(msg.chat.id, "🎤 Voice received (Whisper unavailable)").await?;
                                }
                            }
                        }
                        Err(e) => {
                            log::error!("Download error: {}", e);
                            bot.send_message(msg.chat.id, "⚠️ Failed to download audio").await?;
                        }
                    }
                }
                MediaKind::Video(video_media) => {
                    log::info!("Received video: {:?}", video_media.video.file.id);
                    let file = bot.get_file(&video_media.video.file.id).await?;
                    downloader.download_file(&bot, &file, "mp4").await.ok();
                    bot.send_message(msg.chat.id, "🎥 Video received").await?;
                }
                MediaKind::VideoNote(video_note_media) => {
                    log::info!("Received video note: {:?}", video_note_media.video_note.file.id);
                    let file = bot.get_file(&video_note_media.video_note.file.id).await?;
                    downloader.download_file(&bot, &file, "mp4").await.ok();
                    bot.send_message(msg.chat.id, "⭕ Video note received").await?;
                }
                MediaKind::Photo(photo_media) => {
                    let chat_id = msg.chat.id.0;
                    if let Some(largest_photo) = photo_media.photo.last() {
                        log::info!("Received photo: {:?}", largest_photo.file.id);
                        let file = bot.get_file(&largest_photo.file.id).await?;
                        
                        match downloader.download_file(&bot, &file, "jpg").await {
                            Ok(image_path) => {
                                let caption = msg.caption().map(|s| s.to_string());
                                
                                match rag_engine.query_with_vision(chat_id, &image_path, caption).await {
                                    Ok(response) => {
                                        bot.send_message(msg.chat.id, format!("📷 {}", response)).await?;
                                    }
                                    Err(e) => {
                                        log::error!("Vision error: {}", e);
                                        bot.send_message(msg.chat.id, "⚠️ Vision model unavailable. Check Ollama llava").await?;
                                    }
                                }
                            }
                            Err(e) => {
                                log::error!("Download error: {}", e);
                                bot.send_message(msg.chat.id, "⚠️ Failed to download photo").await?;
                            }
                        }
                    }
                }
                MediaKind::Animation(animation_media) => {
                    log::info!("Received animation: {:?}", animation_media.animation.file.id);
                    let file = bot.get_file(&animation_media.animation.file.id).await?;
                    downloader.download_file(&bot, &file, "mp4").await.ok();
                    bot.send_message(msg.chat.id, "🎞️ Animation received").await?;
                }
                MediaKind::Document(document_media) => {
                    let chat_id = msg.chat.id.0;
                    let doc = &document_media.document;
                    
                    if let Some(file_name) = &doc.file_name {
                        if file_name.ends_with(".bbl") || file_name.ends_with(".BBL") {
                            log::info!("Received blackbox log: {}", file_name);
                            let file = bot.get_file(&doc.file.id).await?;
                            
                            match downloader.download_file(&bot, &file, "bbl").await {
                                Ok(bbl_path) => {
                                    bot.send_message(msg.chat.id, "🔄 Analyzing blackbox log...").await?;
                                    
                                    match blackbox_parser.process_blackbox(&bbl_path).await {
                                        Ok(analysis) => {
                                            let user_query = msg.caption()
                                                .map(|s| s.to_string())
                                                .unwrap_or_else(|| "Проанализируй этот лог полета".to_string());
                                            
                                            let augmented_query = format!("{}\n\n{}", analysis, user_query);
                                            
                                            match rag_engine.query_with_context(chat_id, augmented_query).await {
                                                Ok(response) => {
                                                    bot.send_message(msg.chat.id, response).await?;
                                                }
                                                Err(e) => {
                                                    log::error!("RAG error: {}", e);
                                                    bot.send_message(msg.chat.id, analysis).await?;
                                                }
                                            }
                                        }
                                        Err(e) => {
                                            log::error!("Blackbox analysis error: {}", e);
                                            bot.send_message(msg.chat.id, "⚠️ Failed to analyze blackbox log. Install blackbox_decode").await?;
                                        }
                                    }
                                }
                                Err(e) => {
                                    log::error!("Download error: {}", e);
                                    bot.send_message(msg.chat.id, "⚠️ Failed to download file").await?;
                                }
                            }
                        } else {
                            bot.send_message(msg.chat.id, "📄 Document received (only .bbl files supported)").await?;
                        }
                    }
                }
                _ => {}
            }
        }
        _ => {}
    }

    Ok(())
}
