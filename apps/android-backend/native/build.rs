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
        let end="fn missing_source_facts(";
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
        for module in ["long_meeting","short_memo","context_plan","question_sources","template","short_evidence"] {
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
                // Progress belongs to the mobile adapter; preserve the shared
                // desktop engine and insert hooks only at durable boundaries.
                let hook="super::super::mobile_minutes_progress";
                let at="    if result.processing.as_ref().is_some_and(|p|p.is_complete()) {";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("{at}\n        {hook}::check()?;"));
                let at="        match super::run_deepseek_prompt(endpoint,model,key,&input,&result,&prompt,&system,client) {";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("        let response=super::run_deepseek_prompt(endpoint,model,key,&input,&result,&prompt,&system,client);\n        {hook}::check()?;\n        match response {{"));
                let at="    save_checkpoint(&path, &checkpoint)?;\n    let started = Instant::now();";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("    save_checkpoint(&path, &checkpoint)?;\n    {hook}::update(checkpoint.chapters.iter().flatten().map(|c| (c.end-c.start) as u64).sum())?;\n    let started = Instant::now();"));
                let at="    while let Some(index) = pending.pop_front() {\n        let (start, end) = slices[index];";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("    while let Some(index) = pending.pop_front() {{\n        let (start, end) = slices[index];\n        {hook}::check()?;"));
                let at="            let remaining = ATTEMPT_TIME.saturating_sub(started.elapsed());\n            if fresh < MAX_FRESH_REQUESTS";
                assert_eq!(long.matches(at).count(),2);
                let long=long.replace(at,&format!("            {hook}::check()?;\n            let remaining = ATTEMPT_TIME.saturating_sub(started.elapsed());\n            if fresh < MAX_FRESH_REQUESTS"));
                let at="                let retried_result = prepare(request(index, slices.len(), &part, remaining.min(Duration::from_secs(180))));\n                if let (Ok(previous), Ok(candidate))";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("                let retried_result = prepare(request(index, slices.len(), &part, remaining.min(Duration::from_secs(180))));\n                {hook}::check()?;\n                if let (Ok(previous), Ok(candidate))"));
                let at="                if let Err(error) = save_checkpoint(&path, &checkpoint) { failure = Some(error); break; }";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("{at}\n                {hook}::update(checkpoint.chapters.iter().flatten().map(|c| (c.end-c.start) as u64).sum())?;"));
                let at="    // A nearby conversation can contain genuine instructions";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("    {hook}::check()?;\n{at}"));
                let at="        if let Ok(points) = request_concise_overview";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("        {hook}::check()?;\n{at}"));
                let at="        } else if let Ok(indices) = request_overview(endpoint, model, key, &overview_summary, client) {\n            prepend_overview(&mut minutes, &overview_summary, &indices);\n        }";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("        }} else {{\n            {hook}::check()?;\n            if let Ok(indices) = request_overview(endpoint, model, key, &overview_summary, client) {{\n                prepend_overview(&mut minutes, &overview_summary, &indices);\n            }}\n        }}"));
                let at="    for (start, end) in [(0, third), (third, two_thirds), (two_thirds, items.len())] {";
                assert_eq!(long.matches(at).count(),1);
                let long=long.replace(at,&format!("{at}\n        {hook}::check()?;"));
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
    if std::env::var_os("CARGO_FEATURE_MOBILE_CONTROL").is_some() {
        let root=Path::new("../../windows/src-tauri/src/backend");
        let out=std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap());
        let read=|name:&str|{let path=root.join(name);println!("cargo:rerun-if-changed={}",path.display());std::fs::read_to_string(path).expect("shared recorder source").replace("\r\n","\n")};
        let section=|text:&str,start:&str,end:&str|->String {
            assert_eq!(text.matches(start).count(),1,"missing or ambiguous section start: {start}");
            assert_eq!(text.matches(end).count(),1,"missing or ambiguous section end: {end}");
            let a=text.find(start).unwrap();let b=text.find(end).unwrap();assert!(a<b);text[a..b].to_owned()
        };
        let source=read("recording_wire.rs");
        let constants=section(&source,"const DESCRIPTOR_BYTES: usize", "const GOLDEN: &str");
        let helpers=section(&source,"fn fail(reason: &str)","mod legacy;");
        let key=section(&source,"#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]","#[derive(Clone, Debug, PartialEq, Eq)]\npub(crate) struct Descriptor");
        let descriptor=section(&source,"#[derive(Clone, Debug, PartialEq, Eq)]\npub(crate) struct Descriptor","#[derive(Clone, Debug, PartialEq, Eq)]\nstruct Page");
        let group=section(&source,"#[derive(Debug, PartialEq, Eq, Serialize)]\n#[serde(rename_all = \"camelCase\")]\npub(crate) struct GroupPlan","fn unhex(s: &str)");
        let transport=read("recording_wire/transport.rs");
        let transport=section(&transport,"const STATUS_PREFIX: usize","    pub(crate) fn validate(&self, d: &Descriptor)");
        let transport=format!("use super::{{fail,u16le,u32le,u64le}};\n{transport}\n}}\n");
        let transport_path=out.join("mobile_control_transport.rs");std::fs::write(&transport_path,transport).expect("prepare recorder peer");
        let control_source=read("recording_wire/control.rs");
        let test_path=root.join("recording_wire/control/pause_tests.rs").canonicalize().expect("shared pause tests").to_string_lossy().replace('\\',"/");
        assert_eq!(control_source.matches("mod pause_tests;").count(),1);
        let control_source=control_source.lines().map(|line|if let Some(doc)=line.strip_prefix("//!"){format!("//{doc}")}else{line.to_string()}).collect::<Vec<_>>().join("\n")
            .replace("mod pause_tests;",&format!("#[path = \"{test_path}\"] mod pause_tests;"));
        let control=out.join("mobile_control_protocol.rs");std::fs::write(&control,control_source).expect("prepare recorder protocol");
        let peer_path=transport_path.to_string_lossy().replace('\\',"/");let control_path=control.to_string_lossy().replace('\\',"/");
        std::fs::write(out.join("mobile_control_wire.rs"),format!("use serde::Serialize;\nuse sha2::{{Digest,Sha256}};\nuse std::collections::{{BTreeMap,BTreeSet}};\n{constants}\n{helpers}\n{key}\n{descriptor}\n{group}\n#[path = \"{peer_path}\"] pub(crate) mod transport;\n#[path = \"{control_path}\"] pub(crate) mod control;\n")).expect("prepare recorder wire");
        let journal=read("recorder_control.rs");
        let prefix=section(&journal,"use std::{fs::", "/// The cross-process lock spans the complete command/status operation.");
        let catalogue=read("recorder_control/catalogue.rs");
        let catalogue=catalogue.lines().map(|line|if let Some(doc)=line.strip_prefix("//!"){format!("//{doc}")}else{line.to_string()}).collect::<Vec<_>>().join("\n");
        let catalogue_path=out.join("mobile_control_catalogue.rs");
        std::fs::write(&catalogue_path,catalogue).expect("prepare recorder sealed status");
        let catalogue_path=catalogue_path.to_string_lossy().replace('\\',"/");
        let bridge=read("ble_bridge/recorder_control.rs");
        let settlement=section(&bridge,"#[derive(Debug,PartialEq,Eq)]\nenum SettlementAction", "async fn settle(")
            .replace("enum SettlementAction", "pub(crate) enum SettlementAction")
            .replace("fn settlement_action(","pub(crate) fn settlement_action(");
        let local=read("recorder_control/local_adoption.rs");
        let local=section(&local,"impl Journal {\n    fn from_local(","pub(crate) fn adopt_local(")
            .replace("    fn from_local(","    pub(crate) fn from_local(");
        let local_path=out.join("mobile_control_local.rs");std::fs::write(&local_path,format!("use super::*;\n{local}")).expect("prepare original local adoption");
        let local_path=local_path.to_string_lossy().replace('\\',"/");
        std::fs::write(out.join("mobile_control_journal.rs"),format!("{prefix}\n#[path = \"{catalogue_path}\"] mod catalogue;\npub(crate) use catalogue::SealedCatalogueEnd;\n#[path = \"{local_path}\"] mod local_adoption;\n{settlement}")).expect("prepare recorder journal");
        let device=read("device_connection.rs");
        let identity=section(&device,"pub(crate) fn stable_device_id(","fn preference_path()");
        std::fs::write(out.join("mobile_device_identity.rs"),identity).expect("prepare device identity comparison");
    }
}
