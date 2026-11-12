fn main() {
    let source = std::path::Path::new("../../third_party/imu-pointer/fusion/Fusion");
    let mut build = cc::Build::new();
    if build.get_compiler().is_like_msvc() {build.flag("/std:c11");}
    build.include(source).file(source.join("FusionAhrs.c"))
        .file(source.join("FusionBias.c")).file(source.join("FusionConvention.c"))
        .file("src/pointer/fusion_adapter.c").compile("companion_pointer_fusion");
    println!("cargo:rerun-if-changed={}",source.display());
    println!("cargo:rerun-if-changed=src/pointer/fusion_adapter.c");
}
