// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod audio_duck;

use std::net::TcpStream;
use std::sync::Mutex;
use std::time::Duration;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

struct BackendChild(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_websocket::init())
        .invoke_handler(tauri::generate_handler![audio_duck::duck_lmu])
        .setup(|app| {
            // ================================================================
            // Backend (vantare-engine)
            //   DEBUG (dev):  manual — python backend/run_dev.py or scripts/dev.ps1
            //   RELEASE (prod): Tauri spawns backend.exe with native telemetry
            // ================================================================
            if cfg!(debug_assertions) {
                println!("[Rust] MODO DEBUG: backend no se auto-inicia.");
                println!("[Rust] Inicia el backend con: .\\scripts\\dev.ps1");
                app.manage(BackendChild(Mutex::new(None)));
            } else {
                let resource_dir = match app.path().resource_dir() {
                    Ok(dir) => dir,
                    Err(e) => {
                        eprintln!("[Rust] ERROR al obtener resource dir: {}", e);
                        app.manage(BackendChild(Mutex::new(None)));
                        return Ok(());
                    }
                };
                let shell = app.shell();

                let backend_path = resource_dir.join("backend").join("backend.exe");
                println!("[Rust] Iniciando vantare-engine desde: {:?}", backend_path);
                let command = shell.command(backend_path.to_str().unwrap_or("backend.exe"));
                match command
                    .env("PORT", "8008")
                    .env("VANTARE_NATIVE_TELEMETRY", "1")
                    .spawn()
                {
                    Ok((mut rx, child)) => {
                        app.manage(BackendChild(Mutex::new(Some(child))));
                        tauri::async_runtime::spawn(async move {
                            let mut is_ready = false;
                            while let Some(event) = rx.recv().await {
                                match event {
                                    tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                                        let s = String::from_utf8_lossy(&line);
                                        println!("[vantare-engine STDOUT] {}", s.trim());
                                        if s.contains("Uvicorn running") || s.contains("Starting server") {
                                            is_ready = true;
                                            println!("[Rust] vantare-engine confirmado y LISTO en el puerto 8008!");
                                        }
                                    }
                                    tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                                        let s = String::from_utf8_lossy(&line);
                                        eprintln!("[vantare-engine STDERR] {}", s.trim());
                                    }
                                    tauri_plugin_shell::process::CommandEvent::Terminated(status) => {
                                        println!("[vantare-engine] Detenido con código: {:?}", status.code);
                                    }
                                    _ => {}
                                }
                            }
                            if !is_ready {
                                eprintln!("[Rust] ERROR: vantare-engine finalizo de forma prematura sin arrancar el servidor.");
                            }
                        });
                        println!("[Rust] Hilo de monitorizacion de vantare-engine lanzado con exito.");
                    }
                    Err(e) => {
                        eprintln!("[Rust] ERROR al spawnear vantare-engine: {:?}", e);
                        app.manage(BackendChild(Mutex::new(None)));
                    }
                }

                tauri::async_runtime::spawn(async {
                    let backend_addr = "127.0.0.1:8008";
                    let timeout = Duration::from_secs(2);
                    let mut consecutive_failures = 0u8;
                    loop {
                        tokio::time::sleep(Duration::from_secs(5)).await;
                        match TcpStream::connect_timeout(&backend_addr.parse().unwrap(), timeout) {
                            Ok(_) => {
                                if consecutive_failures > 0 {
                                    println!("[Rust] Health check OK: vantare-engine responde en 8008");
                                    consecutive_failures = 0;
                                }
                            }
                            Err(_) => {
                                consecutive_failures += 1;
                                eprintln!("[Rust] Health check FAIL: vantare-engine no responde en 8008 (intento {})", consecutive_failures);
                            }
                        }
                    }
                });
            }

            let hide_i = MenuItem::with_id(app, "hide", "Ocultar", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;

            let menu = Menu::with_items(app, &[&hide_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        let backend_state = app.state::<BackendChild>();
                        if let Some(child) = backend_state.0.lock().unwrap().take() {
                            let _ = child.kill();
                            println!("[Rust] vantare-engine matado antes de salir.");
                        }
                        app.exit(0);
                    }
                    "hide" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.hide();
                        }
                    }
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if window.label() == "main" {
                    println!("[Rust] Ventana principal cerrada. Deteniendo backend...");
                    let backend_state = window.state::<BackendChild>();
                    if let Some(child) = backend_state.0.lock().unwrap().take() {
                        let _ = child.kill();
                        println!("[Rust] vantare-engine destruido.");
                    }
                    println!("[Rust] Adios.");
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
