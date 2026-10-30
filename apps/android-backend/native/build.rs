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
    if std::env::var_os("CARGO_FEATURE_MOBILE_MEMO").is_some() {
        // Include the exact comparison functions used by the shared short-memo
        // extractor; fail closed if the desktop source layout ever changes.
        let source=Path::new("../../windows/src-tauri/src/backend/minutes.rs");
        let text=std::fs::read_to_string(source).expect("shared minutes source");
        let start="fn normalized_fact_chars(text: &str) -> Vec<char> {";
        let end="fn merge_missing_source_facts(";
        assert_eq!(text.matches(start).count(),1);
        assert_eq!(text.matches(end).count(),1);
        let start_at=text.find(start).unwrap();let end_at=text.find(end).unwrap();
        assert!(start_at<end_at);
        let section=text[start_at..end_at].replace("fn source_fact_covered(","pub(super) fn source_fact_covered(");
        let out=std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap()).join("minutes_fact_match.rs");
        std::fs::write(out,section).expect("prepare shared fact comparison");
        println!("cargo:rerun-if-changed={}",source.display());
    }
    if std::env::var_os("CARGO_FEATURE_MOBILE_MINUTES").is_some() {
        let root=Path::new("../../windows/src-tauri/src/backend");
        let original=root.join("minutes.rs");
        let out=std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap());
        let mut text=std::fs::read_to_string(&original).expect("desktop minutes");
        text=text.lines().map(|line|if let Some(doc)=line.strip_prefix("//!"){format!("//{doc}")}else{line.to_string()}).collect::<Vec<_>>().join("\n");
        for module in ["long_meeting","short_memo","context_plan","question_sources"] {
            let declaration=if module=="long_meeting" {"pub(super) mod long_meeting;".to_string()}else{format!("mod {module};")};
            assert_eq!(text.matches(&declaration).count(),1);
            let source=root.join("minutes").join(format!("{module}.rs"));
            let path=source.canonicalize().expect("desktop minutes module").to_string_lossy().replace('\\',"/");
            let path=if module=="long_meeting" {
                let long=std::fs::read_to_string(&source).expect("desktop long minutes");
                let long=long.lines().map(|line|if let Some(doc)=line.strip_prefix("//!"){format!("//{doc}")}else{line.to_string()}).collect::<Vec<_>>().join("\n");
                assert_eq!(long.matches("#[cfg(test)]\nmod tests;").count(),1);
                let long=long.replace("#[cfg(test)]\nmod tests;","#[cfg(any())]\nmod tests;");
                let test_guard="if cfg!(test) && std::env::var_os(\"COMPANION_TYPE_STATE_PATH\").is_none()\n        && std::env::var_os(\"COMPANION_TYPE_STATE_DIR\").is_none() { return None; }";
                assert_eq!(long.matches(test_guard).count(),1);
                // The mobile caller must always provide its private cache root,
                // including in tests. No desktop state directory is consulted.
                let long=long.replace(test_guard,"");
                let path=out.join("mobile_long_minutes.rs");std::fs::write(&path,long).expect("prepare long minutes");
                path.to_string_lossy().replace('\\',"/")
            }else{path};
            let replacement=if module=="long_meeting" {format!("#[path = \"{path}\"] pub(super) mod long_meeting;")} else {format!("#[path = \"{path}\"] mod {module};")};
            text=text.replace(&declaration,&replacement);
            println!("cargo:rerun-if-changed={}",source.display());
        }
        assert_eq!(text.matches("#[cfg(test)]\nmod tests {").count(),1);
        text=text.replace("#[cfg(test)]\nmod tests {","#[cfg(any())]\nmod tests {");
        std::fs::write(out.join("mobile_minutes_shared.rs"),text).expect("prepare shared minutes");
        println!("cargo:rerun-if-changed={}",original.display());
    }
}
