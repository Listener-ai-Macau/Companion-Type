#![cfg(feature="mobile-asr")]

#[test]
fn existing_production_provider_handles_local_synthetic_network_fixtures() {
    assert_eq!(companion_mobile_audio::local_asr_probe().unwrap(),12);
}
