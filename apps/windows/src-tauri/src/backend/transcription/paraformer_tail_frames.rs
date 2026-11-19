use super::shared::{verified, OFFICIAL_MODEL_SHA, OFFICIAL_TAIL_FILE, OFFICIAL_TAIL_SHA};
use std::{
    fs::{self, File},
    io::{self, Read, Seek, SeekFrom, Write},
    path::Path,
    sync::Mutex,
};

const PREFIX: &[u8] = include_bytes!("official_paraformer_assets/tail-graph-prefix.bin");
const INPUTS: &[u8] = include_bytes!("official_paraformer_assets/tail-graph-inputs.bin");
const METADATA: &[u8] = include_bytes!("official_paraformer_assets/tail-runtime-metadata.bin");

// Offsets are relative to the pinned official ONNX with Companion's original
// metadata appended. Only the graph header, the two graph inputs, and model
// metadata are replaced. The original nodes and weights are copied verbatim.
const GRAPH_FIELD: u64 = 24;
const GRAPH_CONTENT: u64 = 29;
const GRAPH_INPUTS_START: u64 = 237_279_227;
const GRAPH_INPUTS_END: u64 = 237_279_320;
const PUBLISHER_BYTES: u64 = 237_653_364;

static PREPARING_TAIL: Mutex<()> = Mutex::new(());

fn copy_range(source: &mut File, out: &mut File, start: u64, end: u64) -> io::Result<()> {
    source.seek(SeekFrom::Start(start))?;
    let copied = io::copy(&mut (&mut *source).take(end - start), out)?;
    if copied != end - start {
        return Err(io::Error::from(io::ErrorKind::UnexpectedEof));
    }
    Ok(())
}

fn write_tail_graph(source: &Path, target: &Path) -> io::Result<()> {
    let mut source = File::open(source)?;
    let mut target = File::options().write(true).create_new(true).open(target)?;
    copy_range(&mut source, &mut target, 0, GRAPH_FIELD)?;
    target.write_all(PREFIX)?;
    copy_range(&mut source, &mut target, GRAPH_CONTENT, GRAPH_INPUTS_START)?;
    target.write_all(INPUTS)?;
    copy_range(&mut source, &mut target, GRAPH_INPUTS_END, PUBLISHER_BYTES)?;
    target.write_all(METADATA)?;
    target.sync_all()
}

pub(super) fn prepare(official: &Path) -> Result<(), String> {
    let _guard = PREPARING_TAIL
        .lock()
        .map_err(|_| "本地转写模型准备失败。")?;
    let official = official.canonicalize().map_err(|e| e.to_string())?;
    let target = official.join(OFFICIAL_TAIL_FILE);
    if verified(&target, OFFICIAL_TAIL_SHA).is_ok() {
        return Ok(());
    }
    let original = official.join("model.int8.onnx");
    verified(&original, OFFICIAL_MODEL_SHA)?;
    let temporary = official.join(format!(".paraformer-tail-{}.tmp", uuid::Uuid::new_v4()));
    let result = (|| {
        write_tail_graph(&original, &temporary).map_err(|error| error.to_string())?;
        verified(&temporary, OFFICIAL_TAIL_SHA)?;
        super::super::super::export::replace_file(&temporary, &target)
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}
