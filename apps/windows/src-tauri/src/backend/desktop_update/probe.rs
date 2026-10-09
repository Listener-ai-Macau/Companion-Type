use super::*;
use serde_json::{json, Value};
pub(crate) fn self_test(output: &Path) -> Result<Value, String> {
    fs::create_dir(output).map_err(|_| "Desktop update probe requires a fresh output folder")?;
    let root = output
        .canonicalize()
        .map_err(|_| "Probe directory unavailable")?;
    let mut checks = vec![];
    macro_rules! check {
        ($name:expr,$condition:expr) => {
            if !$condition {
                return Err(format!("desktop update probe failed: {}", $name));
            }
            checks.push($name);
        };
    }
    check!("release-version-increase", newer("0.1.0", "v0.1.1")?);
    check!("version-equality-refused", !newer("0.1.0", "0.1.0")?);
    check!("downgrade-refused", !newer("0.2.0", "0.1.0")?);
    check!(
        "prerelease-refused",
        newer("0.1.0", "0.2.0-beta.1").is_err()
    );
    check!(
        "malformed-version-refused",
        newer("0.1.0", "latest").is_err()
    );
    let url = "https://api.github.com/repos/Listener-ai-Macau/Companion-Type/releases/assets/123";
    check!("fixed-repository-asset", asset_id(url)? == "123");
    for (name,url) in [("wrong-repository","https://api.github.com/repos/Listener-ai-Macau/Listener-Type/releases/assets/123"),
        ("wrong-host","https://api.github.com.attacker.invalid/repos/Listener-ai-Macau/Companion-Type/releases/assets/123"),
        ("insecure-transport","http://api.github.com/repos/Listener-ai-Macau/Companion-Type/releases/assets/123"),
        ("url-credential","https://user:secret@api.github.com/repos/Listener-ai-Macau/Companion-Type/releases/assets/123"),
        ("url-query","https://api.github.com/repos/Listener-ai-Macau/Companion-Type/releases/assets/123?secret=fixture"),
        ("encoded-path","https://api.github.com/repos/Listener-ai-Macau/Companion-Type/releases/assets/%31%32%33")] {
        check!(name,asset_id(url).is_err());
    }
    // Public, non-secret test vector from minisign-verify (MIT licensed).
    // Payload is exactly "test", not an installer; execution is never attempted.
    let public="untrusted comment: minisign public key E7620F1842B4E81F\nRWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3";
    let signature="untrusted comment: signature from minisign secret key\nRWQf6LRCGA9i59SLOFxz6NxvASXDJeRtuZykwQepbDEGt87ig1BNpWaVWuNrm73YiIiJbq71Wi+dP9eKL8OC351vwIasSSbXxwA=\ntrusted comment: timestamp:1555779966\tfile:test\nQtKMXWyYcwdpZAlPF7tE2ENJkRd1ujvKjlj1m9RtHTBnZPa5WKU5uWRs5GoP5M/VqE81QFuMKI5k/SfNQUaOAA==";
    let public = base64::engine::general_purpose::STANDARD.encode(public);
    let signature = base64::engine::general_purpose::STANDARD.encode(signature);
    verify(b"test", &signature, &public)?;
    checks.push("known-signature-accepted");
    check!(
        "tampered-body-refused",
        verify(b"Test", &signature, &public).is_err()
    );
    check!(
        "malformed-signature-refused",
        verify(b"test", "invalid", &public).is_err()
    );
    check!(
        "malformed-key-refused",
        verify(b"test", &signature, "invalid").is_err()
    );
    check!(
        "empty-installer-refused",
        verify(b"", &signature, &public).is_err()
    );
    let msi = installer::fixture("Companion Type", "0.2.0", installer::UPGRADE_CODE, "x64")?;
    installer::validate(&msi, "0.2.0")?;
    checks.push("msi-product-version-upgrade-architecture-accepted");
    check!(
        "msi-version-disagrees",
        installer::validate(&msi, "0.2.1").is_err()
    );
    for (name, product, code, arch) in [
        (
            "msi-other-product",
            "Listener Type",
            installer::UPGRADE_CODE,
            "x64",
        ),
        (
            "msi-other-upgrade-code",
            "Companion Type",
            "{00000000-0000-0000-0000-000000000001}",
            "x64",
        ),
        (
            "msi-other-architecture",
            "Companion Type",
            installer::UPGRADE_CODE,
            "Intel",
        ),
    ] {
        check!(
            name,
            installer::validate(&installer::fixture(product, "0.2.0", code, arch)?, "0.2.0")
                .is_err()
        );
    }
    check!(
        "non-msi-signed-fixture-not-installable",
        installer::validate(b"test", "0.2.0").is_err()
    );
    check!(
        "malformed-msi-refused",
        installer::validate(&msi[..msi.len() / 2], "0.2.0").is_err()
    );
    let manager = Manager::default();
    let held = manager.begin()?;
    check!("duplicate-operation-refused", manager.begin().is_err());
    drop(held);
    check!("operation-lease-released", manager.begin().is_ok());
    let coordinator = crate::coordinator::CompanionCoordinator::new_fixture();
    let held = coordinator.begin_desktop_update_operation()?;
    check!(
        "device-operation-excludes-installer",
        coordinator.begin_desktop_update_operation().is_err()
    );
    drop(held);
    let output = json!({"schema":"companion.desktop-update.probe.v1","result":"PASS_LOCAL_UPDATE_CONTRACT_ONLY","checkCount":checks.len(),"checks":checks,
        "payload":"public signed four-byte fixture; not an MSI", "network":"NOT_RUN","windowsInstaller":"NOT_RUN",
        "productionChannel":"BLOCKED_MISSING_PRODUCT_SIGNING_KEY_AND_USER_AUTH", "fullChain":"NOT_RUN"});
    super::super::export::write_atomic(
        &root.join("result.json"),
        &serde_json::to_vec_pretty(&output).map_err(|_| "Probe encoding failed")?,
    )?;
    Ok(output)
}
#[cfg(test)]
mod tests {
    #[test]
    fn desktop_update_signature_and_channel_contract() {
        let root = std::env::temp_dir().join(format!(
            "companion-update-{}",
            uuid::Uuid::new_v4().simple()
        ));
        assert_eq!(
            super::self_test(&root).unwrap()["result"],
            "PASS_LOCAL_UPDATE_CONTRACT_ONLY"
        );
        assert!(super::self_test(&root).is_err());
    }
}
