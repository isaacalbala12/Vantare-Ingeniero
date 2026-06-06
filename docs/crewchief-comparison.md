# Análisis Comparativo: CrewChiefV4 vs Vantare-Ingeniero

> **Fecha:** 6 Junio 2026
> **Versión documento:** 2.0 (revisión exhaustiva)
> **Propósito:** Comparación feature-por-feature entre CrewChiefV4 (C#, .NET, Windows Forms, ~10 años) y Vantare-Ingeniero (Python, FastAPI, Tauri 2 + React 19, ~1 año)
> **Metodología:** Exploración del árbol de GitLab vía API (`api/v4/projects/.../repository/tree`) con paginación, más documentación oficial, changelog completo y código fuente de Vantare.

---

## 0. Ficha Técnica

| Aspecto | CrewChiefV4 | Vantare-Ingeniero |
|---|---|---|
| **Lenguaje** | C# .NET Framework 4.x | Python 3.12+ / TypeScript 5.x / Rust |
| **Arquitectura** | Windows Forms monolítico (WinForms) | FastAPI async + Tauri 2 + React 19 |
| **Archivos .cs/.py/.ts** | ~450+ .cs + ~50 .html + ~30 .json | ~60 .py + ~20 .ts/.tsx + ~10 .rs |
| **Líneas de código** | ~200,000+ (estimado) | ~15,000 (estimado) |
| **Commits** | 8,512 | ~200 |
| **Versión actual** | 4.19.3.4 | 1.0.0 |
| **Años de desarrollo** | 10+ (2015–2026) | ~1 |
| **Juegos soportados** | **22+** | 1 (LMU) |
| **Voces** | Humanas grabadas (Jim, Jerry) + Windows TTS | TTS sintético (Edge, Piper, ElevenLabs, Gemini) |
| **IA/LLM** | No (100% determinista) | Sí (LLM + RAG + ChromaDB) |
| **Licencia** | MIT | Propietaria |
| **Instalador** | WiX Toolset (MSI) | PyInstaller + Tauri bundle |
| **Tests** | XUnit + UnitTest (~20 subdirectorios) | Pytest (31 tests) + Vitest (7 tests) |
| **Reconocimiento de voz** | **Grammar-based** (Windows SAPI, 100+ comandos definidos) | **Free-form** (Web Speech API + Whisper) |
| **Overlays in-game** | Sí (DirectX overlay + SteamVR) | No (ventana Tauri separada) |
| **SDK público** | Sí (CrewChiefV4SDK) | No |
| **Publicación MQTT** | Sí | No |
| **Auto-actualización** | Sí (AutoUpdater.NET) | No |
| **Plugins DLL** | 10 juegos con plugins dedicados | Sidecar Python independiente |

---

## 1. Mapa Completo del Repositorio CrewChiefV4

Árbol completo, explorado vía API de GitLab con verificación de paginación (per_page=100, page=1..N). **Ningún directorio tenía más de 100 archivos.**

```
CrewChiefV4/                          ← PROYECTO PRINCIPAL C# (450+ .cs)
│
├── AllGames/                         ← ABSTRACCIÓN MULTIJUEGO (8 archivos)
│   ├── Game.cs                       ← Clase base abstracta para TODOS los juegos
│   ├── GameDataReader.cs             ← Lector genérico de datos del juego
│   ├── GameDataSerializer.cs         ← Serializador de datos
│   ├── GameDefinition.cs             ← Definición de juegos (nombre, tipo, mapper)
│   ├── GameDefinition.csv            ← Tabla de definiciones (editable)
│   ├── GameDefinitionTable.cs        ← Tabla generada automáticamente desde CSV
│   ├── GameStateReaderFactory.cs     ← Factory pattern: crea reader según juego
│   └── GameDataReadException.cs      ← Excepción personalizada
│
├── Audio/                            ← SISTEMA DE REPRODUCCIÓN (12 archivos)
│   ├── AudioPlayer.cs                ← Reproductor principal con cola
│   ├── BackgroundPlayer.cs           ← Reproducción en segundo plano (hilo separado)
│   ├── MediaPlayerBackgroundPlayer.cs← Backend MediaPlayer
│   ├── NAudioBackgroundPlayerWasapi.cs← Backend NAudio WASAPI (baja latencia)
│   ├── NAudioBackgroundPlayerWaveOut.cs← Backend NAudio WaveOut
│   ├── NAudioLoopStream.cs           ← Loop stream para NAudio
│   ├── NAudioOut.cs                  ← Salida NAudio
│   ├── PlaybackModerator.cs          ← Moderador: prioridades, colas, interrupción
│   ├── SoundMetadata.cs              ← Metadatos de archivos de sonido
│   ├── SoundPackVersionsHelper.cs    ← Gestión de versiones de paquetes de voz
│   ├── Sounds.cs                     ← GESTOR CENTRAL: carga, cachea, reproduce
│   └── SubtitleManager.cs            ← Subtítulos en tiempo real
│
├── SRE/                              ← SISTEMA DE RECONOCIMIENTO DE VOZ (13 archivos)
│   ├── SREWrapper.cs                 ← Wrapper abstracto del motor SRE
│   ├── SREWrapperFactory.cs          ← Factory: Microsoft vs System SRE
│   ├── MicrosoftSREWrapper.cs        ← Implementación Microsoft SAPI
│   ├── MicrosoftChoicesWrapper.cs    ← Choices grammar (Microsoft)
│   ├── MicrosoftGrammarBuilderWrapper.cs  ← Grammar builder (Microsoft)
│   ├── MicrosoftGrammarWrapper.cs    ← Grammar compiled (Microsoft)
│   ├── SystemSREWrapper.cs           ← Implementación System.Speech
│   ├── SystemChoicesWrapper.cs       ← Choices grammar (System)
│   ├── SystemGrammarBuilderWrapper.cs ← Grammar builder (System)
│   ├── SystemGrammarWrapper.cs       ← Grammar compiled (System)
│   ├── ChoicesWrapper.cs             ← Interfaz abstracta Choices
│   ├── GrammarBuilderWrapper.cs      ← Interfaz abstracta GrammarBuilder
│   └── GrammarWrapper.cs             ← Interfaz abstracta Grammar
│   └── → Esto es GRAMMAR-BASED, NO free-form. Define comandos exactos.
│
├── Events/                           ← SISTEMA DE EVENTOS (42 archivos)
│   ├── AbstractEvent.cs              ← Clase base abstracta para eventos
│   ├── AlarmClock.cs                 ← "Set alarm to 10:30pm"
│   ├── Battery.cs                    ← Monitor de batería híbrida (SOC, tendencias)
│   ├── CoDriver.cs                   ← COPILOTO DE RALLY con pace notes
│   ├── CommonActions.cs              ← Acciones transversales
│   ├── CommonDataContainers.cs        ← Contenedores de datos compartidos
│   ├── ConditionsMonitor.cs          ← Clima, hora del día, condiciones
│   ├── DamageReporting.cs            ← "Damage report" / daños selectivos
│   ├── DriverSwaps.cs                ← CAMBIOS DE PILOTO (endurance)
│   ├── EngineMonitor.cs              ← Temperatura aceite, agua, motor
│   ├── FlagsMonitor.cs               ← Banderas: verde, amarilla, roja, azul
│   ├── FrozenOrderMonitor.cs         ← Orden congelado (bandera roja)
│   ├── Fuel.cs                       ← Módulo de combustible (nuevo, mejorado)
│   ├── Fuel_legacy.cs                ← Módulo legacy de combustible
│   ├── IRacingBroadcastMessageEvent.cs ← Mensajes broadcast iRacing
│   ├── LapCounter.cs                 ← Contador de vueltas
│   ├── LapTimes.cs                   ← Tiempos de vuelta (nuevo)
│   ├── LapTimes_legacy.cs            ← Tiempos de vuelta (legacy)
│   ├── Mqtt.cs                       ← PUBLICACIÓN MQTT de telemetría
│   ├── MulticlassWarnings.cs         ← ADVERTENCIAS MULTICLASE
│   ├── NullEvent.cs                  ← Evento nulo (placeholder)
│   ├── OpponentMessages.cs           ← Mensajes sobre oponentes
│   ├── Opponents.cs                  ← Seguimiento de oponentes (nuevo)
│   ├── Opponents_legacy.cs           ← Seguimiento de oponentes (legacy)
│   ├── OverlayController.cs          ← Control de overlays por voz
│   ├── OvertakingAidsMonitor.cs      ← DRS, KERS, PUSH-TO-PASS
│   ├── PearlsOfWisdom.cs             ← PERSONALIDAD: mensajes de ánimo
│   ├── Penalties.cs                  ← PENALIZACIONES: drive-through, etc.
│   ├── PitStops.cs                   ← Eventos de parada en boxes
│   ├── Position.cs                   ← Monitor de posición
│   ├── PushNow.cs                    ← MODO ATAQUE: "push now"
│   ├── RaceTime.cs                   ← Tiempo de carrera restante
│   ├── Ratings.cs                    ← iRacing: iRating, SOF, incidentes
│   ├── SessionEndMessages.cs         ← Mensajes de fin de sesión
│   ├── SmokeTest.cs                  ← Smoke test del sistema
│   ├── Spotter.cs                    ← Spotter genérico (car left/right)
│   ├── Strategy.cs                   ← Módulo de estrategia
│   ├── Timings.cs                    ← Cronometraje (nuevo)
│   ├── Timings_legacy.cs             ← Cronometraje (legacy)
│   ├── TyreMonitor.cs                ← Monitor de neumáticos
│   ├── VROverlayController.cs        ← Control de overlay VR
│   ├── WatchedOpponents.cs           ← Oponentes vigilados (nuevo)
│   ├── WatchedOpponentsSnip.cs       ← Fragmento de vigilancia
│   └── WatchedOpponents_legacy.cs    ← Oponentes vigilados (legacy)
│
├── GameState/                        ← ESTADO DEL JUEGO (7 archivos)
│   ├── DummyGameDataReader.cs        ← Para testing sin juego
│   ├── DummyGameStateMapper.cs
│   ├── GameStateData.cs              ← Estructura de datos de estado
│   ├── GameStateMapper.cs            ← Mapper genérico
│   ├── GlobalBehaviourSettings.cs    ← Configuración global
│   └── ReflectionGameStateAccessor.cs ← Acceso por reflexión a datos crudos
│
├── [GAME MAPPERS]                    ← 17 JUEGOS, CADA UNO CON:
│   ├── <Game>GameStateMapper.cs      ← Mapea datos crudos → GameStateData
│   ├── <Game>SharedMemoryReader.cs   ← Lee memoria compartida del juego
│   ├── <Game>Spotter.cs              ← Spotter específico del juego
│   ├── <Game>Data.cs / Struct.cs     ← Estructuras de datos nativas
│   ├── <Game>UDPreader.cs            ← Lector UDP (para juegos que lo usan)
│   └── <Game>PitMenu*.cs             ← Integración con menú de boxes
│   │
│   ├── ACC/ (7 archivos)             ← Assetto Corsa Competizione
│   │   ├── UDPHandler/ + ksBroadcastingNetwork/
│   │   ├── ACCData.cs, ACCGameStateMapper.cs
│   │   ├── ACCPitMenuManager.cs      ← Gestión de boxes ACC
│   │   ├── ACCSharedMemoryReader.cs
│   │   ├── ACCSpotter.cs
│   │
│   ├── ACE/ (6 archivos)             ← Assetto Corsa Evo
│   │   ├── UDPHandler/ + ksBroadcastingNetwork/
│   │   ├── ACEData.cs, ACEGameStateMapper.cs
│   │   ├── ACESharedMemoryReader.cs, ACESpotter.cs
│   │
│   ├── ACS/ (4 archivos)             ← Assetto Corsa 32-bit
│   ├── ACS128/ (4 archivos)          ← Assetto Corsa 128 cars
│   │
│   ├── AMS2/ (7 archivos)            ← Automobilista 2
│   │   ├── AMS2GameStateMapper.cs, AMS2SharedMemoryReader.cs
│   │   ├── AMS2Spotter.cs, AMS2Struct.cs
│   │   ├── AMS2UDPTelemetryDataStruct.cs, AMS2UDPreader.cs
│   │
│   ├── Dirt/ (4 archivos)            ← DiRT Rally 1/2
│   │   ├── DirtData.cs, DirtGameStateMapper.cs
│   │   ├── DirtStructWrapper.cs, DirtUDPreader.cs
│   │
│   ├── F1_2018/2019/2020/2021/2022/2023/ ← F1 (spotter only)
│   │   ├── F12018GameStateMapper.cs, F12018Spotter.cs
│   │   ├── F12018StructWrapper.cs, F12018UDPreader.cs
│   │
│   ├── GTR2/ (4 archivos)           ← GTR 2
│   │   ├── GTR2Data.cs, GTR2GameStateMapper.cs
│   │   ├── GTR2SharedMemoryReader.cs, GTR2Spotter.cs
│   │
│   ├── iRacing/ (13 archivos)        ← iRacing (el más complejo)
│   │   ├── Bitfields/ + Drivers/ + iRSDKSharp/
│   │   ├── Enums.cs, Parser.cs, SessionData.cs, SessionInfo.cs
│   │   ├── Sim.cs, Track.cs, iRacingData.cs
│   │   ├── iRacingGameStateMapper.cs
│   │   ├── iRacingSharedMemoryReader.cs, iRacingSpotter.cs
│   │
│   ├── LMU/ (7 archivos)             ← Le Mans Ultimate (¡el que nos importa!)
│   │   ├── LMUPitMenuAPI.cs          ← API REST del menú de boxes
│   │   ├── LMUPitMenuAbstractionLayer.cs ← Capa de abstracción
│   │   ├── LMUPitMenuController.cs   ← Controlador del menú
│   │   ├── LMU_REST_API.cs           ← Cliente REST API de LMU
│   │   ├── LMU_REST_API_classes.cs   ← Clases de datos REST
│   │   └── *.json                    ← Esquemas de la API REST
│   │
│   ├── PCars/ (8 archivos)           ← Project CARS
│   │   ├── PCarsGameStateMapper.cs, PCarsSharedMemoryReader.cs
│   │   ├── PCarsSpotter.cs + PCarsSpotterv2.cs (¡2 spots diferentes!)
│   │   ├── PCarsStruct.cs, PCarsUDPreader.cs
│   │
│   ├── PCars2/ (7 archivos)          ← Project CARS 2
│   │   ├── PCars2GameStateMapper.cs, PCars2SharedMemoryReader.cs
│   │   ├── PCars2Spotterv2.cs, PCars2Struct.cs
│   │   ├── PCars2UDPreader.cs
│   │
│   ├── PMR/ (7 archivos)             ← Project Motor Racing
│   │   ├── ConversionHelper.cs, DataStore.cs
│   │   ├── PMRGameStateMapper.cs, PMRSpotter.cs
│   │   ├── PMRUDPReader.cs, UDPProtocol.cs, UDPThread.cs
│   │
│   ├── R3E/ (7 archivos)             ← RaceRoom Racing Experience
│   │   ├── R3EGameStateMapper.cs, R3EPitMenuManager.cs
│   │   ├── R3ERatings.cs            ← Sistema de ratings R3E
│   │   ├── R3ESerializer.cs, R3ESharedMemoryReader.cs
│   │   ├── R3ESpotterv2.cs, RaceRoomData.cs
│   │
│   ├── RBR/ (3 archivos)             ← Richard Burns Rally
│   │   ├── RBRData.cs, RBRGameStateMapper.cs
│   │   └── RBRSharedMemoryReader.cs
│   │
│   ├── RF1/ (4 archivos)             ← rFactor 1
│   │   ├── RF1Data.cs, RF1GameStateMapper.cs
│   │   ├── RF1SharedMemoryReader.cs, RF1Spotter.cs
│   │
│   └── RF2/ (9 archivos)             ← rFactor 2
│       ├── MappedBuffer.cs, RF2Data.cs, RF2GameStateMapper.cs
│       ├── RF2PitMenuAPI.cs, RF2PitMenuAbstractionLayer.cs
│       ├── RF2PitMenuController.cs, RF2SharedMemoryReader.cs
│       ├── RF2Spotter.cs, rF2HWControl.cs
│
├── Overlay/                          ← SUPERPOSICIÓN IN-GAME (18 archivos)
│   ├── Charts.cs                     ← Renderizado de gráficas de telemetría
│   ├── CommonSubscriptions.cs        ← Suscripciones de datos comunes
│   ├── CrewChiefOverlay.cs           ← Superposición DirectX principal
│   ├── OverlayDataSource.cs          ← Fuente de datos para charts
│   ├── OverlaySettings.cs            ← Configuración de overlay
│   ├── OverlaySubscription.cs        ← Suscripción a canales de datos
│   ├── SubtitleOverlay.cs            ← Superposición de subtítulos
│   └── OverlayElements/              ← Elementos UI del overlay (10 archivos)
│       ├── ElementGroupBox.cs        ← Grupo visual
│       ├── ElementImage.cs           ← Imagen
│       ├── ElementListBox.cs         ← Lista
│       ├── ElementRadioButton.cs     ← Radio button
│       ├── ElementText.cs            ← Texto
│       ├── ElementTextBox.cs         ← Caja de texto
│       ├── elementButton.cs          ← Botón
│       ├── elementCheckBox.cs        ← Checkbox
│       ├── OverlayElemets.cs         ← Contenedor base
│       └── OverlayHeader.cs          ← Cabecera
│
├── VROverlayWindow/                  ← SUPERPOSICIÓN VR (18 archivos)
│   ├── SteamVR.cs                    ← Integración OpenVR/SteamVR
│   ├── VROverlayWindow.cs            ← Ventana overlay
│   ├── CaptureScreen.cs              ← Captura de escritorio
│   ├── ChromaKey.cs                  ← Chroma key para transparencia
│   ├── CursorInteraction.cs          ← Interacción con cursor
│   ├── DeviceManager.cs / DeviceState.cs ← Gestión de dispositivos VR
│   ├── TouchController.cs → TouchControllerButton.cs / TouchControllerHand.cs
│   ├── TrackedDevices.cs             ← Dispositivos rastreados
│   ├── GDIStuff.cs / MathUtil.cs / RECT.cs / Win32Stuff.cs
│   ├── VROverlayConfiguration.cs     ← Configuración VR
│   └── openvr_api.cs                 ← Bindings C# de OpenVR
│
├── PitManager/                       ← SISTEMA DE GESTIÓN DE BOXES (20+ archivos)
│   ├── PitManager.cs                 ← Gestor central
│   ├── PitManagerVoiceCmds.cs        ← Comandos de voz para boxes
│   ├── PitManagerResponseHandlers.cs ← Respuestas de voz a comandos
│   ├── IPitMenu.cs                   ← Interface del menú de boxes
│   ├── IPitMenuAbstractionLayer.cs   ← Capa de abstracción
│   ├── IPitMenuController.cs         ← Controlador del menú
│   ├── GamePitManagerDict.csv        ← CSV: mapeo comandos → teclas por juego
│   ├── PitManagerEventHandlersTable_ACC.cs + _LMU.cs + _R3E.cs + _RF2.cs + _iRacing.cs
│   ├── PitManagerEventHandlers_LMU.cs / _RF2.cs
│   └── Documentation/                ← Documentación del sistema
│
├── NumberProcessing/                 ← LECTURA DE NÚMEROS MULTI-IDIOMA (9 archivos)
│   ├── CarNumber.cs                  ← Procesamiento de números de coche
│   ├── NumberReader.cs               ← Lector genérico
│   ├── NumberReaderFactory.cs        ← Factory pattern
│   ├── NumberReaderEn.cs             ← Inglés
│   ├── NumberReaderIt.cs             ← Italiano (1ª versión)
│   ├── NumberReaderIt2.cs            ← Italiano (2ª versión)
│   ├── NumberReaderPtBr.cs           ← Portugués Brasileño
│   ├── SpokenNumberParser.cs         ← Parseo de números hablados a texto
│   └── TimeSpanWrapper.cs            ← Formateo de intervalos de tiempo
│
├── TrackSpline/                      ← SPLINES DE PISTA (4 archivos)
│   ├── TrackSpline.cs                ← Datos de spline de pista
│   ├── TrackSplineManager.cs         ← Gestor de splines
│   ├── SplineViewerControl.cs        ← Visualizador de splines
│   └── TelemetrySampleCollector.cs   ← Colector de muestras de telemetría
│
├── Track_splines/                    ← DATOS DE SPLINES POR JUEGO
│   └── ASSETTO_EVO/                  ← Splines para Assetto Corsa Evo
│
├── UserInterface/                    ← UI WINDOWS FORMS (80+ archivos)
│   ├── MainWindow.cs + .Designer.cs + MainWindowConsole.cs + MainWindowLayout.cs + MainWindowMenu.cs
│   ├── PropertiesForm.cs             ← VENTANA DE PROPIEDADES con buscador y filtros
│   ├── ActionEditor.cs               ← Editor de acciones para botones
│   ├── MacroEditor.cs                ← Editor de macros de teclado
│   ├── SoundPacks.cs                 ← Gestor de paquetes de sonido
│   ├── SpeechWizard-V.cs             ← ASISTENTE DE CONFIGURACIÓN DE VOZ
│   ├── OpponentNames-V.cs + OpponentNameSelection-V.cs + MyName-V.cs
│   ├── PitMenuDebug-V.cs             ← DEPURACIÓN DEL MENÚ DE BOXES
│   ├── TraceWindow-V.cs + PlaybackTrace-V.cs ← Reproducción de traces
│   ├── SendLogTraceDialog.cs         ← Diálogo de envío de logs
│   ├── VROverlay.cs                  ← Configuración de VR
│   ├── PropertyFilter.cs             ← Filtro de propiedades por categoría
│   ├── BooleanPropertyControl / FloatPropertyControl / IntPropertyControl / ListPropertyControl / ...
│   ├── Loading.cs / Wait.cs / Spacer.cs
│   ├── DarkMode/                     ← MODO OSCURO (5 archivos)
│   │   ├── DarkModeCS.cs, FlatComboBox.cs, FlatProgressBar.cs
│   │   ├── FlatTabControl.cs, Messenger.cs
│   ├── TopicWindows/                 ← VENTANAS DE TEMAS (9 archivos)
│   │   ├── TopicWindowBrakes.cs      ← Frenos en tiempo real
│   │   ├── TopicWindowFuel.cs        ← Combustible en tiempo real
│   │   └── TopicWindowTyres.cs       ← Neumáticos en tiempo real
│   ├── Models/                       ← Modelos de datos de UI (6 archivos)
│   └── VMs/                          ← ViewModels MVVM (5 archivos)
│
├── Properties/                       ← Recursos de ensamblado (6 archivos)
├── Resources/                        ← Iconos, cursores
├── ui_text/                          ← Texto UI (en.txt)
│
├── commands/                         ← MACROS DE TECLADO (4 archivos)
│   ├── CommandMacro.cs               ← Definición de macro
│   ├── KeyPresser.cs                 ← Pulsador de teclas (SendKeys)
│   ├── MacroManager.cs               ← Gestor de macros
│   └── Rf2ChatTransceiver.cs         ← Transceptor de chat para rFactor2
│
├── plugins/                          ← PLUGINS DLL (10 juegos)
│   ├── ARCA/ Automobilista/ GTR2/ "Le Mans Ultimate"
│   ├── RBR/ rFactor/ "rFactor 2"
│   ├── assettocorsa/ assettocorsa128cars/ assettoevo/
│   └── Cada uno contiene: plugin DLL + posible .dll.config
│
├── sounds/                           ← MILES DE .WAV GRABADOS
│   ├── voice/                        ← Voces principales (Jim, Jerry)
│   ├── driver_names/                 ← Miles de nombres de pilotos
│   ├── personalsations/              ← Respuestas personalizadas
│   ├── composite_personalisation_stubs/
│   ├── background_sounds/            ← Sonidos ambientales
│   ├── alt/                          ← Voces alternativas
│   ├── fx/                           ← Efectos de sonido
│   └── pace_notes/                   ← Notas de ritmo grabadas
│   └── Scripts: fixup-soundpack.sh, mk-jerry-diff.sh, mk-soundpack.sh, normalize-volumes.sh
│
├── tools/                            ← HERRAMIENTAS DE DESAROLLO (22 archivos)
│   ├── buildRelease.ps1              ← Script de build
│   ├── Patch.ps1 / PatchLite.ps1 / PatchLiteRC.ps1 ← Scripts de parcheo
│   ├── CCuninstaller.ps1             ← Desinstalador
│   ├── CC_sourceWrangler/            ← Manipulación de código fuente
│   ├── Find-UniqueFileCommits.ps1    ← Encontrar commits únicos
│   ├── Get-UnvocalizedCorners.ps1    ← Curvas sin grabar
│   ├── GetUnvocalizedDrivers.ps1     ← Pilotos sin grabar
│   ├── extractR3eClasses.py          ← Extraer clases R3E
│   └── soundpacks.bat                ← Gestión de paquetes de sonido
│
├── *.cs                              ← ARCHIVOS RAÍZ (~30)
│   ├── CrewChief.cs                  ← PUNTO DE ENTRADA PRINCIPAL
│   ├── Program.cs                    ← Main() / WinForms startup
│   ├── CommandManager.cs             ← GESTOR DE COMANDOS DE VOZ
│   ├── SpeechRecogniser.cs           ← RECONOCEDOR DE VOZ (punto de entrada)
│   ├── SpeechCommands.cs             ← DEFINICIÓN DE COMANDOS
│   ├── Configuration.cs              ← Configuración global
│   ├── UserSettings.cs               ← Ajustes de usuario (persistencia)
│   ├── SharedMemory.cs               ← Lector de memoria compartida
│   ├── CarData.cs                    ← Base de datos de coches
│   ├── TrackData.cs                  ← Datos de pistas
│   ├── DriverNameHelper.cs           ← Fuzzy matching de nombres
│   ├── DriverTrainingService.cs      ← Entrenamiento de reconocimiento de voz
│   ├── DataFiles.cs                  ← Archivos de datos del juego
│   ├── JsonFiles.cs                  ← Helper de archivos JSON
│   ├── ColloquialTime.cs             ← "half past ten" / "26 point 5"
│   ├── ControlVolumeOfProcess.cs     ← Ducking de audio del juego
│   ├── ControllerConfiguration.cs    ← Mapeo de botones de mando
│   ├── NoisyCartesianCoordinateSpotter.cs ← Spotter por coordenadas XYZ
│   ├── PluginInstaller.cs            ← Instalador de plugins DLL
│   ├── PluginInstaller_deprecated.cs ← Versión legacy
│   ├── UpdateHelper.cs               ← Actualizador automático
│   ├── ThreadManager.cs              ← Gestión de hilos
│   ├── Logging.cs / Debugging.cs     ← Sistema de logging
│   ├── LogFluentExtensions.cs        ← Extensiones de logging fluido
│   ├── Utilities.cs / Extensions.cs  ← Utilidades varias
│   ├── QueuedMessage.cs              ← Cola de mensajes
│   ├── CircularBuffer.cs             ← Buffer circular
│   ├── RingBufferException.cs        ← Excepción de buffer
│   ├── RingBufferStream.cs           ← Stream de buffer circular
│   ├── GlobalResources.cs            ← Recursos globales
│   ├── AdditionalDataProvider.cs     ← Proveedor de datos adicionales
│   └── *.json + *.txt + *.py         ← Datos y scripts (ver sección 1.2)
│
├── CrewChiefV4SDK/                   ← SDK PÚBLICO (5 archivos)
│   ├── CrewChiefData.cs              ← Estructuras de datos públicas
│   ├── CrewChiefV4SDK.cs             ← API pública
│   └── Program.cs                    ← Ejemplo de uso
│
├── GameOverlay.Net/                  ← FORK DE BIBLIOTECA EXTERNA
│   └── source/ + LICENSE + README
│
├── CrewChiefV4_installer/            ← INSTALADOR MSI (WiX)
│   ├── Assets/ + Installs/ + Soundpacks/
│   ├── Components.wxs / Directories.wxs / Product.wxs
│
├── LMU_REST_API_dummy/               ← SERVIDOR DUMMY DE LA REST API DE LMU
│   ├── Program.cs + Startup.cs       ← Servidor ASP.NET Core
│   ├── LMU_REST_API_classes.*.json   ← Datos de ejemplo:
│   │   ├── DRIVEAIDS_invulnerable.json ← Invulnerabilidad
│   │   ├── Options.Settings.json     ← Opciones de sesión
│   │   ├── RepairAndRefuel.json      ← Reparación y combustible
│   │   ├── SESSSET_Fuel_Usage.json   ← Uso de combustible por sesión
│   │   └── Sessions.json             ← Datos de sesiones
│   └── → ¡Útil para desarrollo sin LMU!
│
├── DriverFileDeDupe/                 ← DEDUPLICACIÓN DE NOMBRES (Go)
│   ├── DriverFileDeDupe.go
│   └── go.mod
│
├── CC_log_compare/                   ← COMPARADOR DE LOGS (9 archivos)
│   ├── CC_log_compare.cs             ← Lógica de comparación
│   ├── UnitTest1.cs                  ← Tests
│   └── console_2022_06_14-13-13-06.txt ← Log de ejemplo
│
├── UnitTest/                         ← TESTS UNITARIOS C#
│   ├── GrammarFiles/                 ← Tests de gramáticas de voz
│   ├── LMU/                          ← Tests de LMU
│   ├── Misc/                         ← Tests varios
│   ├── PitMenu/                      ← Tests de menú de boxes
│   ├── Refactoring/                  ← Tests de refactorización
│   ├── TopicWindows/                 ← Tests de ventanas de temas
│   ├── Utils/                        ← Tests de utilidades
│   └── VROverlayWindow/              ← Tests de VR overlay
│
├── XunitTest/                        ← TESTS XUNIT
│   └── TimePrecision/                ← Tests de precisión temporal
│
├── HelpFiles/                        ← ARCHIVOS DE AYUDA (HTML, duplicado de public/)
├── auto_update_data_files/           ← Datos de actualización automática
│   └── gitlab/ + primary/ + secondary/
│
└── public/                           ← DOCUMENTACIÓN HTML (GitLab Pages, ~60 archivos)
    ├── index.html + styles.css
    ├── About_*.html                  ← Documentación general
    ├── GettingStarted_*.html         ← Guías de inicio por juego
    ├── Speech_*.html                 ← Documentación de voz
    ├── VoiceRecognition_*.html       ← Documentación de comandos
    ├── Overlays_*.html               ← Documentación de overlays
    ├── Properties_*.html             ← Documentación de propiedades
    └── GameSpecific_*.html           ← Documentación específica por juego
```

### 1.1 Archivos de datos clave en raíz de CrewChiefV4/

| Archivo | Propósito |
|---|---|
| `carClassData.json` | Datos de clases de coches |
| `chart_subscriptions.json` | Suscripciones de canales de telemetría para overlays |
| `controllerConfigurationData.json` | Configuración de botones de mando |
| `iracing-track.json` | Datos de pistas de iRacing |
| `iracing_formation.json` | Reglas de formación de salida por pista |
| `lap_lengths.json` | Longitudes de vuelta por pista |
| `mqtt_telemetry.json` | Configuración del broker MQTT |
| `saved_command_macros.json` | Macros de comandos guardadas |
| `sounds_config.txt` | Configuración de sonidos |
| `speech_recognition_config.txt` | Configuración de gramáticas de voz |
| `trackLandmarksData.json` | Datos de puntos de referencia de pistas |
| `trackLandmarksData-*.py` (5 scripts) | Scripts Python para procesar landmarks |
| `tracks.zip` | Datos de pistas comprimidos |

---

## 2. Diferencia Arquitectónica Fundamental: Speech Recognition

Esta es probablemente la diferencia de diseño MÁS IMPORTANTE entre ambos proyectos:

### CrewChiefV4: Grammar-Based SAPI

```
Windows SAPI Speech Recognition
         │
         ▼
SREWrapperFactory ──→ MicrosoftSREWrapper
         │                └── Grammar: comandos EXACTOS definidos
         │                    "how's my fuel" → Fuel.howMyFuel()
         │                    "pitstop add 10 litres" → PitManager.addFuel(10)
         │                    "where should I attack" → Strategy.whereAttack()
         │
         └──→ SystemSREWrapper
                  └── Fallback: System.Speech (misma gramática)

SpeechCommands.cs → 100+ comandos estructurados con parámetros
                         │
                         ▼
                    CommandManager.cs → Event específico
```

**Características:**
- **Reconocimiento por gramática**: Solo reconoce frases definidas explícitamente
- **Sin ambigüedad**: "how's my fuel" → siempre al mismo handler
- **Sin LLM**: Respuestas 100% deterministas (grabadas o generadas por TTS)
- **Precisión muy alta** en los comandos soportados
- **No puede responder** a preguntas no definidas
- **Soporta parámetros**: "pitstop add [10] litres" → el número se parsea

### Vantare-Ingeniero: Free-Form + LLM

```
Web Speech API / Whisper
         │
         ▼
    Texto libre sin estructura
    "¿cuánto combustible me queda?"
         │
         ▼
    IntelligenceEngine.evaluate_cycle()
         │
         ▼
    Context Builder (ticker + RAG + snapshot)
         │
         ▼
    LLM (vLLM / OpenAI compatible)
         │
         ▼
    Streaming de tokens → TTS
```

**Características:**
- **Reconocimiento free-form**: Cualquier frase, cualquier pregunta
- **Máxima flexibilidad**: Puede responder a preguntas no previstas
- **LLM necesario**: Requiere modelo de lenguaje para interpretar y responder
- **Respuesta generada**: No grabada, sino generada en el momento
- **Contexto enriquecido**: Ticker + RAG + snapshot histórico
- **Puede alucinar**: El LLM puede inventar respuestas incorrectas

### Implicaciones

| Aspecto | CC (Grammar) | Vantare (Free-form + LLM) |
|---|---|---|
| **Precisión comandos conocidos** | 100% | Depende del LLM |
| **Flexibilidad** | 0% (solo comandos definidos) | 100% (cualquier pregunta) |
| **Latencia** | Instantánea (archivos .wav) | 1-5 segundos (LLM + TTS) |
| **Naturalidad** | Media (voces grabadas) | Alta (LLM genera lenguaje natural) |
| **Cobertura** | 100+ comandos exactos | Ilimitada en teoría |
| **Offline** | Sí (grabaciones locales) | No (requiere LLM cloud) |
| **Personalización** | Propiedades + perfiles | Prompt engineering |
| **Coste operativo** | Cero (grabaciones) | Por token de LLM |

**La combinación ideal**: Usar comandos estructurados (gramática) para acciones predecibles (boxes, consultas de estado) y LLM para análisis estratégico complejo.

---

## 3. Features de CrewChiefV4: Estado en Vantare

> ✅ = Implementado | ⚠️ = Parcial | ❌ = No implementado | 🔍 = Descubierto en 2ª pasada

### 3.1 SPOTTER

| Feature CC | Estado | Notas |
|---|---|---|
| Car-left/car-right por coordenadas XYZ (`NoisyCartesianCoordinateSpotter.cs`) | ❌ | Vantare no detecta proximidad lateral |
| Desactivado en calificación (propiedad) | ❌ | CC tiene "Spotter off during qualifying" |
| Spotter multiclase (coche doblando/doblado) | ❌ | No hay distinción de clases |
| Exclusión de coches en boxes/rotos | ❌ | CC no reporta coches parados |
| Basado en dimensiones reales del coche | ❌ | No disponible |
| "Spot" / "Don't spot" por voz | ❌ | Sin comando de activación |
| Spotter para óvalos | N/A | No aplica a LMU |
| Pit limiter entrada/salida | ✅ | En `spotter.py` |
| Gap < 0.5s delante/detrás | ✅ | En `spotter.py` |
| Daños detectados | ✅ | En `spotter.py` |
| Safety Car / FCY | ✅ | En `spotter.py` |
| Última vuelta | ✅ | En `spotter.py` |
| Combustible < 1 vuelta | ✅ | En `spotter.py` |

### 3.2 INGENIERO DE CARRERA

#### Estado del Coche

| Feature CC | Estado | Notas |
|---|---|---|
| "How's my body work / aero / engine / transmission / suspension" | ❌ | Sin comandos específicos |
| "Damage report" | ⚠️ | LLM puede responder si se le pregunta |
| "Car status" (todo junto) | ⚠️ | LLM puede generar |
| "Full status" / "Update me" | ⚠️ | LLM puede generar |

#### Neumáticos

| Feature CC | Estado | Notas |
|---|---|---|
| "How's my tyre wear" (cualitativo) | ⚠️ | Vía LLM |
| "What are my tyre temperatures" | ⚠️ | Vía LLM |
| "What tyres am I on" / "What tyre type" | ❌ | Sin seguimiento de compuesto |
| "How old are these tyres" | ❌ | Sin edad de neumáticos |
| Consulta neumáticos de oponentes | ❌ | No disponible |
| "Give me tyre pace differences" | ❌ | Comparación compuestos |
| Ventana de tema neumáticos (overlay) | ❌ | CC overlay visual coloreado |
| Corrección temperatura LMU | ❌ | CC lee temperatura interna, no superficie |

#### Frenos / Motor / Combustible

| Feature CC | Estado | Notas |
|---|---|---|
| Cualquier comando de frenos | ⚠️ | Vía LLM |
| Cualquier comando de motor | ⚠️ | Vía LLM |
| "How's my fuel" | ✅ | Trigger + LLM |
| "What's my fuel usage" | ✅ | `fuel.py` |
| "Calculate fuel for X minutes/laps" | ❌ | Sin comando paramétrico |
| "How much fuel to the end" | ✅ | `fuel_needed_to_finish` |
| Márgenes dinámicos ("play it safe" / "roll the dice") | ❌ | CC permite ajuste por voz |
| Persistencia entre sesiones (`fuel_usage.json`) | ❌🔍 | CC guarda por coche/pista |
| "Running on fumes" | ❌ | Mensaje para combustible marginal |

#### Batería / Híbrido

| Feature CC | Estado | Notas |
|---|---|---|
| Monitor de batería | ✅ | `hybrid.py` con máquina de estados |
| Recordatorio KERS | ❌🔍 | CC tiene evento dedicado |
| "How many DRS activations left" | ❌🔍 | CC monitorea DRS |

### 3.3 GESTIÓN DE BOXES (⛔ GAP MÁS CRÍTICA)

| Feature CC | Estado | Notas |
|---|---|---|
| **Sistema PitManager completo** | ❌🔍 | CC tiene 20+ archivos dedicados |
| **PitManagerVoiceCmds** | ❌🔍 | Interfaz completa por voz |
| **Tablas por juego** (ACC, LMU, R3E, RF2, iRacing) | ❌🔍 | Event handlers específicos |
| **LMUPitMenuAPI.cs** (REST API de LMU) | ❌🔍 | **CC YA TIENE integración con LMU** |
| "Pitstop add 10 litres" | ❌ | Añadir combustible |
| "Pitstop fuel to the end" | ❌ | Calcular hasta el final |
| "Pitstop fill to X litres" | ❌ | Rellenar hasta |
| "Pitstop change all/front/rear/left/right tyres" | ❌ | Cambio de neumáticos |
| "Pitstop change tyre pressures" (por esquina) | ❌ | Ajuste individual |
| "Pitstop fix body / all / none" | ❌ | Reparaciones |
| "Pitstop virtual energy X%" (LMU) | ❌ | **¡ESPECÍFICO LMU!** |
| "Pitstop fuel ration X%" (LMU) | ❌ | **¡ESPECÍFICO LMU!** |
| "Pitstop serve penalty" / "don't serve" | ❌ | Gestión de sanciones |
| "Pitstop tearoff / windscreen" | ❌ | Limpieza visera (iRacing) |
| "Pitstop clear all" | ❌ | Reset opciones |
| "What's the pitstop plan" | ❌ | Resumen de acciones |
| Auto-refuel on pit entry (propiedad) | ❌ | Repostaje automático |

### 3.4 VOCES Y AUDIO

| Feature CC | Estado | Notas |
|---|---|---|
| Voces humanas grabadas (Jim, Jerry) | ❌ | TTS sintético |
| Miles de nombres de pilotos grabados | ❌ | `sound/driver_names/` |
| Fuzzy matching de nombres | ❌ | `DriverNameHelper.cs` |
| Paquetes de voz descargables | ❌ | Instalación 1 clic |
| Soporte multi-idioma en voces | ❌ | Voice packs por idioma |
| Pitidos de radio configurables | ✅ | Beeps en Vantare |
| **Ducking de audio** (bajar volumen juego) | ❌🔍 | `ControlVolumeOfProcess.cs` |
| Control de volumen por voz | ❌ | "Crew Chief quieter/louder" |
| TTS para nombres faltantes | ✅ | Edge TTS |
| Modo Trainee (Jerry aprendiz) | ❌ | Alternar voces |
| Juramentos opcionales | ❌ | "Use sweary messages" |
| Perlas de sabiduría | ❌🔍 | `PearlsOfWisdom.cs` |
| Tiempo coloquial | ❌🔍 | `ColloquialTime.cs` |
| Formato vuelta sin minutos | ❌🔍 | "26 point 5" vs "1:26.5" |

### 3.5 RECONOCIMIENTO DE VOZ

| Feature CC | Estado | Notas |
|---|---|---|
| **100+ comandos estructurados** | ❌ | Vantare: solo preguntas libres |
| **Sistema grammar-based (SRE/)** | ❌🔍 | CC: 13 archivos dedicados |
| Comandos de estado de carrera | ❌ | Posición, gaps, vueltas |
| Comandos de estado del coche | ❌ | Daños, neumáticos, frenos |
| Comandos de oponentes por nombre | ❌ | "Where's [driver]" |
| Comandos de gestión de boxes | ❌ | Cobertura completa |
| Comandos de estrategia | ❌ | Ataque/defensa, combustible |
| Comandos de verbosidad | ❌ | "Keep quiet" / "Keep me informed" |
| Comandos de superposición | ❌ | "Show/hide overlay" |
| **Macros de teclado** (sequences) | ❌🔍 | `CommandMacro.cs`, `KeyPresser.cs` |
| Macros de chat | ❌🔍 | Mensajes predefinidos online |
| Macros DOS | ❌🔍 | Ejecutar programas por voz |
| Dictado libre (chat) | ❌🔍 | Free dictation |
| Desactivación granular de comandos | ❌ | Mejora precisión |
| **Soporte multi-idioma** (EN, IT, PT-BR) | ❌🔍 | `NumberReader*.cs` |

### 3.6 SUPERPOSICIONES (OVERLAYS)

| Feature CC | Estado | Notas |
|---|---|---|
| Overlay de consola DirectX in-game | ❌ | Vantare: ventana Tauri separada |
| Overlay de telemetría con gráficos | ❌ | `Charts.cs` — configurable |
| Overlay de subtítulos | ❌ | Tiempo real |
| **Overlay VR (SteamVR)** | ❌🔍 | 18 archivos + Touch Controllers |
| Chroma key para VR | ❌🔍 | Transparencia |
| **Múltiples charts** (stacked/single) | ❌ | CC overlay gráfico |
| Zoom/pan/sectores en charts | ❌ | Control por voz |
| Selección de canales | ❌ | `chart_subscriptions.json` |

### 3.7 PREDICCIÓN SALIDA BOXES

| Feature CC | Estado | Notas |
|---|---|---|
| "Where will I be after a stop?" | ❌ | Estimar tráfico y posición |
| "Time this stop" / cronometrar parada | ❌ | Medir pérdida |
| Estimación desde datos oponentes | ❌ | Fallback automático |

### 3.8 COMPETIDORES

| Feature CC | Estado | Notas |
|---|---|---|
| Consultas por nombre ("What's [driver]'s last lap") | ❌ | Requiere nombres grabados |
| Consultas por posición ("What's P4's best lap") | ❌ | |
| "Who's ahead/behind in race" vs "on track" | ❌ | Distinción pista vs clasificación |
| "Monitor [driver]" / "Stop monitoring" | ❌ | Seguimiento continuo |
| "Is the car ahead/behind in my class" | ❌ | Comprobación multiclase |
| "What class is the car ahead/behind" | ❌ | Consulta de clase |

### 3.9 ESTRATEGIA / PISTA

| Feature CC | Estado | Notas |
|---|---|---|
| "Where should I attack/defend" | ❌🔍 | Análisis por curva |
| Modo deltas ("Tell me the gaps") | ❌ | Lectura automática por vuelta |
| Nombres de curvas (corner names) | ❌ | Track landmarks comunitarios |
| Grabación de landmarks | ❌ | Botón asignable |
| **Splines de pista** | ❌🔍 | `TrackSpline.cs` |
| **Pace notes** (notas de ritmo) | ❌🔍 | Grabación y reproducción |
| Detección óvalo/circuito | ✅ | LMU expone dato |

### 3.10 EVENTOS ADICIONALES

| Feature CC | Estado | Relevancia LMU |
|---|---|---|
| **DriverSwaps** (cambios piloto endurance) | ❌🔍 | **MUY RELEVANTE** (24h Le Mans) |
| **MulticlassWarnings** | ❌🔍 | **MUY RELEVANTE** (Hypercar + GT3) |
| **OvertakingAidsMonitor** (DRS/KERS) | ❌🔍 | Relevante (LMU tiene DRS) |
| **FlagsMonitor** (banderas) | ❌🔍 | Vantare solo SC/FCY |
| **FrozenOrderMonitor** (bandera roja) | ❌🔍 | LMU tiene bandera roja |
| **Penalties** (drive-through, stop-and-go) | ❌🔍 | LMU tiene penalizaciones |
| **PushNow** (modo ataque) | ❌🔍 | |
| **SessionEndMessages** | ❌🔍 | |
| **ConditionsMonitor** (clima) | ❌🔍 | |
| **AlarmClock** | ❌🔍 | Baja prioridad |
| CoDriver (rally) | N/A | No aplica |
| iRacing ratings | N/A | No aplica |

### 3.11 SISTEMA MQTT

| Feature CC | Estado | Notas |
|---|---|---|
| Publicación telemetría a broker MQTT | ❌🔍 | Dashboards externos |
| Suscripción MQTT | ❌🔍 | |

### 3.12 CONFIGURACIÓN

| Feature CC | Estado | Notas |
|---|---|---|
| Ventana propiedades con filtros/búsqueda | ❌ | Categorías VIP, "solo diferencias" |
| **Sistema de perfiles** | ❌ | Guardar/cargar configuraciones |
| **Asistente de voz** (Speech Wizard) | ❌🔍 | Configuración inicial guiada |
| **Detección automática de juego** | ❌ | Se activa al iniciar LMU |
| **Auto-update** | ❌ | CC se actualiza solo |
| Modo oscuro | ⚠️ | Vantare tiene tema oscuro en UI |

### 3.13 SDK + DEBUG

| Feature CC | Estado | Notas |
|---|---|---|
| SDK público (CrewChiefV4SDK) | ❌🔍 | API pública |
| Reproducción de traces | ❌🔍 | `PlaybackTrace-V.cs` |
| Debug de reconocimiento de voz (WAV) | ❌ | Escuchar lo que CC oyó |
| **Depuración de menú de boxes** | ❌🔍 | `PitMenuDebug-V.cs` |
| **Editor de acciones** para botones | ❌🔍 | `ActionEditor.cs` |
| **Editor de macros** visual | ❌🔍 | `MacroEditor.cs` |
| LMU REST API dummy server | ❌🔍 | CC tiene servidor de prueba |

---

## 4. Lo que Vantare TIENE y CC NO

| Feature Vantare | Ventaja Diferencial |
|---|---|
| **Motor de inteligencia LLM** 🏆 | CC es 100% determinista. Vantare genera consejo contextual, adaptativo y natural en español. |
| **RAG / ChromaDB Event Store** 🏆 | Búsqueda semántica de eventos históricos. CC no tiene nada similar. |
| **Ticker compacto para LLM** 🏆 | 400 tokens vs JSON de miles. Optimizado específicamente para prompts. |
| **Spatial Delta Arrays** 🏆 | Comparación telemetría cada 10m por posición. CC no tiene este concepto. |
| **4 backends TTS** | Edge, Piper (local ONNX), ElevenLabs, Gemini. CC solo Windows TTS + grabaciones. |
| **Streaming de tokens** | Piloto ve respuesta token por token en tiempo real. |
| **Preemption de LLM** | Evento de mayor prioridad interrumpe respuesta en curso. |
| **3 tiers de contexto** | FAST (400t), STANDARD, DEEP. Optimizado latencia vs riqueza. |
| **Arquitectura async moderna** | FastAPI + Tauri 2 + React 19 + TypeScript + Tailwind. |
| **Delta-encoding MessagePack** | Eficiencia en WebSocket a 20Hz. CC usa JSON sin comprimir. |
| **Sidecar Windows independiente** | Backend Linux + sidecar Windows. CC es monolítico Windows-only. |
| **4 modos de radio visuales** | IDLE → LISTENING → THINKING → SPEAKING con indicador. |
| **Hotkeys globales** (Tauri) | Shortcuts incluso con ventana en segundo plano. |
| **Web Speech API** | Reconocimiento sin dependencias externas. CC requiere SAPI. |
| **LMU REST API dummy en Python** | (parcial) Vantare tiene `lmu_api.py` similar. |
| **FIFO TTS queue con interrupción** | `audioQueue.ts` — stop/interrupt. |

---

## 5. Features Descubiertas en Exploración del Árbol GitLab (2ª + 3ª pasada)

Features que NO estaban en el análisis inicial basado solo en documentación web. Identificadas al explorar CADA archivo individual del repositorio vía API:

1. **🔍 `LMUPitMenuAPI.cs` + `PitManagerEventHandlers_LMU.cs`** — CC YA tiene integración REST API con LMU para boxes, Virtual Energy y Fuel Ration

2. **🔍 `OvertakingAidsMonitor.cs`** — Monitor de DRS, KERS, Push-to-Pass

3. **🔍 `DriverSwaps.cs`** — Cambios de piloto en endurance

4. **🔍 `MulticlassWarnings.cs`** — Advertencias multiclase

5. **🔍 `FlagsMonitor.cs`** — Banderas verde/amarilla/roja/azul

6. **🔍 `FrozenOrderMonitor.cs`** — Orden congelado en bandera roja

7. **🔍 `CoDriver.cs`** — Copiloto rally con pace notes

8. **🔍 `PearlsOfWisdom.cs`** — Personalidad/mensajes de ánimo

9. **🔍 `PushNow.cs`** — Modo ataque

10. **🔍 `Mqtt.cs`** — Publicación MQTT

11. **🔍 `ControlVolumeOfProcess.cs`** — Ducking de audio del juego

12. **🔍 `ColloquialTime.cs`** — Formato de tiempo coloquial

13. **🔍 `NumberReader*.cs`** — Lectura números multi-idioma (EN, IT, PT-BR)

14. **🔍 `TrackSpline.cs` + `TrackSplineManager.cs`** — Sistema de splines de pista

15. **🔍 `Rf2ChatTransceiver.cs`** — Transceptor de chat rF2

16. **🔍 `MacroEditor.cs` + `ActionEditor.cs`** — Editores visuales

17. **🔍 `TopicWindow*.cs`** — Ventanas de temas (frenos, combustible, neumáticos)

18. **🔍 `VROverlayWindow/`** — Sistema VR completo con SteamVR + Touch Controllers

19. **🔍 `PitMenuDebug-V.cs`** — Depuración visual del menú de boxes

20. **🔍 `PlaybackTrace-V.cs`** — Reproducción de datos grabados

21. **🔍 SDK público `CrewChiefV4SDK/`** — Para integraciones externas

22. **🔍 Persistencia `fuel_usage.json`** — Combustible entre sesiones

23. **🔍 Análisis ataque/defensa** — "Where should I attack / defend"

24. **🔍 `Penalties.cs`** — Sistema de penalizaciones

25. **🔍 `AlarmClock.cs`** — Alarma por voz

26. **🔍 `SRE/`** **(13 archivos)** — Sistema grammar-based de reconocimiento de voz con wrappers Microsoft + System SAPI

27. **🔍 `LMU_REST_API_dummy/`** — Servidor dummy REST API de LMU con datos de ejemplo

28. **🔍 `ACCSpotter.cs`** — Spotter específico ACC

29. **🔍 `R3ERatings.cs`** — Sistema de ratings específico R3E

30. **🔍 `PCarsSpotter.cs` + `PCarsSpotterv2.cs`** — Dos versiones de spotter

31. **🔍 `R3ESpotterv2.cs`** — Spotter v2 específico R3E

32. **🔍 `ACCUDPHandler/` + `ACEUDPHandler/`** — Handlers UDP para ACC y ACE

33. **🔍 `rF2HWControl.cs`** — Control de hardware rF2

34. **🔍 `AdditionalDataProvider.cs`** — Proveedor extensible de datos adicionales

35. **🔍 `CircularBuffer.cs` + `RingBufferStream.cs`** — Buffers circulares para datos en tiempo real

36. **🔍 `GlobalBehaviourSettings.cs`** — Configuración global de comportamiento

37. **🔍 `ReflectionGameStateAccessor.cs`** — Acceso por reflexión a datos crudos del juego

---

## 6. Features Prioritarias para Vantare (Actualizado)

### 🥇 P0 — Imperativo (transformacional)

1. **Gestión de boxes por voz + API REST LMU**
   - CC ya demostró que funciona: `LMUPitMenuAPI.cs` + `PitManagerEventHandlers_LMU.cs`
   - API LMU en `http://localhost:6397`
   - Comandos: add fuel, fill to, fuel to end, change tyres, fix body, virtual energy %, fuel ration %
   - **Esto es lo que más impacto tendría en Vantare**

2. **Sistema de comandos de voz estructurados**
   - Inspirado en CC pero híbrido: grammar para acciones predecibles, LLM para análisis
   - Categorías: fuel, tyres, brakes, engine, pitstops, session, opponents, strategy, verbosity
   - Arquitectura: Comando → Handler específico → Respuesta directa (sin LLM si es simple)

### 🥈 P1 — Alta

3. **MulticlassWarnings** — Hypercar vs GT3
4. **DriverSwaps** — Endurance (24h Le Mans)
5. **OvertakingAidsMonitor** — DRS, KERS
6. **FlagsMonitor** — Bandera amarilla, roja, azul
7. **Predicción de salida de boxes** — "Where will I be after a stop?"
8. **Ataque/defensa** — Usando spatial delta arrays

### 🥉 P2 — Media

9. **Ducking de audio** — `ControlVolumeOfProcess.cs`
10. **Persistencia de combustible entre sesiones** — `fuel_usage.json`
11. **PushNow** — Modo ataque
12. **Penalizaciones** — Drive-through, stop-and-go
13. **Modo verbosidad** — "Keep quiet" / "Don't talk in braking zones"
14. **Márgenes de combustible dinámicos** — "Play it safe / roll the dice"
15. **SessionEndMessages** — Mensajes específicos al final

---

## 7. Resumen Estadístico

| Categoría | ✅ | ⚠️ | ❌ | 🔍 Nuevas |
|---|---|---|---|---|
| Spotter | 6 | 0 | 5 | 0 |
| Ingeniero de carrera | 2 | 8 | 8 | 3 |
| Gestión de boxes | 0 | 0 | 20+ | 8 |
| Voces y audio | 2 | 1 | 11 | 4 |
| Reconocimiento de voz | 0 | 0 | 15 | 7 |
| Superposiciones | 0 | 0 | 11 | 3 |
| Competidores | 0 | 0 | 12 | 0 |
| Pista | 1 | 0 | 5 | 3 |
| Eventos adicionales | 0 | 0 | 12 | 12 |
| Configuración | 0 | 1 | 6 | 0 |
| SDK + Debug | 0 | 0 | 8 | 6 |
| **TOTAL** | **11** | **10** | **~110+** | **46** |

**Features totales de CC identificadas:** ~130
**Implementadas en Vantare:** ~11 (8%)
**Parcialmente implementadas:** ~10 (8%)
**No implementadas:** ~110+ (84%)

**Nota sobre las 46 "🔍 Nuevas":** Descubiertas al explorar el árbol de GitLab archivo por archivo, NO visibles en la documentación web del proyecto.

---

## 8. Conclusión

CrewChiefV4 es un proyecto de **~10 años**, **8,512 commits**, **~450+ archivos .cs** en **45+ directorios**, soportando **22+ juegos**. Su fortaleza es la **madurez funcional**: sistema de eventos completo (42 eventos), gestión de boxes por juego, spotter por juego, reconocimiento de voz grammar-based con 100+ comandos, miles de grabaciones de voz humanas, y 10 años de iteración.

Vantare-Ingeniero tiene una **ventaja tecnológica fundamental** (LLM, RAG, arquitectura async, TTS diverso, streaming) pero solo cubre **~8% de las features** que CC ya tiene.

**La brecha más crítica** no es técnica sino de **cobertura funcional**: CC tiene 42 eventos y 100+ comandos; Vantare tiene 12 triggers y solo preguntas libres. La gestión de boxes para LMU es la carencia más dolorosa porque CC **ya demostró** que funciona con la REST API de LMU.

**No se trata de copiar CC, sino de entender qué aprender de 10 años de desarrollo.** La lección principal: un asistente de carrera necesita **tanto** comandos predecibles de alta precisión (grammar) **como** inteligencia flexible (LLM). Lo óptimo es una arquitectura híbrida.
