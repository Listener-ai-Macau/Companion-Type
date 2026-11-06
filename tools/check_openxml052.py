from pathlib import Path
import subprocess,json
qa=Path('E:/CodexData/Companion/.build-cache/exports052-qa')
b=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-material-exports052')
framework=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319')
args=[str(framework/'csc.exe'),'/nologo','/target:exe','/out:'+str(qa/'ValidatePresentation052.exe'),
      '/reference:'+str(qa/'DocumentFormat.OpenXml.dll'),'/reference:'+str(framework/'WPF/WindowsBase.dll'),
      '/reference:'+str(framework/'System.Web.Extensions.dll'),str(Path('work/ValidatePresentation052.cs').resolve())]
p=subprocess.run(args,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
(b/'openxml-compiler.log').write_text(p.stdout+p.stderr,encoding='utf8');assert p.returncode==0,p.stdout+p.stderr
files=sorted(sorted(b.glob('native-files-*'))[-1].glob('*.pptx'))
p=subprocess.run([str(qa/'ValidatePresentation052.exe'),*[str(f) for f in files]],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(b/'openxml-schema-first.json').write_text(p.stdout,encoding='utf8');print(p.stdout);print(p.stderr);raise SystemExit(p.returncode)
