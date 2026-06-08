//! Ducking de audio en Windows — baja volumen del dispositivo de salida durante TTS.

#[cfg(target_os = "windows")]
mod imp {
    use std::sync::{Mutex, Once};

    use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
    use windows::Win32::Media::Audio::{
        eMultimedia, eRender, IMMDeviceEnumerator, MMDeviceEnumerator,
    };
    use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CLSCTX_ALL, COINIT_APARTMENTTHREADED};

    static COM_INIT: Once = Once::new();
    static PREV_VOLUME: Mutex<Option<f32>> = Mutex::new(None);

    fn ensure_com() {
        COM_INIT.call_once(|| {
            unsafe {
                let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
            }
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

#[tauri::command]
pub fn duck_lmu(active: bool, level: Option<f32>) -> Result<(), String> {
    use std::sync::Mutex;
    static DUCK_SERIAL: Mutex<()> = Mutex::new(());
    let level = level.unwrap_or(0.2);
    std::thread::spawn(move || {
        let _guard = DUCK_SERIAL.lock().unwrap();
        let _ = imp::duck(active, level);
    });
    Ok(())
}
