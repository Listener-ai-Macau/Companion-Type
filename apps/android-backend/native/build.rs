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
    if std::env::var_os("CARGO_FEATURE_MOBILE_ASR").is_some() {
        let source=Path::new("../../windows/src-tauri/src/backend/volcengine.rs");
        let probe=Path::new("../../windows/src-tauri/src/backend/volcengine/network_probe.rs").canonicalize().expect("shared ASR probe");
        let probe=probe.to_string_lossy().replace('\\',"/");
        let text=std::fs::read_to_string(source).expect("shared ASR adapter");
        let text=text.lines().map(|line| if let Some(doc)=line.strip_prefix("//!"){format!("//{doc}")}else{line.to_string()}).collect::<Vec<_>>().join("\n");
        assert_eq!(text.matches("mod network_probe;").count(),1);
        let text=text.replace("mod network_probe;",&format!("#[path = \"{probe}\"] mod network_probe;"));
        // Desktop-only unit tests depend on the Tauri host recording manager;
        // mobile runs the shared adapter's local-network fixture separately.
        assert_eq!(text.matches("#[cfg(test)]\nmod tests {").count(),1);
        let text=text.replace("#[cfg(test)]\nmod tests {", "#[cfg(any())]\nmod tests {");
        let out=std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap()).join("volcengine_shared.rs");
        std::fs::write(out,text).expect("prepare shared ASR adapter");
        println!("cargo:rerun-if-changed={}",source.display());
        println!("cargo:rerun-if-changed={probe}");
    }
}
