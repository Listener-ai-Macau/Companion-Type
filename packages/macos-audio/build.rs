fn main() {
    println!("cargo:rerun-if-env-changed=OPUS_LIB_DIR");
    let path = std::env::var("OPUS_LIB_DIR").expect("OPUS_LIB_DIR must name the existing static libopus directory");
    println!("cargo:rustc-link-search=native={path}");
    println!("cargo:rustc-link-lib=static=opus");
}
