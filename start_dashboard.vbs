' start_dashboard.vbs
' เปิดเว็บแอปพอร์ตหุ้นแบบ "ไม่มีหน้าต่าง terminal" แล้วเปิดเบราว์เซอร์ให้อัตโนมัติ
' ใช้: ดับเบิลคลิกไฟล์นี้

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder  = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = folder

' ถ้ามีเซิร์ฟเวอร์รันอยู่แล้วที่พอร์ต 5000 ก็ข้ามการเปิดใหม่
Set exec = sh.Exec("cmd /c netstat -ano ^| findstr :5000 ^| findstr LISTENING")
running = (Len(exec.StdOut.ReadAll) > 0)

If Not running Then
  ' pythonw = รัน Python แบบไม่มีหน้าต่าง console
  ' 0 = ซ่อนหน้าต่าง, False = ไม่รอให้จบ (รันค้างเป็น background)
  sh.Run "pythonw " & Chr(34) & folder & "\app.py" & Chr(34), 0, False
  WScript.Sleep 2500   ' รอเซิร์ฟเวอร์บูต ~2.5 วินาที
End If

' เปิดเบราว์เซอร์ไปหน้าแดชบอร์ด
sh.Run "http://127.0.0.1:5000/dashboard"
