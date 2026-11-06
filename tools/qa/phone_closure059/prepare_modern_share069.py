from pathlib import Path
import json,subprocess,shutil,hashlib
W=Path(__file__).parent
text=(W/'check_shell_share069.py').read_text(encoding='utf8')
text=text.replace('ShellShareVerbs.exe','ModernShareWindow.exe').replace('ShellShareVerbs.obj','ModernShareWindow.obj').replace('ShellShareVerbs.cpp','ModernShareWindow.cpp')
end=text.index('run=subprocess.run([str(exe),str(public)]')
text=text[:end]+"\nprint('Modern system-share window prepared, not launched; source uses only exact observed Windows.ModernShare verb.')\n"
exec(compile(text,'modern-share069-build','exec'))
