!define NYXOR_PROCESS_SCRIPT "${__FILEDIR__}\processes.ps1"

!macro NYXOR_CHECK_DIRECTORY_ACCESS DIRECTORY
  ${If} "${DIRECTORY}" != ""
    System::Call 'kernel32::SetEnvironmentVariable(t "NYXOR_INSTALL_TARGET", t "${DIRECTORY}") i.r0'
    nsExec::ExecToLog '"$PowerShellPath" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\nyxor-processes.ps1" -Mode Access'
    Pop $R0
    ${If} $R0 == 4
      SetErrorLevel 1
      MessageBox MB_OK|MB_ICONEXCLAMATION "Windows does not allow updating NYXOR in this folder:$\r$\n${DIRECTORY}$\r$\n$\r$\nClose setup, then right-click the NYXOR installer and choose Run as administrator. Your account and lists will be kept." /SD IDOK
      Quit
    ${ElseIf} $R0 != 0
      SetErrorLevel 1
      MessageBox MB_OK|MB_ICONEXCLAMATION "Windows could not verify access to the NYXOR installation folder. Setup stopped before changing the installed files. Check folder permissions or PowerShell restrictions, then run setup again." /SD IDOK
      Quit
    ${EndIf}
  ${EndIf}
!macroend

!macro customCheckAppRunning
  InitPluginsDir
  File /oname=$PLUGINSDIR\nyxor-processes.ps1 "${NYXOR_PROCESS_SCRIPT}"
  !insertmacro NYXOR_CHECK_DIRECTORY_ACCESS "$INSTDIR"
  # A newly chosen folder can be writable while the previous installation
  # still needs administrator rights to uninstall. Check both registry scopes.
  !ifndef BUILD_UNINSTALLER
    !ifdef INSTALL_REGISTRY_KEY
      ReadRegStr $R2 HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
      !insertmacro NYXOR_CHECK_DIRECTORY_ACCESS "$R2"
      ReadRegStr $R2 HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation
      !insertmacro NYXOR_CHECK_DIRECTORY_ACCESS "$R2"
    !endif
  !endif
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
