Option Explicit
Dim sh, fso, repoRoot, bat
Set sh = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' scripts\run_cafe_door_hidden.vbs -> repo root is parent of scripts
repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
bat = repoRoot & "\cafe_door.bat"
sh.CurrentDirectory = repoRoot
' 0 = hidden window, True = wait for exit
sh.Run "cmd /c """ & bat & """", 0, True
