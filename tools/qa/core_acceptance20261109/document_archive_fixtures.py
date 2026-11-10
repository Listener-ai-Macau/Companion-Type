"""Independent standard-library ZIP fixtures for bounded local document reading."""
from pathlib import Path
import io,zipfile,json,struct,sys
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
def fixture(name,entries):
 target=out/(name+'.zip')
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
  for path,data in entries:archive.writestr(path,data)
 return target
text='<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>公开资料：周二核对12000元预算。</w:t></w:r></w:p></w:body></w:document>'
valid=fixture('valid',[('word/',''),('word/document.xml',text),('word/media/not-read.bin',b'\x01\x02')]);source=valid.read_bytes();directory=source.index(b'PK\x01\x02');cases=[]
def changed(name,mutate):
 data=bytearray(source);mutate(data);(out/(name+'.zip')).write_bytes(data);cases.append(name)
changed('truncated',lambda data:data.__delitem__(slice(-8,None)))
def crc(data):
 first=data.index(b'PK\x01\x02',directory+4);value=struct.unpack_from('<I',data,first+16)[0]^1;struct.pack_into('<I',data,first+16,value)
 # Keep the local/central declarations consistent; the actual data CRC is wrong.
 local=struct.unpack_from('<I',data,first+42)[0];struct.pack_into('<I',data,local+14,value)
changed('bad-crc',crc)
def size(data):
 at=data.index(b'PK\x01\x02',directory+4);local=struct.unpack_from('<I',data,at+42)[0];struct.pack_into('<I',data,at+24,1);struct.pack_into('<I',data,local+22,1)
changed('false-output-size',size)
changed('unsupported-method',lambda data:struct.pack_into('<H',data,directory+10,12))
changed('oversized-advertised-part',lambda data:struct.pack_into('<I',data,directory+24,8*1024*1024+1))
fixture('traversal',[('../word/document.xml',text)]);cases.append('traversal')
fixture('duplicate',[('word/document.xml',text),('word/document.xml',text)]);cases.append('duplicate')
def overlap(data):
 at=data.index(b'PK\x01\x02',directory+4);struct.pack_into('<I',data,at+42,0)
changed('alias-local-header',overlap)
(out/'manifest.json').write_text(json.dumps({'text':text,'valid':'valid.zip','invalid':cases},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Prepared independent ZIP size/CRC/name/overlap fixtures; no product or owner data.')
