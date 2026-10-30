use crate::backend::control_runtime::{self,Transport};
use jni::{objects::{JByteArray,JObject,JObjectArray,JString,JValue},JNIEnv};
use std::path::Path;

struct JavaTransport<'a,'local> {env:&'a mut JNIEnv<'local>,callback:&'a JObject<'local>}
impl JavaTransport<'_,'_> {
    fn error(&mut self)->String {let _=self.env.exception_clear();"蓝牙连接或录音控制失败；原请求和录音保留。".into()}
    fn read(&mut self,name:&str)->Result<Vec<u8>,String> {
        let value=match self.env.call_method(self.callback,name,"()[B",&[]).and_then(|v|v.l()){Ok(v)=>v,Err(_)=>return Err(self.error())};
        if value.is_null(){return Err("设备未返回录音状态。".into());}
        let array=JByteArray::from(value);let result=self.env.convert_byte_array(&array).map_err(|_|"设备录音状态无法读取。".to_string());
        let _=self.env.delete_local_ref(array);result
    }
    fn send(&mut self,name:&str,wire:&[u8],returns_bytes:bool)->Result<Option<Vec<u8>>,String> {
        let bytes=self.env.byte_array_from_slice(wire).map_err(|_|"录音控制数据不可用。")?;
        let obj=JObject::from(bytes);let signature=if returns_bytes{"([B)[B"}else{"([B)V"};
        let called=self.env.call_method(self.callback,name,signature,&[JValue::Object(&obj)]);
        let _=self.env.delete_local_ref(obj);
        let value=match called{Ok(v)=>v,Err(_)=>return Err(self.error())};
        if !returns_bytes{return Ok(None);}
        let obj=value.l().map_err(|_|"设备容量回复不可用。")?;if obj.is_null(){return Ok(None);}
        let array=JByteArray::from(obj);let result=self.env.convert_byte_array(&array).map(Some).map_err(|_|"设备容量回复不可用。".to_string());
        let _=self.env.delete_local_ref(array);result
    }
}
impl Transport for JavaTransport<'_,'_> {
    fn identity(&mut self)->Result<Vec<u8>,String>{self.read("identity")}
    fn status(&mut self)->Result<Vec<u8>,String>{self.read("status")}
    fn write_control(&mut self,wire:&[u8])->Result<(),String>{self.send("writeControl",wire,false).map(|_|())}
    fn capacity_slots(&mut self,wire:&[u8])->Result<Option<Vec<u8>>,String>{self.send("capacitySlots",wire,true)}
    fn catalogue(&mut self)->Result<Vec<Vec<u8>>,String>{
        let value=match self.env.call_method(self.callback,"catalogue","()[[B",&[]).and_then(|v|v.l()){Ok(v)=>v,Err(_)=>return Err(self.error())};
        if value.is_null(){return Err("设备录音目录不可用。".into());}
        let array=JObjectArray::from(value);let len=self.env.get_array_length(&array).map_err(|_|"录音目录不可读取。")?;
        if len>1024{return Err("录音目录过大。".into());}
        let mut entries=Vec::with_capacity(len as usize);
        for i in 0..len {let item=self.env.get_object_array_element(&array,i).map_err(|_|"录音目录不可读取。")?;
            if item.is_null(){return Err("录音目录项目不可读取。".into());}
            let bytes=JByteArray::from(item);let data=self.env.convert_byte_array(&bytes).map_err(|_|"录音目录项目不可读取。")?;
            let _=self.env.delete_local_ref(bytes);entries.push(data);
        }
        let _=self.env.delete_local_ref(array);Ok(entries)
    }
    fn local_files(&mut self)->Result<Vec<std::path::PathBuf>,String>{
        let value=match self.env.call_method(self.callback,"localFiles","()[Ljava/lang/String;",&[]).and_then(|v|v.l()){Ok(v)=>v,Err(_)=>return Err(self.error())};
        if value.is_null(){return Err("本地录音目录不可用。".into());}
        let array=JObjectArray::from(value);let len=self.env.get_array_length(&array).map_err(|_|"本地录音目录不可读取。")?;
        if len>1024{return Err("本地录音目录过大。".into());}
        let mut entries=Vec::with_capacity(len as usize);
        for i in 0..len {let item=self.env.get_object_array_element(&array,i).map_err(|_|"本地录音路径不可读取。")?;
            if item.is_null(){return Err("本地录音路径不可读取。".into());}
            let value=JString::from(item);let path:String=self.env.get_string(&value).map_err(|_|"本地录音路径不可读取。")?.into();
            let _=self.env.delete_local_ref(value);entries.push(path.into());
        }
        let _=self.env.delete_local_ref(array);Ok(entries)
    }
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeRecordingControl_reconcileNative<'local>(
    mut env:JNIEnv<'local>,_class:JObject<'local>,callback:JObject<'local>,root:JString<'local>,host:JString<'local>,device:JString<'local>
)->jni::sys::jstring {
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<String,String>{
        if callback.is_null(){return Err("录音连接不可用。".into());}
        let root:String=env.get_string(&root).map_err(|_|"录音控制目录不可读取。")?.into();
        let host:String=env.get_string(&host).map_err(|_|"录音会话不可读取。")?.into();
        let device:String=env.get_string(&device).map_err(|_|"设备身份不可读取。")?.into();
        let mut transport=JavaTransport{env:&mut env,callback:&callback};
        let report=control_runtime::reconcile_catalogue(Path::new(&root),&host,&device,&mut transport)?;
        serde_json::to_string(&report).map_err(|_|"原录音状态无法读取。".into())
    }));
    match result {
        Ok(Ok(value))=>match env.new_string(value){Ok(s)=>s.into_raw(),Err(_)=>{let _=env.throw_new("java/io/IOException","原录音状态无法读取。");std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","原录音目录未核对；原音保持不变。");std::ptr::null_mut()},
    }
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeRecordingControl_executeNative<'local>(
    mut env:JNIEnv<'local>,_class:JObject<'local>,callback:JObject<'local>,root:JString<'local>,host:JString<'local>,device:JString<'local>,
    command:jni::sys::jint,seconds:jni::sys::jint
)->jni::sys::jstring {
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<String,String>{
        if callback.is_null()||!(0..=5).contains(&command)||!(0..=65535).contains(&seconds){return Err("录音控制参数无效。".into());}
        let root:String=env.get_string(&root).map_err(|_|"录音控制目录不可读取。")?.into();
        let host:String=env.get_string(&host).map_err(|_|"录音会话不可读取。")?.into();
        let device:String=env.get_string(&device).map_err(|_|"设备身份不可读取。")?.into();
        let mut transport=JavaTransport{env:&mut env,callback:&callback};
        let report=control_runtime::execute(Path::new(&root),&host,&device,command as u8,seconds as u16,&mut transport)?;
        serde_json::to_string(&report).map_err(|_|"录音状态无法读取。".into())
    }));
    match result {
        Ok(Ok(value))=>match env.new_string(value){Ok(s)=>s.into_raw(),Err(_)=>{let _=env.throw_new("java/io/IOException","录音状态无法读取。");std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","录音操作未完成；原录音和请求保留。");std::ptr::null_mut()},
    }
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeRecordingControl_listNative<'local>(
    mut env:JNIEnv<'local>,_class:JObject<'local>,root:JString<'local>,device:JString<'local>,identity:JByteArray<'local>
)->jni::sys::jstring {
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<String,String>{
        let root:String=env.get_string(&root).map_err(|_|"录音控制目录不可读取。")?.into();
        let device:String=env.get_string(&device).map_err(|_|"设备身份不可读取。")?.into();
        let identity=env.convert_byte_array(identity).map_err(|_|"设备身份不可读取。")?;
        let inventory=control_runtime::inventory(Path::new(&root),&device,&identity)?;
        serde_json::to_string(&inventory).map_err(|_|"录音控制记录无法读取。".into())
    }));
    match result {
        Ok(Ok(value))=>match env.new_string(value){Ok(s)=>s.into_raw(),Err(_)=>{let _=env.throw_new("java/io/IOException","录音控制记录无法读取。");std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","录音控制记录无法读取；原音保留。");std::ptr::null_mut()},
    }
}

#[no_mangle]
pub extern "system" fn Java_com_denzic_companion_mobile_NativeRecordingControl_adoptNative<'local>(
    mut env:JNIEnv<'local>,_class:JObject<'local>,callback:JObject<'local>,root:JString<'local>,device:JString<'local>
)->jni::sys::jstring {
    let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<String,String>{
        if callback.is_null(){return Err("录音连接不可用。".into());}
        let root:String=env.get_string(&root).map_err(|_|"录音控制目录不可读取。")?.into();
        let device:String=env.get_string(&device).map_err(|_|"设备身份不可读取。")?.into();
        let mut transport=JavaTransport{env:&mut env,callback:&callback};
        let report=control_runtime::adopt_local(Path::new(&root),&device,&mut transport)?;
        serde_json::to_string(&report).map_err(|_|"原录音状态无法读取。".into())
    }));
    match result {
        Ok(Ok(value))=>match env.new_string(value){Ok(s)=>s.into_raw(),Err(_)=>{let _=env.throw_new("java/io/IOException","原录音状态无法读取。");std::ptr::null_mut()}},
        Ok(Err(error))=>{let _=env.throw_new("java/io/IOException",error);std::ptr::null_mut()},
        Err(_)=>{let _=env.throw_new("java/io/IOException","原录音未接续；原音保持不变。");std::ptr::null_mut()},
    }
}
