//! Resume the one pinned optional speech model without retaining copies of audio.
use std::{fs::{self, OpenOptions}, io::{Read, Seek, SeekFrom, Write}, path::Path};
use reqwest::{blocking::Client, header::{ACCEPT_ENCODING, CONTENT_RANGE, RANGE}, StatusCode};

fn valid_range(value: &str, offset: u64, size: u64) -> bool {
    let Some((span, total)) = value.strip_prefix("bytes ").and_then(|s| s.split_once('/')) else { return false; };
    let Some((start, end)) = span.split_once('-') else { return false; };
    match (start.parse::<u64>(), end.parse::<u64>(), total.parse::<u64>()) {
        (Ok(start), Ok(end), Ok(total)) => start == offset && end >= start && end < size && total == size,
        _ => false,
    }
}

/// A partial is private to the pinned model hash and protected by the caller's
/// process lock. A successful return means the complete file matches the hash.
pub(super) fn fetch(client: &Client, url: &str, size: u64, hash: &str, partial: &Path) -> Result<(), String> {
    if let Ok(metadata) = fs::symlink_metadata(partial) {
        if !metadata.is_file() || metadata.file_type().is_symlink() { return Err("本地模型下载文件不可用。".into()); }
    }
    let mut file = OpenOptions::new().read(true).write(true).create(true).open(partial)
        .map_err(|_| "无法保存本地模型。")?;
    let mut offset = file.metadata().map_err(|_| "无法读取本地模型下载进度。")?.len();
    if offset == size && super::shared::verified(partial, hash).is_ok() { return Ok(()); }
    if offset >= size { file.set_len(0).map_err(|_| "无法重新准备本地模型。")?; offset = 0; }
    for attempt in 0..2 {
        let mut request = client.get(url).header(ACCEPT_ENCODING, "identity");
        if offset > 0 { request = request.header(RANGE, format!("bytes={offset}-")); }
        let response = request.send().map_err(|_| "本地模型下载中断，重试可继续。")?;
        if response.status() == StatusCode::RANGE_NOT_SATISFIABLE && offset > 0 && attempt == 0 {
            file.set_len(0).map_err(|_| "无法重新准备本地模型。")?; offset = 0; continue;
        }
        if response.status() == StatusCode::OK {
            // A server ignoring Range returned a whole file, not a suffix.
            file.set_len(0).map_err(|_| "无法重新准备本地模型。")?; offset = 0;
        } else if response.status() == StatusCode::PARTIAL_CONTENT {
            let valid = response.headers().get(CONTENT_RANGE).and_then(|v|v.to_str().ok())
                .is_some_and(|v|valid_range(v, offset, size));
            if !valid { return Err("模型服务器返回的续传范围不正确，已保留下载进度。".into()); }
        } else { return Err("本地模型下载失败，请检查网络后重试。".into()); }
        file.seek(SeekFrom::Start(offset)).map_err(|_| "无法保存本地模型。")?;
        let count = std::io::copy(&mut response.take(size - offset + 1), &mut file);
        file.flush().and_then(|_|file.sync_all()).map_err(|_| "本地模型保存失败。")?;
        let count = count.map_err(|_| "本地模型下载中断，重试可继续。")?;
        if count > size - offset {
            file.set_len(offset).map_err(|_| "无法恢复模型下载进度。")?;
            return Err("模型服务器返回的文件过大，已保留原下载进度。".into());
        }
        if count != size - offset { return Err("本地模型下载未完成，重试可继续。".into()); }
        drop(file);
        if super::shared::verified(partial, hash).is_err() {
            OpenOptions::new().write(true).truncate(true).open(partial).map_err(|_| "无法重置模型下载。")?;
            return Err("本地模型校验失败，重试将重新下载。".into());
        }
        return Ok(());
    }
    Err("本地模型下载未完成，请重试。".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::{Digest, Sha256};
    use std::{io::{Read, Write}, net::TcpListener, sync::{Arc, Mutex}, thread};

    fn root() -> std::path::PathBuf {
        let dir=std::env::temp_dir().join(format!("companion-model-download-test-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&dir).unwrap();dir
    }
    fn cleanup(root: &Path) {
        let resolved=root.canonicalize().unwrap();
        assert_eq!(resolved.parent().unwrap(),std::env::temp_dir().canonicalize().unwrap());
        assert!(resolved.file_name().unwrap().to_string_lossy().starts_with("companion-model-download-test-"));
        fs::remove_dir_all(resolved).unwrap();
    }
    fn server(replies:Vec<Vec<u8>>) -> (String, Arc<Mutex<Vec<String>>>, thread::JoinHandle<()>) {
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();let addr=listener.local_addr().unwrap();
        let requests=Arc::new(Mutex::new(Vec::new()));let out=requests.clone();
        let handle=thread::spawn(move || for reply in replies {
            let (mut stream,_)=listener.accept().unwrap();stream.set_read_timeout(Some(std::time::Duration::from_secs(5))).unwrap();
            let mut data=Vec::new();let mut buf=[0;1024];
            while !data.windows(4).any(|w|w==b"\r\n\r\n") {
                let n=stream.read(&mut buf).unwrap();if n==0 {break;}data.extend_from_slice(&buf[..n]);
            }
            out.lock().unwrap().push(String::from_utf8(data).unwrap().to_ascii_lowercase());
            stream.write_all(&reply).unwrap();
        });
        (format!("http://{addr}/model"),requests,handle)
    }
    fn response(status:&str,headers:&str,body:&[u8])->Vec<u8> {
        let mut out=format!("HTTP/1.1 {status}\r\n{headers}Connection: close\r\n\r\n").into_bytes();
        out.extend_from_slice(body);out
    }
    fn client()->Client {Client::builder().no_proxy().timeout(std::time::Duration::from_secs(5)).build().unwrap()}
    fn hash(bytes:&[u8])->String {format!("{:x}",Sha256::digest(bytes))}

    #[test]
    fn interrupted_download_resumes_without_repeating_completed_bytes() {
        let data=b"abcdefghij";let (url,requests,worker)=server(vec![
            response("200 OK","Content-Length: 10\r\n",&data[..4]),
            response("206 Partial Content","Content-Length: 6\r\nContent-Range: bytes 4-9/10\r\n",&data[4..]),
        ]);
        let dir=root();let part=dir.join("model.part");
        assert!(fetch(&client(),&url,10,&hash(data),&part).is_err());
        assert_eq!(fs::read(&part).unwrap(),&data[..4]);
        fetch(&client(),&url,10,&hash(data),&part).unwrap();assert_eq!(fs::read(&part).unwrap(),data);
        worker.join().unwrap();let req=requests.lock().unwrap();assert!(!req[0].contains("range: bytes="));
        assert!(req[1].contains("range: bytes=4-"));drop(req);cleanup(&dir);
    }

    #[test]
    fn server_ignoring_range_restarts_cleanly() {
        let data=b"abcdefghij";let (url,requests,worker)=server(vec![response("200 OK","Content-Length: 10\r\n",data)]);
        let dir=root();let part=dir.join("model.part");fs::write(&part,&data[..4]).unwrap();
        fetch(&client(),&url,10,&hash(data),&part).unwrap();assert_eq!(fs::read(&part).unwrap(),data);
        worker.join().unwrap();assert!(requests.lock().unwrap()[0].contains("range: bytes=4-"));cleanup(&dir);
    }

    #[test]
    fn wrong_server_range_does_not_damage_saved_prefix() {
        let data=b"abcdefghij";let (url,_,worker)=server(vec![
            response("206 Partial Content","Content-Length: 6\r\nContent-Range: bytes 3-8/10\r\n",&data[4..]),
        ]);
        let dir=root();let part=dir.join("model.part");fs::write(&part,&data[..4]).unwrap();
        assert!(fetch(&client(),&url,10,&hash(data),&part).is_err());assert_eq!(fs::read(&part).unwrap(),&data[..4]);
        worker.join().unwrap();cleanup(&dir);
    }

    #[test]
    fn completed_corrupt_partial_is_replaced_and_verified() {
        let data=b"abcdefghij";let (url,requests,worker)=server(vec![response("200 OK","Content-Length: 10\r\n",data)]);
        let dir=root();let part=dir.join("model.part");fs::write(&part,b"0123456789").unwrap();
        fetch(&client(),&url,10,&hash(data),&part).unwrap();assert_eq!(fs::read(&part).unwrap(),data);
        worker.join().unwrap();assert!(!requests.lock().unwrap()[0].contains("range: bytes="));cleanup(&dir);
    }
}
