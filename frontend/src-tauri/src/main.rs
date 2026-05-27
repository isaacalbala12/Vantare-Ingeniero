// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::sync::Mutex;
use std::time::Duration;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

// Estructuras thread-safe para almacenar los procesos hijos
struct BackendChild(Mutex<Option<CommandChild>>);
struct SidecarChild(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_websocket::init())
        .setup(|app| {
            // ================================================================
            // Sidecars Python
            //   DEBUG (dev):  se salta el spawn, sidecars se corren manualmente
            //   RELEASE (prod): inicia automaticamente los sidecars empaquetados
            // ================================================================
            if cfg!(debug_assertions) {
                println!("[Rust] MODO DEBUG: Sidecars desactivados.");
                println!("[Rust] Inicia el backend manualmente con: python backend/run_dev.py");
                println!("[Rust] Inicia el strategy-sidecar manualmente si lo necesitas.");
                app.manage(BackendChild(Mutex::new(None)));
                app.manage(SidecarChild(Mutex::new(None)));
            } else {
                let shell = app.shell();

                // --- vantare-engine (backend FastAPI) ---
                println!("[Rust] Iniciando el sidecar vantare-engine...");
                match shell.sidecar("vantare-engine") {
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
                    }
                    Err(e) => {
                        eprintln!("[Rust] ERROR al resolver el sidecar 'vantare-engine': {:?}", e);
                        app.manage(BackendChild(Mutex::new(None)));
                    }
                }

                // --- strategy-sidecar (lector LMU) ---
                println!("[Rust] Iniciando el sidecar strategy-sidecar...");
                match shell.sidecar("strategy-sidecar") {
                    Ok(command) => {
                        match command.spawn() {
                            Ok((mut rx, child)) => {
                                app.manage(SidecarChild(Mutex::new(Some(child))));
                                tauri::async_runtime::spawn(async move {
                                    while let Some(event) = rx.recv().await {
                                        match event {
                                            tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                                                let s = String::from_utf8_lossy(&line);
                                                println!("[strategy-sidecar STDOUT] {}", s.trim());
                                            }
                                            tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                                                let s = String::from_utf8_lossy(&line);
                                                eprintln!("[strategy-sidecar STDERR] {}", s.trim());
                                            }
                                            tauri_plugin_shell::process::CommandEvent::Terminated(status) => {
                                                println!("[strategy-sidecar] Detenido con codigo: {:?}", status.code);
                                            }
                                            _ => {}
                                        }
                                    }
                                });
                                println!("[Rust] Hilo de monitorizacion de strategy-sidecar lanzado con exito.");
                            }
                            Err(e) => {
                                eprintln!("[Rust] ERROR al spawnear strategy-sidecar: {:?}", e);
                                app.manage(SidecarChild(Mutex::new(None)));
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("[Rust] ERROR al resolver el sidecar 'strategy-sidecar': {:?}", e);
                        app.manage(SidecarChild(Mutex::new(None)));
                    }
                }

                // --- Health check loop: verificar que vantare-engine responde en puerto 8008 ---
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

            // 2. Configurar el menu de la bandeja del sistema (Tauri v2 Tray Icon)
            let hide_i = MenuItem::with_id(app, "hide", "Ocultar", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;
            
            let menu = Menu::with_items(app, &[&hide_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        // Forzar matado de ambos sidecars al salir desde el menu tray
                        let backend_state = app.state::<BackendChild>();
                        if let Some(child) = backend_state.0.lock().unwrap().take() {
                            let _ = child.kill();
                            println!("[Rust] vantare-engine matado antes de salir.");
                        }
                        let sidecar_state = app.state::<SidecarChild>();
                        if let Some(child) = sidecar_state.0.lock().unwrap().take() {
                            let _ = child.kill();
                            println!("[Rust] strategy-sidecar matado antes de salir.");
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

            // 3. Pre-calentar permiso de microfono en WebView2 (evita el bloqueo del message loop
            //    cuando se llama a getUserMedia() durante la pulsacion PTT).
            //    Se ejecuta 5 segundos despues del arranque via JS setTimeout en el propio eval.
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
            // 3. Captura del evento de cierre de ventana para apagar ambos sidecars
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if window.label() == "main" {
                    println!("[Rust] Ventana principal cerrada. Deteniendo sidecars...");
                    let backend_state = window.state::<BackendChild>();
                    if let Some(child) = backend_state.0.lock().unwrap().take() {
                        let _ = child.kill();
                        println!("[Rust] vantare-engine destruido.");
                    };
                    let sidecar_state = window.state::<SidecarChild>();
                    if let Some(child) = sidecar_state.0.lock().unwrap().take() {
                        let _ = child.kill();
                        println!("[Rust] strategy-sidecar destruido.");
                    };
                    println!("[Rust] Adios.");
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}