; DEPRECATED: use frontend/electron-builder NSIS (npm run build:desktop)
; Vantare Ingeniero IA - NSIS Installer Script
; Genera vantare-engine-setup.exe

!include "MUI2.nsh"

; ====================
; CONFIGURACIÓN GENERAL
; ====================
!define PRODUCT_NAME "Vantare Ingeniero IA"
!define PRODUCT_VERSION "0.1.0-alpha"
!define PRODUCT_PUBLISHER "Vantare"
!define PRODUCT_WEB_SITE "https://github.com/isaac-albala/Vantare-Ingeniero"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\vantare-engine.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; ====================
; INSTALADOR CONFIG
; ====================
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "vantare-instalador-${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES\Vantare Ingeniero IA"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show

; ====================
; INTERFAZ MODERNA
; ====================
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; ====================
; PÁGINAS DEL INSTALADOR
; ====================
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ====================
; IDIOMAS (Español + English)
; ====================
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "English"

; ====================
; SECCIÓN PRINCIPAL
; ====================
Section "Principal" SEC01
  SetOutPath "$INSTDIR"

  ; Copiar archivos del build
  File /r "backend/dist/vantare-engine/*.*"

  ; Copiar archivos de configuración de ejemplo
  SetOutPath "$INSTDIR\config"
  File "backend/.env.example"

  ; Crear archivo de versión
  FileOpen $0 "$INSTDIR\VERSION.txt" w
  FileWrite $0 "${PRODUCT_NAME} v${PRODUCT_VERSION}$\r$\n"
  FileWrite $0 "Fecha de instalacion: "
  FileWrite $0 __DATE__
  FileClose $0

  ; ====================
  ; ACCESOS DIRECTOS
  ; ====================
  CreateDirectory "$SMPROGRAMS\Vantare Ingeniero IA"
  CreateShortCut "$SMPROGRAMS\Vantare Ingeniero IA\Vantare Engine.lnk" "$INSTDIR\vantare-engine\vantare-engine.exe"
  CreateShortCut "$SMPROGRAMS\Vantare Ingeniero IA\Desinstalar.lnk" "$INSTDIR\uninstall.exe"
  CreateShortCut "$DESKTOP\Vantare Engine.lnk" "$INSTDIR\vantare-engine\vantare-engine.exe"

  ; ====================
  ; REGISTRO DE WINDOWS
  ; ====================
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\vantare-engine\vantare-engine.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\vantare-engine\vantare-engine.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"

  ; Ejecutar post-instalación (crear config si no existe)
  ExecWait '"$INSTDIR\vantare-engine\vantare-engine.exe" --init-config'

  ; Escribir desinstalador
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; ====================
; SECCIÓN DE DESINSTALACIÓN
; ====================
Section "Uninstall"
  ; Eliminar archivos
  RMDir /r "$INSTDIR"

  ; Eliminar accesos directos
  Delete "$DESKTOP\Vantare Engine.lnk"
  RMDir /r "$SMPROGRAMS\Vantare Ingeniero IA"

  ; Eliminar registro
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
SectionEnd

; ====================
; FUNCIONES DE INSTALACIÓN
; ====================
Function .onInit
  ; Verificar que no esté ya instalado
  ReadRegStr $0 HKLM "${PRODUCT_UNINST_KEY}" "DisplayName"
  StrCmp $0 "" done
  
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
    "Ya existe una versión instalada. $\n$\n¿Deseas desinstalar la versión anterior primero?" \
    IDOK uninst
  Abort
uninst:
  ExecWait '"$INSTDIR\uninstall.exe" /S'
done:
FunctionEnd