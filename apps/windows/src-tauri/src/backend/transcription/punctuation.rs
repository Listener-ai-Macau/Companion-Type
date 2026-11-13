//! Optional local punctuation. Never replace recognizer words or numeric tokens.
use libloading::Library;
use std::{ffi::{c_char,c_void,CStr,CString},path::Path};
pub(crate) const DIRECTORY:&str="ct-transformer-punctuation-zh-en-2024";
pub(crate) const MODEL_SHA:&str="e93593a6dbd69a07f8734ef269dbe861a379755f8d1c8354719432116f2c44bd";
pub(crate) const MODEL_SIZE:u64=294_372_519;
pub(crate) const MODEL_URL:&str="https://huggingface.co/csukuangfj/sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12/resolve/432aeba669265e7aeb06b9359753419683b38597/model.onnx";
pub(crate) const MIRROR_URL:&str="https://hf-mirror.com/csukuangfj/sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12/resolve/432aeba669265e7aeb06b9359753419683b38597/model.onnx";
#[repr(C)]
struct Config {model:*const c_char,threads:i32,debug:i32,provider:*const c_char}
type Create=unsafe extern "C" fn(*const Config)->*const c_void;
type Add=unsafe extern "C" fn(*const c_void,*const c_char)->*const c_char;
type Free=unsafe extern "C" fn(*const c_char);
type Destroy=unsafe extern "C" fn(*const c_void);
pub(super) struct Punctuator {handle:*const c_void,add:Add,free:Free,destroy:Destroy}
impl Drop for Punctuator {fn drop(&mut self){unsafe{(self.destroy)(self.handle)}}}
impl Punctuator {
    // The owning Runtime destroys this object before unloading its library.
    pub(super) fn optional(lib:&Library,root:&Path)->Option<Self>{
        let model=root.join(DIRECTORY).join("model.onnx");
        super::verified(&model,MODEL_SHA).ok()?;
        let model=CString::new(model.to_str()?).ok()?;
        let cpu=CString::new("cpu").ok()?;
        unsafe {
            let create:Create=*lib.get(b"SherpaOnnxCreateOfflinePunctuation\0").ok()?;
            let add:Add=*lib.get(b"SherpaOfflinePunctuationAddPunct\0").ok()?;
            let free:Free=*lib.get(b"SherpaOfflinePunctuationFreeText\0").ok()?;
            let destroy:Destroy=*lib.get(b"SherpaOnnxDestroyOfflinePunctuation\0").ok()?;
            let handle=create(&Config{model:model.as_ptr(),threads:1,debug:0,provider:cpu.as_ptr()});
            if handle.is_null(){None}else{Some(Self{handle,add,free,destroy})}
        }
    }
    pub(super) fn apply(&self,raw:&str)->String{
        if raw.len()>12_000{return raw.into();}
        let Ok(input)=CString::new(raw)else{return raw.into()};
        unsafe {
            let value=(self.add)(self.handle,input.as_ptr());
            if value.is_null(){return raw.into();}
            let output=CStr::from_ptr(value).to_str().ok().map(str::to_owned);
            (self.free)(value);
            output.filter(|text|preserves_literals(raw,text)).unwrap_or_else(||raw.into())
        }
    }
}
fn content(text:&str)->String {
    text.chars().filter(|c|!c.is_whitespace()&&!"，。？！、；：,.?!;:".contains(*c)).collect()
}
fn numbers(text:&str)->Vec<String>{
    let chars:Vec<_>=text.chars().collect();let mut out=Vec::new();let mut i=0;
    while i<chars.len(){
        if !chars[i].is_ascii_digit(){i+=1;continue;}
        let start=i;i+=1;
        while i<chars.len(){
            if chars[i].is_ascii_digit(){i+=1;}
            else if ".,:/-".contains(chars[i])&&i+1<chars.len()&&chars[i+1].is_ascii_digit(){i+=2;}
            else{break;}
        }
        out.push(chars[start..i].iter().collect());
    }
    out
}
fn preserves_literals(raw:&str,output:&str)->bool{
    content(raw)==content(output)&&numbers(raw)==numbers(output)
}
#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn punctuation_preserves_words_numbers_negation_and_symbols(){
        assert!(preserves_literals("小李说追加20%的费用尚未批准周五再确认","小李说，追加20%的费用尚未批准，周五再确认。"));
        assert!(preserves_literals("预算12000元下降-5%版本1.2","预算12000元，下降-5%，版本1.2。"));
        assert!(preserves_literals("hello world 2026/11/13","hello world，2026/11/13。"));
    }
    #[test]fn changed_facts_and_numeric_separators_reject_the_whole_result(){
        for (raw,changed) in [("尚未批准20%","已经批准20%。"),("3.14","3，14。"),("1,000","1000。"),("小李","小王。"),("下降-5%","下降5%。"),("a+b=c","a，b，c。")]{assert!(!preserves_literals(raw,changed));}
    }
    #[test]fn missing_model_is_optional_before_loading_any_neural_runtime(){
        assert!(super::super::verified(&std::env::temp_dir().join("companion-no-punctuation-model.onnx"),MODEL_SHA).is_err());
    }
}
