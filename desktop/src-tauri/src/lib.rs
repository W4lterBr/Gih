mod motor;

use std::path::Path;
use std::sync::Mutex;
use tauri::{AppHandle, Manager};
use tauri_plugin_opener::OpenerExt;

/// Porta e token do motor (serviço local Python).
#[tauri::command]
fn motor_info(estado: tauri::State<motor::MotorState>) -> motor::MotorInfo {
    estado.0.lock().map(|m| m.clone()).unwrap_or_default()
}

/// Abre um arquivo (PDF, planilha) no programa padrão do Windows.
#[tauri::command]
fn abrir_arquivo(app: AppHandle, caminho: String) -> Result<(), String> {
    if !Path::new(&caminho).exists() {
        return Err(format!("Arquivo não encontrado: {caminho}"));
    }
    app.opener().open_path(caminho, None::<&str>).map_err(|e| e.to_string())
}

/// Abre o Explorer com o arquivo selecionado.
#[tauri::command]
fn mostrar_no_explorer(app: AppHandle, caminho: String) -> Result<(), String> {
    if !Path::new(&caminho).exists() {
        return Err(format!("Arquivo não encontrado: {caminho}"));
    }
    app.opener().reveal_item_in_dir(caminho).map_err(|e| e.to_string())
}

/// Abre um endereço (ex.: painel da cozinha) no navegador padrão.
#[tauri::command]
fn abrir_url(app: AppHandle, url: String) -> Result<(), String> {
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        return Err("Endereço inválido.".into());
    }
    app.opener().open_url(url, None::<&str>).map_err(|e| e.to_string())
}

fn mostrar_janela(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // Primeiro plugin: uma segunda cópia do app só traz a janela da primeira de volta
        // (dois motores disputariam a porta 5000 do painel da cozinha).
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| mostrar_janela(app)))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // O motor sobe em paralelo: a janela não espera por ele.
            let recursos = app.path().resource_dir().ok();
            app.manage(motor::MotorState(Mutex::new(motor::iniciar(recursos))));
            mostrar_janela(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            motor_info,
            abrir_arquivo,
            mostrar_no_explorer,
            abrir_url
        ])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar a Confeitaria");
}
