// Compile the same vendored Opus sources as the Windows decoder.
fn main() {
    use std::path::Path;
    let root=Path::new("../../../third_party/denzic-platform/host_audio/native/opus");
    let mut build=cc::Build::new();
    build.include(root.join("include")).include(root.join("src")).include(root.join("celt"))
        .include(root.join("silk")).include(root.join("silk/float"))
        .define("OPUS_BUILD",None).define("USE_ALLOCA",None)
        .define("PACKAGE_VERSION",Some("\"1.5.2\"")).warnings(false);
    for (file,groups) in [("opus_sources.mk",&["OPUS_SOURCES","OPUS_SOURCES_FLOAT"][..]),
                          ("celt_sources.mk",&["CELT_SOURCES"][..]),
                          ("silk_sources.mk",&["SILK_SOURCES","SILK_SOURCES_FLOAT"][..])] {
        let manifest=std::fs::read_to_string(root.join(file)).expect("vendored Opus source manifest");
        let mut selected=false;
        for line in manifest.lines() {
            if let Some((name,_))=line.split_once('=') {selected=groups.contains(&name.trim());continue;}
            let name=line.trim().trim_end_matches('\\').trim();
            if selected && name.ends_with(".c") {build.file(root.join(name));}
        }
    }
    println!("cargo:rerun-if-changed={}",root.display());
    build.compile("companion_opus");
}
