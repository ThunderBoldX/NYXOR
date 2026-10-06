!define NYXOR_PROCESS_SCRIPT "${__FILEDIR__}\processes.ps1"

!macro customCheckAppRunning
  InitPluginsDir
  File /oname=$PLUGINSDIR\nyxor-processes.ps1 "${NYXOR_PROCESS_SCRIPT}"
  # Pass the chosen directory as data, not embedded PowerShell code.
  System::Call 'kernel32::SetEnvironmentVariable(t "NYXOR_INSTALL_TARGET", t "$INSTDIR") i.r0'
  System::Call 'kernel32::GetCurrentProcessId() i.r1'
  System::Call 'kernel32::SetEnvironmentVariable(t "NYXOR_INSTALLER_PID", t r1) i.r0'
  nsExec::ExecToLog '"$PowerShellPath" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\nyxor-processes.ps1" -Mode Check'
  Pop $R0
  ${If} $R0 == 0
    DetailPrint "Closing NYXOR and its farming engine..."
    nsExec::ExecToLog '"$PowerShellPath" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\nyxor-processes.ps1" -Mode Close'
    Pop $R0
    ${If} $R0 != 0
      SetErrorLevel 1
      MessageBox MB_OK|MB_ICONEXCLAMATION "Windows could not close NYXOR from the selected installation folder. Check Task Manager or administrator permissions, then run setup again." /SD IDOK
      Quit
    ${EndIf}
  ${ElseIf} $R0 != 1
    SetErrorLevel 1
    MessageBox MB_OK|MB_ICONEXCLAMATION "Windows could not check NYXOR processes. Setup cannot continue safely. Check Windows permissions or PowerShell restrictions, then run setup again." /SD IDOK
    Quit
  ${EndIf}
!macroend
