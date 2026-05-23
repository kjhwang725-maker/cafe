Option Explicit
' webapp.py 를 콘솔 창 없이 백그라운드로 띄운다. 로그는 webapp.log 에 append.
' 사용: 더블클릭 또는 webapp_start.bat 에서 호출.
Dim sh, fso, repoRoot, logPath, cmd, port
Set sh = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
repoRoot = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.CurrentDirectory = repoRoot
logPath = repoRoot & "\webapp.log"

port = "8088"
If WScript.Arguments.Count >= 1 Then port = WScript.Arguments(0)

' py -3 가 있으면 그걸로, 없으면 python 으로
cmd = "cmd /c py -3 webapp.py --port " & port & " >> """ & logPath & """ 2>&1"
' 0 = hidden, False = 부모는 즉시 리턴(백그라운드)
sh.Run cmd, 0, False
