from pathlib import Path
A=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109');p=A/'apps/android/app/src/main/java/com/denzic/companion/app/ExportContents.java';s=p.read_text(encoding='utf-8')
def sub(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
sub('final JSONArray problems,materials;','final JSONArray problems,materials;final JSONObject notes;')
sub('JSONArray errors,JSONArray savedMaterials){this.key=key;', 'JSONArray errors,JSONArray savedMaterials){this(key,title,token,m,n,tr,errors,savedMaterials,null);}\n        Source(String key,String title,String token,MeetingStore.Snapshot m,MeetingStore.Minutes n,TranslationStore.Entry tr,JSONArray errors,JSONArray savedMaterials,JSONObject savedNotes){notes=savedNotes;this.key=key;')
sub('!meeting.tasks.isEmpty());','!meeting.tasks.isEmpty())||notes!=null&&notes.getJSONArray("entries").length()>0;')
sub('+materialBinding()).getBytes', '+materialBinding()+"\\u0000"+(notes==null?"":canonical(notes))).getBytes')
sub('.put("problems",problems).put("materials",materialInfo());', '.put("problems",problems).put("materials",materialInfo()).put("noteImages",imageCount());')
sub('        private boolean hasMaterial', '        private int imageCount()throws Exception{int count=0;if(notes!=null){JSONArray entries=notes.getJSONArray("entries");for(int i=0;i<entries.length();i++)if(entries.getJSONObject(i).has("image"))count++;}return count;}\n        private boolean hasMaterial')
sub('StringBuilder text=new StringBuilder(meeting.notes);for(MeetingStore.Task task:meeting.tasks)', 'StringBuilder text=new StringBuilder(meeting==null?"":meeting.notes);for(MeetingStore.Task task:meeting==null?Collections.<MeetingStore.Task>emptyList():meeting.tasks)')
sub('result.add(new MeetingDocumentSections.Section("用户补充与事项",text.toString(),false));','if(notes!=null)text.append("\\n").append(RecordingNotes.text(notes));\n                result.add(new MeetingDocumentSections.Section("用户补充与事项",text.toString(),false));')
p.write_text(s,encoding='utf-8',newline='\r\n');print('Export content binding includes independently saved notes')
