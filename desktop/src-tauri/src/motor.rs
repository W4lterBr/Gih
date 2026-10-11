//! Inicia o motor Python da Confeitaria (`servico_local.py`, na raiz do projeto `app/`)
//! como processo em segundo plano e guarda porta + token para a interface usar.
//!
//! - Porta livre escolhida na hora, só em 127.0.0.1.
//! - Token aleatório por sessão (o serviço recusa requisições sem ele).
//! - O motor usa o mesmo banco do app PyQt (resolvido por `core/config.py`).
//! - Ao fechar a interface, o serviço se encerra sozinho (vigia o PID do pai).

use serde::Serialize;
use std::collections::hash_map::RandomState;
use std::fs::OpenOptions;
use std::hash::{BuildHasher, Hasher};
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::Mutex;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Raiz do projeto Python (`app/`); a interface fica em `app/desktop/`. Só vale em
/// desenvolvimento: o app instalado usa o motor empacotado.
fn raiz_projeto() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

#[derive(Clone, Serialize, Default)]
pub struct MotorInfo {
    pub porta: u16,
    pub token: String,
    pub erro: Option<String>,
}

pub struct MotorState(pub Mutex<MotorInfo>);

fn token_aleatorio() -> String {
    // RandomState é semeado pelo sistema operacional a cada instância.
    (0..4)
        .map(|i| {
            let mut h = RandomState::new().build_hasher();
            h.write_u64(i);
            h.write_u128(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map(|d| d.as_nanos())
                    .unwrap_or(0),
            );
            format!("{:016x}", h.finish())
        })
        .collect()
}

fn porta_livre() -> std::io::Result<u16> {
    Ok(TcpListener::bind("127.0.0.1:0")?.local_addr()?.port())
}

pub fn iniciar(pasta_recursos: Option<PathBuf>) -> MotorInfo {
    match tentar_iniciar(pasta_recursos) {
        Ok(info) => info,
        Err(e) => MotorInfo { erro: Some(e), ..Default::default() },
    }
}

/// O executável empacotado junto com o app instalado (`<recursos>/motor/confeitaria-motor.exe`)
/// ou, em desenvolvimento, o Python rodando `servico_local.py`.
enum Motor {
    Empacotado(PathBuf),
    Python { python: PathBuf, script: PathBuf },
}

fn localizar(pasta_recursos: Option<PathBuf>) -> Result<Motor, String> {
    if std::env::var("CONFEITARIA_MOTOR_PYTHON").is_err() {
        if let Some(exe) = pasta_recursos.map(|p| p.join("motor").join("confeitaria-motor.exe")) {
            if exe.exists() {
                return Ok(Motor::Empacotado(exe));
            }
        }
    }
    let script = std::env::var_os("CONFEITARIA_MOTOR_SCRIPT")
        .map(PathBuf::from)
        .unwrap_or_else(|| raiz_projeto().join("servico_local.py"));
    if !script.exists() {
        return Err(format!("servico_local.py não encontrado em {}", script.display()));
    }
    // Python: variável de ambiente, .venv do projeto, lançador "py" do Windows ou o do PATH.
    // ("python" sozinho no Windows costuma ser o atalho da Microsoft Store, que não roda nada.)
    let python = std::env::var_os("CONFEITARIA_MOTOR_PYTHON")
        .map(PathBuf::from)
        .or_else(|| {
            let venv = raiz_projeto().join(".venv").join("Scripts").join("python.exe");
            venv.exists().then_some(venv)
        })
        .or_else(|| {
            let windir = std::env::var_os("WINDIR").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(r"C:\Windows"));
            let py = windir.join("py.exe");
            py.exists().then_some(py)
        })
        .unwrap_or_else(|| PathBuf::from("python"));
    Ok(Motor::Python { python, script })
}

/// Pasta dos logs do motor: a mesma pasta de dados do app instalado.
fn pasta_logs() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    base.join("Confeitaria").join("logs")
}

fn tentar_iniciar(pasta_recursos: Option<PathBuf>) -> Result<MotorInfo, String> {
    let motor = localizar(pasta_recursos)?;
    let porta = porta_livre().map_err(|e| format!("Sem porta livre: {e}"))?;
    let token = token_aleatorio();

    let logs = pasta_logs();
    let _ = std::fs::create_dir_all(&logs);
    let saida = OpenOptions::new()
        .create(true)
        .append(true)
        .open(logs.join("servico_local.log"))
        .map_err(|e| e.to_string())?;
    let erro = saida.try_clone().map_err(|e| e.to_string())?;

    let mut cmd = match &motor {
        Motor::Empacotado(exe) => {
            let mut c = Command::new(exe);
            if let Some(p) = exe.parent() {
                c.current_dir(p);
            }
            c
        }
        Motor::Python { python, script } => {
            let mut c = Command::new(python);
            c.arg(script);
            if let Some(p) = script.parent() {
                c.current_dir(p);
            }
            c
        }
    };
    cmd.args(["--porta", &porta.to_string(), "--pai", &std::process::id().to_string()])
        .env("CONFEITARIA_TOKEN", &token)
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::null())
        .stdout(Stdio::from(saida))
        .stderr(Stdio::from(erro));
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    cmd.spawn().map_err(|e| format!("Não foi possível iniciar o motor: {e}"))?;
    Ok(MotorInfo { porta, token, erro: None })
}
