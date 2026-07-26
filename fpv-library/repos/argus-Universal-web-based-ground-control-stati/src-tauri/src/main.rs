#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Spawn Python backend as a sidecar process.
            // The binary is expected at src-tauri/binaries/python-backend-<target-triple>
            // (built via PyInstaller, see scripts/build_desktop.sh).
            let sidecar_command = app
                .shell()
                .sidecar("python-backend")
                .expect("failed to create sidecar command")
                .args(["--port", "8100"]);

            let (mut rx, _child) = sidecar_command
                .spawn()
                .expect("failed to spawn python backend sidecar");

            // Log sidecar stdout/stderr in debug builds
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let msg = String::from_utf8_lossy(&line);
                            if !msg.trim().is_empty() {
                                eprintln!("[backend] {}", msg.trim());
                            }
                        }
                        CommandEvent::Stderr(line) => {
                            let msg = String::from_utf8_lossy(&line);
                            if !msg.trim().is_empty() {
                                eprintln!("[backend:err] {}", msg.trim());
                            }
                        }
                        CommandEvent::Error(err) => {
                            eprintln!("[backend:error] {}", err);
                        }
                        CommandEvent::Terminated(status) => {
                            eprintln!("[backend] terminated: {:?}", status);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
