from pathlib import Path
W=Path(__file__).parent
source=(W/'prepare_template_phone147.py').read_text(encoding='utf8').replace('android147-local-r2','android158-local').replace('147','158')
exec(compile(source,str(W/'prepare_template_phone147.py'),'exec'),{'__name__':'__main__','__file__':str(W/'prepare_template_phone147.py')})
for name in ['run_note_phone157.py','review_resumed_phone157.cjs']:
 (W/name.replace('157','158')).write_text((W/name).read_text(encoding='utf8').replace('157','158'),encoding='utf8')
