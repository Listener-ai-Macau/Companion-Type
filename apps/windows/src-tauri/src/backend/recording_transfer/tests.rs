use super::*;

fn fixture() -> (Source, Vec<u8>) {
    let body: Vec<u8> = (0..180_000).map(|n| (n % 239) as u8).collect();
    let sha = Sha256::digest(&body);
    let mut prefix = [0u8; 8];
    prefix.copy_from_slice(&sha[..8]);
    (
        Source {
            device: "buffered-receive-fixture".into(),
            recording_id: 78,
            codec: 3,
            source_mode: 1,
            duration_ms: 90_000,
            total_length: body.len() as u32,
            sha256_prefix: prefix,
            content_crc32: crc32fast::hash(&body),
        },
        body,
    )
}

fn fresh_root() -> PathBuf {
    let root = std::env::temp_dir().join(format!(
        "companion-receive-buffer-{}",
        uuid::Uuid::new_v4().simple()
    ));
    fs::create_dir(&root).unwrap();
    root
}

// Run only as a child of the crash/restart check. exit deliberately skips the
// Cursor and BufWriter destructors, unlike dropping a cursor in this process.
#[test]
#[ignore = "subprocess helper for interrupted receive"]
fn exit_with_uncommitted_tail() {
    let root = std::env::var_os("COMPANION_TRANSFER_TEST_CHILD_ROOT").unwrap();
    let length: usize = std::env::var("COMPANION_TRANSFER_TEST_CHILD_BYTES")
        .unwrap()
        .parse()
        .unwrap();
    let (source, body) = fixture();
    let (mut cursor, _) = Cursor::open(Path::new(&root), source).unwrap();
    for packet in body[..length].chunks(224) {
        cursor.append(packet).unwrap();
    }
    std::process::exit(0);
}

#[test]
fn process_exit_replays_only_durable_prefix_and_finishes_exact_bytes() {
    let (source, body) = fixture();
    for length in [4_321, 80_000] {
        let root = fresh_root();
        let status = std::process::Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "backend::recording_transfer::tests::exit_with_uncommitted_tail",
                "--ignored",
            ])
            .env("COMPANION_TRANSFER_TEST_CHILD_ROOT", &root)
            .env("COMPANION_TRANSFER_TEST_CHILD_BYTES", length.to_string())
            .status()
            .unwrap();
        assert!(status.success());
        let committed = if length < CHECKPOINT_BYTES as usize {
            0
        } else {
            (CHECKPOINT_BYTES as usize).div_ceil(224) * 224
        };
        let (mut cursor, recovered) = Cursor::open(&root, source.clone()).unwrap();
        assert_eq!(recovered, body[..committed]);
        assert_eq!(fs::metadata(&cursor.path).unwrap().len(), committed as u64);
        for packet in body[committed..].chunks(224) {
            cursor.append(packet).unwrap();
        }
        cursor.finish(&body).unwrap();
        assert_eq!(fs::read(&cursor.path).unwrap(), body);
        drop(cursor);
        let (cursor, complete) = Cursor::open(&root, source.clone()).unwrap();
        assert_eq!(complete, body);
        drop(cursor);
        release(&root, source.clone()).unwrap();
    }
}

#[test]
fn failed_audio_flush_never_advances_receipt_or_consumes_recording() {
    let root = fresh_root();
    let (source, body) = fixture();
    let (mut cursor, _) = Cursor::open(&root, source.clone()).unwrap();
    cursor.append(&body[..4_321]).unwrap();
    cursor.checkpoint().unwrap();
    let committed_receipt = fs::read(&cursor.receipt_path).unwrap();
    // The next small payload is accepted into RAM, but its eventual disk write
    // fails through an actual read-only file handle at the committed position.
    let mut read_only = File::open(&cursor.path).unwrap();
    read_only.seek(SeekFrom::Start(4_321)).unwrap();
    cursor.file = Some(BufWriter::with_capacity(CHECKPOINT_BYTES as usize, read_only));
    cursor.append(&body[4_321..8_642]).unwrap();
    assert!(cursor.checkpoint().is_err());
    assert_eq!(fs::read(&cursor.receipt_path).unwrap(), committed_receipt);
    assert!(release(&root, source.clone()).is_err());
    drop(cursor);
    let (cursor, recovered) = Cursor::open(&root, source.clone()).unwrap();
    assert_eq!(recovered, body[..4_321]);
    assert_eq!(fs::read(&cursor.receipt_path).unwrap(), committed_receipt);
    drop(cursor);
    assert!(release(&root, source).is_err());
}
