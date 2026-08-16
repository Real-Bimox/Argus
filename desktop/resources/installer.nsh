; Argus intentionally maps a normal window close to "hide in tray". NSIS must
; therefore terminate the old release explicitly before its built-in running-
; app check; sending WM_CLOSE alone can never prove that the process exited.
!macro customInit
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM "Argus.exe"'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM "argus-backend.exe"'
  Sleep 750
!macroend
