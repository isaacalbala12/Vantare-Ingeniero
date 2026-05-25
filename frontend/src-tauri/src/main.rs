// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

// Estructura thread-safe para almacenar el proceso hijo del sidecar backend
struct BackendChild(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_websocket::init())
        .setup(|app| {
            // ================================================================
            // Sidecar backend Python
            //   DEBUG (dev):  se salta el spawn, backend se corre manualmente
            //                 con: cd backend && python run_dev.py
            //   RELEASE (prod): inicia automaticamente el sidecar empaquetado
            // ================================================================
            if cfg!(debug_assertions) {
                println!("[Rust] MODO DEBUG: Sidecar backend desactivado.");
                println!("[Rust] Inicia el backend manualmente con: python backend/run_dev.py");
                app.manage(BackendChild(Mutex::new(None)));
            } else {
                let shell = app.shell();
                println!("[Rust] Iniciando el sidecar backend...");
                
                match shell.sidecar("backend") {
                    Ok(command) => {
                        let configured_command = command.env("PORT", "8008");
                        
                        match configured_command.spawn() {
                            Ok((mut rx, child)) => {
                                app.manage(BackendChild(Mutex::new(Some(child))));
                                
                                tauri::async_runtime::spawn(async move {
                                    let mut is_ready = false;
                                    while let Some(event) = rx.recv().await {
                                        match event {
                                            tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                                                let s = String::from_utf8_lossy(&line);
                                                println!("[Backend STDOUT] {}", s.trim());
                                                
                                                if s.contains("Uvicorn running") || s.contains("Starting server") {
                                                    is_ready = true;
                                                    println!("[Rust] Backend sidecar confirmado y LISTO en el puerto 8008!");
                                                }
                                            }
                                            tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                                                let s = String::from_utf8_lossy(&line);
                                                eprintln!("[Backend STDERR] {}", s.trim());
                                            }
                                            tauri_plugin_shell::process::CommandEvent::Terminated(status) => {
                                                println!("[Backend] Detenido con código: {:?}", status.code);
                                            }
                                            _ => {}
                                        }
                                    }
                                    if !is_ready {
                                        eprintln!("[Rust] ERROR: El sidecar backend finalizó de forma prematura sin arrancar el servidor.");
                                    }
                                });
                                println!("[Rust] Hilo de monitorización del sidecar backend lanzado con éxito.");
                            }
                            Err(e) => {
                                eprintln!("[Rust] ERROR al spawnear el proceso sidecar: {:?}", e);
                                app.manage(BackendChild(Mutex::new(None)));
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("[Rust] ERROR al resolver el sidecar 'backend': {:?}", e);
                        app.manage(BackendChild(Mutex::new(None)));
                    }
                }
            }

            // 2. Configurar el menú de la bandeja del sistema (Tauri v2 Tray Icon)
            let hide_i = MenuItem::with_id(app, "hide", "Ocultar", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;
            
            let menu = Menu::with_items(app, &[&hide_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        // Forzar matado del sidecar al salir desde el menú tray
                        let state = app.state::<BackendChild>();
                        if let Some(child) = state.0.lock().unwrap().take() {
                            let _ = child.kill();
                            println!("[Rust] Sidecar backend matado antes de salir.");
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

            // 3. Pre-calentar permiso de micrófono en WebView2 (evita el bloqueo del message loop
            //    cuando se llama a getUserMedia() durante la pulsación PTT).
            //    Se ejecuta 5 segundos después del arranque via JS setTimeout en el propio eval.
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval(
                    r#"setTimeout(() => {
                        navigator.mediaDevices.getUserMedia({audio:true})
                            .then(s => s.getTracks().forEach(t => t.stop()))
                            .catch(() => {});
                    }, 5000)"#
                );
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            // 3. Captura del evento de cierre de ventana para apagar el sidecar
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if window.label() == "main" {
                    println!("[Rust] Ventana principal cerrada. Deteniendo sidecar backend...");
                    let state = window.state::<BackendChild>();
                    if let Some(child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                        println!("[Rust] Sidecar backend destruido. Adiós.");
                    };
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
