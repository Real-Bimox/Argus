; Argus intentionally maps a normal window close to "hide in tray". NSIS must
; therefore terminate the old release explicitly before its built-in running-
; app check; sending WM_CLOSE alone can never prove that the process exited.
!macro forceStopArgus
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM "Argus.exe"'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM "argus-backend.exe"'
  Sleep 750
!macroend

; Runs before install-mode setup and therefore also protects the legacy
; uninstaller that the new installer invokes during an in-place upgrade.
!macro customInit
  !insertmacro forceStopArgus
!macroend

; Replace electron-builder's dialog-based check in every generated installer
; and uninstaller pass. Its normal graceful WM_CLOSE path maps to "hide in
; tray" in Argus, so waiting/retrying can never establish process exit.
!macro customCheckAppRunning
  !insertmacro forceStopArgus
!macroend
