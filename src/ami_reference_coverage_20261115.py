"""Require the complete official speaker set; AMI is not always four-person."""
import xml.etree.ElementTree as ET
def official_speakers(archive,meeting):
 meetings=[m for m in ET.fromstring(archive.read('corpusResources/meetings.xml')) if m.attrib.get('observation')==meeting]
 if len(meetings)!=1:raise ValueError('Meeting metadata missing or ambiguous: '+meeting)
 speakers=sorted(s.attrib['nxt_agent'] for s in meetings[0] if s.tag=='speaker')
 files=sorted(n for n in archive.namelist() if n.startswith('words/'+meeting+'.') and n.endswith('.words.xml'))
 expected=[f'words/{meeting}.{s}.words.xml' for s in speakers]
 if len(speakers)<2 or len(speakers)!=len(set(speakers)) or files!=expected:
  raise ValueError('Incomplete official AMI references: '+repr((meeting,speakers,files)))
 return speakers
