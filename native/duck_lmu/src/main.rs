#[cfg(target_os = "windows")]
mod imp {
    use std::sync::{Mutex, Once};

    use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
    use windows::Win32::Media::Audio::{eMultimedia, eRender, IMMDeviceEnumerator, MMDeviceEnumerator};
    use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CLSCTX_ALL, COINIT_APARTMENTTHREADED};

    static COM_INIT: Once = Once::new();
    static PREV_VOLUME: Mutex<Option<f32>> = Mutex::new(None);

    fn ensure_com() {
        COM_INIT.call_once(|| unsafe {
            let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
        });
    }

    pub fn duck(active: bool, level: f32) -> Result<(), String> {
        ensure_com();
        unsafe {
            let enumerator: IMMDeviceEnumerator =
                CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL)
                    .map_err(|e| format!("enumerator: {e}"))?;
            let device = enumerator
                .GetDefaultAudioEndpoint(eRender, eMultimedia)
                .map_err(|e| format!("endpoint: {e}"))?;
            let volume: IAudioEndpointVolume = device
                .Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None)
                .map_err(|e| format!("activate: {e}"))?;

            if active {
                let mut prev = PREV_VOLUME.lock().unwrap();
                if prev.is_none() {
                    *prev = Some(volume.GetMasterVolumeLevelScalar().map_err(|e| e.to_string())?);
                }
                volume
                    .SetMasterVolumeLevelScalar(level.clamp(0.0, 1.0), std::ptr::null())
                    .map_err(|e| e.to_string())?;
            } else if let Some(saved) = *PREV_VOLUME.lock().unwrap() {
                volume
                    .SetMasterVolumeLevelScalar(saved, std::ptr::null())
                    .map_err(|e| e.to_string())?;
                *PREV_VOLUME.lock().unwrap() = None;
            }
        }
        Ok(())
    }
}

#[cfg(not(target_os = "windows"))]
mod imp {
    pub fn duck(_active: bool, _level: f32) -> Result<(), String> {
        Ok(())
    }
}

fn parse_args() -> (bool, f32) {
    let mut active = false;
    let mut level = 0.65f32;
    let args: Vec<String> = std::env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--active" => {
                if let Some(v) = args.get(i + 1) {
                    active = v == "true" || v == "1";
                    i += 1;
                }
            }
            "--level" => {
                if let Some(v) = args.get(i + 1) {
                    level = v.parse().unwrap_or(0.65);
                    i += 1;
                }
            }
            _ => {}
        }
        i += 1;
    }
    (active, level)
}

fn main() {
    let (active, level) = parse_args();
    if let Err(err) = imp::duck(active, level) {
        eprintln!("[duck_lmu] {err}");
        std::process::exit(1);
    }
}
