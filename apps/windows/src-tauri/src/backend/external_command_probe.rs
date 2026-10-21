//! Explicit installed-binary fixtures for wrapper supervision. The fixture
//! branch is dispatched before settings/BLE and requires a probe-created
//! directory and nonce. It cannot run an arbitrary command.
use super::external_command::{self, Failure, Limits, MAX_STDERR_BYTES, MAX_STDOUT_BYTES};
use crate::companion_v1::{fixture_snapshot, synced_device_session, CompanionV1ControlRequest};
use serde_json::{json, Value};
use std::{
    fs,
    io::Write,
    path::Path,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};

const PERMIT: &str = "controlled-wrapper-fixture.txt";
const PRIVATE: &str = "wrapper-probe-private-secret";

pub(crate) fn fixture_main(args: &[String]) -> i32 {
    let Some(root) = args.first().map(Path::new) else {
        return 125;
    };
    let (Some(nonce), Some(mode)) = (args.get(1), args.get(2)) else {
        return 125;
    };
    let permit = root.join(PERMIT);
    if !fs::metadata(&permit).is_ok_and(|metadata| metadata.is_file() && metadata.len() <= 100)
        || !fs::read_to_string(permit).is_ok_and(|text| text == *nonce)
    {
        return 125;
    }
    // Mode names are fixed, never used as caller-selected file paths.
    if ![
        "asr",
        "minutes",
        "exit",
        "stdout_large",
        "stderr_large",
        "invalid_utf8",
        "empty",
        "hang",
        "error_json",
        "truncated_json",
        "incomplete_json",
        "partial_json",
        "invalid_actions",
        "argv",
        "tree_root",
        "tree_child",
        "tree_grandchild",
        "exit_with_child",
    ]
    .contains(&mode.as_str())
    {
        return 125;
    }
    let pid_temp = root.join(format!("{mode}.pid.tmp"));
    if fs::write(&pid_temp, std::process::id().to_string()).is_err()
        || fs::rename(&pid_temp, root.join(format!("{mode}.pid"))).is_err()
    {
        return 125;
    }
    let write = |bytes: &[u8], stderr: bool| -> i32 {
        let result = if stderr {
            std::io::stderr().write_all(bytes)
        } else {
            std::io::stdout().write_all(bytes)
        };
        if result.is_ok() {
            0
        } else {
            1
        }
    };
    match mode.as_str() {
        "asr" => write(br#"{"text":"Controlled wrapper final"}"#, false),
        "minutes" => write(br##"{"summary":["Keep the controlled source fact."],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"# Controlled minutes\nKeep the controlled source fact."}"##, false),
        "exit" => { let _ = write(PRIVATE.as_bytes(), true); let _ = write(b"Incomplete output must not become final", false); 37 },
        "stdout_large" | "stderr_large" => {
            let size = if mode == "stdout_large" { MAX_STDOUT_BYTES } else { MAX_STDERR_BYTES };
            write(&vec![b'X'; size + 1], mode == "stderr_large")
        },
        "invalid_utf8" => write(&[0xff, 0xfe], false),
        "empty" => 0,
        "error_json" => write(json!({"error":PRIVATE}).to_string().as_bytes(), false),
        "truncated_json" => write(br#"{"text":"unfinished"#, false),
        "incomplete_json" => write(b"{}", false),
        "partial_json" => write(br##"{"text":"Controlled partial","is_final":false,"quality":"draft","summary":["Controlled partial"],"markdown":"# Controlled partial"}"##, false),
        "invalid_actions" => write(br##"{"summary":["Controlled source"],"markdown":"# Controlled minutes","actionItems":[{"text":"Task","owner":37}]}"##, false),
        "argv" => write(serde_json::to_string(&args[3..]).unwrap_or_default().as_bytes(), false),
        "tree_root" | "tree_child" | "exit_with_child" => {
            let Ok(exe) = std::env::current_exe() else { return 125; };
            let mut child = std::process::Command::new(exe);
            child.arg("--external-command-test-fixture").arg(root).arg(nonce)
                .arg(if mode == "tree_child" { "tree_grandchild" } else { "tree_child" });
            #[cfg(windows)]
            { use std::os::windows::process::CommandExt; child.creation_flags(0x08000000); }
            if child.spawn().is_err() { return 125; }
            if mode == "exit_with_child" {
                let started = Instant::now();
                while !root.join("tree_grandchild.pid").is_file() && started.elapsed() < Duration::from_secs(3) { thread::sleep(Duration::from_millis(10)); }
                if !root.join("tree_grandchild.pid").is_file() { return 125; }
                return write(b"Controlled wrapper final", false);
            }
            loop { thread::sleep(Duration::from_millis(100)); }
        },
        "hang" | "tree_grandchild" => loop { thread::sleep(Duration::from_millis(100)); },
        _ => 125,
    }
}

#[cfg(windows)]
fn all_owned_pids_stopped(root: &Path, expected: usize) -> bool {
    use windows::Win32::{
        Foundation::{CloseHandle, WAIT_OBJECT_0},
        System::Threading::{OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE},
    };
    let files: Vec<_> = match fs::read_dir(root) {
        Ok(files) => files
            .flatten()
            .filter(|entry| {
                entry
                    .path()
                    .extension()
                    .is_some_and(|extension| extension == "pid")
            })
            .collect(),
        Err(_) => return false,
    };
    if files.len() != expected {
        return false;
    }
    files.into_iter().all(|file| {
        let Some(pid) = fs::read_to_string(file.path())
            .ok()
            .and_then(|text| text.parse::<u32>().ok())
        else {
            return false;
        };
        match unsafe { OpenProcess(PROCESS_SYNCHRONIZE, false, pid) } {
            Ok(handle) => {
                let exited = unsafe { WaitForSingleObject(handle, 2000) } == WAIT_OBJECT_0;
                unsafe {
                    let _ = CloseHandle(handle);
                }
                exited
            }
            Err(error) => error.code().0 as u32 == 0x80070057, // no longer exists, not an access-denied assumption
        }
    })
}

#[cfg(not(windows))]
fn all_owned_pids_stopped(_root: &Path, _expected: usize) -> bool {
    false
}

pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    #[cfg(not(windows))]
    return Err("Windows wrapper supervision probe unavailable".into());
    fs::create_dir(output)
        .map_err(|_| "External command probe requires a fresh, creatable output folder")?;
    let exe = std::env::current_exe().map_err(|_| "Cannot identify probe executable")?;
    let exe = exe.to_str().ok_or("Probe executable path is not Unicode")?;
    let prepare = |name: &str, mode: &str| -> Result<(std::path::PathBuf, Vec<String>), String> {
        let root = output.join(name);
        fs::create_dir(&root).map_err(|_| "Cannot create fixture directory")?;
        let nonce = uuid::Uuid::new_v4().to_string();
        fs::write(root.join(PERMIT), &nonce).map_err(|_| "Cannot authorize controlled fixture")?;
        let args = vec![
            "--external-command-test-fixture".into(),
            root.to_string_lossy().into(),
            nonce,
            mode.into(),
        ];
        Ok((root, args))
    };
    let audio = output.join("controlled-original-audio.bin");
    fs::write(&audio, b"controlled original must remain")
        .map_err(|_| "Cannot create controlled original")?;
    let request: CompanionV1ControlRequest = serde_json::from_value(
        json!({"action":"deviceSyncRecordings","title":"Controlled wrapper fixture"}),
    )
    .map_err(|_| "Cannot create controlled session")?;
    let mut session = synced_device_session(&fixture_snapshot(), &request, "wrapper-fixture");
    session.source = "controlledWrapperFixture".into();
    session.audio_path = Some(audio.to_string_lossy().into());
    session.transcript_text = "Decision: Keep the controlled source fact.".into();
    let l0 = super::minutes::rules_l0_minutes(&session, "wrapper-fixture");
    let mut checks = Vec::new();
    let mut check = |name: &str, passed: bool| -> Result<(), String> {
        checks.push(json!({"name":name,"passed":passed}));
        if passed {
            Ok(())
        } else {
            Err(format!("External command probe failed: {name}"))
        }
    };
    let (_, args) = prepare("asr-valid", "asr")?;
    let result = super::transcription::run_command_transcript(
        exe,
        &args,
        Limits::for_timeout(Duration::from_secs(5)),
    );
    check(
        "actual_asr_wrapper_valid_final",
        result.is_ok_and(|value| {
            value.text == "Controlled wrapper final" && value.mode == "external-command"
        }),
    )?;
    let (_, args) = prepare("minutes-valid", "minutes")?;
    let result = super::minutes::run_minutes_command(
        exe,
        &args,
        &session,
        &l0,
        Limits::for_timeout(Duration::from_secs(5)),
    );
    check(
        "actual_minutes_wrapper_valid_final",
        result.is_ok_and(|value| {
            value.quality == "final" && value.markdown.contains("controlled source fact")
        }),
    )?;
    for minutes in [false, true] {
        let prefix = if minutes { "minutes" } else { "asr" };
        for (mode, expected) in [
            ("exit", "exit code 37"),
            ("stdout_large", "stdout exceeds size limit"),
            ("stderr_large", "stderr exceeds size limit"),
            ("invalid_utf8", "UTF-8"),
            ("hang", "timed out"),
            ("empty", "empty"),
            ("error_json", "invalid or incomplete"),
            ("truncated_json", "invalid or incomplete"),
            ("incomplete_json", "invalid or incomplete"),
            ("partial_json", "invalid or incomplete"),
        ] {
            let name = format!("{prefix}_{mode}");
            let (root, args) = prepare(&name, mode)?;
            let limit = Limits::for_timeout(if mode == "hang" {
                Duration::from_secs(1)
            } else {
                Duration::from_secs(5)
            });
            let started = Instant::now();
            let error = if minutes {
                let result = super::minutes::run_minutes_command(exe, &args, &session, &l0, limit);
                let fallback = super::minutes::finalize_minutes(result, l0.clone(), &session);
                if fallback.quality != "draft" || fallback.markdown != l0.markdown {
                    return Err("Wrapper failure lost its local draft".into());
                }
                fallback.llm_note.unwrap_or_default()
            } else {
                match super::transcription::run_command_transcript(exe, &args, limit) {
                    Err(error) => error,
                    Ok(_) => return Err(format!("Invalid wrapper result accepted: {name}")),
                }
            };
            let expected = if mode == "empty" && !minutes {
                "did not print a transcript"
            } else {
                expected
            };
            check(
                &name,
                error.contains(expected)
                    && !error.contains(PRIVATE)
                    && !error.contains(exe)
                    && all_owned_pids_stopped(&root, 1)
                    && started.elapsed() < Duration::from_secs(5),
            )?;
        }
    }
    let (root, args) = prepare("minutes-invalid-actions", "invalid_actions")?;
    let result = super::minutes::run_minutes_command(
        exe,
        &args,
        &session,
        &l0,
        Limits::for_timeout(Duration::from_secs(5)),
    );
    let fallback = super::minutes::finalize_minutes(result, l0.clone(), &session);
    check(
        "invalid_action_fields_preserve_local_draft",
        fallback.quality == "draft"
            && fallback.markdown == l0.markdown
            && fallback
                .llm_note
                .as_deref()
                .is_some_and(|note| note.contains("invalid or incomplete"))
            && all_owned_pids_stopped(&root, 1),
    )?;
    let (_, mut args) = prepare("literal-argv", "argv")?;
    let literals = vec![
        "space and 中文".to_string(),
        "quotes \" stay literal".into(),
        "C:\\path with space\\".into(),
        "".into(),
        "$() & | ` ;".into(),
    ];
    args.extend(literals.clone());
    let result = external_command::run(
        exe,
        &args,
        Limits::for_timeout(Duration::from_secs(5)),
        None,
    )
    .map_err(|_| "Literal argv fixture failed")?;
    check(
        "spaces_unicode_quotes_empty_and_shell_text_remain_literal",
        serde_json::from_str::<Vec<String>>(&result).ok().as_ref() == Some(&literals),
    )?;
    for cancelled in [false, true] {
        let name = if cancelled {
            "cancellation_stops_three_generation_tree"
        } else {
            "timeout_stops_three_generation_tree"
        };
        let (root, args) = prepare(name, "tree_root")?;
        let stop = Arc::new(AtomicBool::new(false));
        let flag = Arc::clone(&stop);
        let watched = root.clone();
        let watcher = cancelled.then(|| {
            thread::spawn(move || {
                let started = Instant::now();
                while !watched.join("tree_grandchild.pid").is_file()
                    && started.elapsed() < Duration::from_secs(5)
                {
                    thread::sleep(Duration::from_millis(10));
                }
                flag.store(true, Ordering::SeqCst);
            })
        });
        let limits = Limits::for_timeout(Duration::from_secs(if cancelled { 8 } else { 2 }));
        let result = external_command::run(exe, &args, limits, Some(&stop));
        if let Some(watcher) = watcher {
            watcher.join().map_err(|_| "Cancellation watcher failed")?;
        }
        check(
            name,
            result
                == Err(if cancelled {
                    Failure::Cancelled
                } else {
                    Failure::Timeout
                })
                && all_owned_pids_stopped(&root, 3),
        )?;
    }
    let (root, args) = prepare("normal-parent-exit", "exit_with_child")?;
    let result = external_command::run(
        exe,
        &args,
        Limits::for_timeout(Duration::from_secs(5)),
        None,
    );
    let stopped = all_owned_pids_stopped(&root, 3);
    if result.as_deref() != Ok("Controlled wrapper final") || !stopped {
        return Err(format!(
            "Normal-exit fixture failed: failure={:?}, output_bytes={}, stopped={stopped}",
            result.as_ref().err(),
            result.as_ref().map_or(0, |text| text.len())
        ));
    }
    check("normal_parent_exit_closes_remaining_descendants", true)?;
    let (_, args) = prepare("pre-cancelled", "asr")?;
    check(
        "already_cancelled_command_never_starts",
        external_command::run(
            exe,
            &args,
            Limits::for_timeout(Duration::from_secs(5)),
            Some(&AtomicBool::new(true)),
        ) == Err(Failure::Cancelled)
            && !output.join("pre-cancelled/asr.pid").exists(),
    )?;
    let missing = output.join(format!("missing-{PRIVATE}.exe"));
    let error = external_command::run(
        &missing.to_string_lossy(),
        &[],
        Limits::for_timeout(Duration::from_secs(5)),
        None,
    )
    .unwrap_err();
    check(
        "missing_command_does_not_echo_path",
        error == Failure::Start && !error.to_string().contains(PRIVATE),
    )?;
    check(
        "original_audio_and_transcript_retained",
        fs::read(&audio).is_ok_and(|bytes| bytes == b"controlled original must remain")
            && session.transcript_text == "Decision: Keep the controlled source fact.",
    )?;
    let report = json!({"schema":"companion.type.external_command_probe.v1","result":"PASS_LOCAL_WRAPPER_FAULTS_ONLY","checks":checks,
        "realUserProfileAccess":false,"networkAccess":false,"deviceAccess":false,"unrelatedProcessesTerminated":false,
        "scope":"Type wrapper process/output boundary; external scripts control their own internal service protocols",
        "trueAsrAcceptance":"NOT_RUN","guiAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN"});
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).map_err(|_| "Cannot encode wrapper report")?,
    )
    .map_err(|_| "Cannot save wrapper report")?;
    Ok(report)
}
