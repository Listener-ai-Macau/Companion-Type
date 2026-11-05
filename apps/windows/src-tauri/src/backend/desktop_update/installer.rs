//! Inspect the exact signed bytes without opening or executing an installer.
use std::io::Cursor;

pub(super) const UPGRADE_CODE: &str = "{62662888-B24B-54F1-B21F-623BE6017A26}";

pub(super) fn validate(bytes: &[u8], version: &str) -> Result<(), String> {
    let failure = || "更新安装包身份无效，原软件保持可用。".to_string();
    let expected = semver::Version::parse(version).map_err(|_| failure())?;
    if !expected.pre.is_empty()
        || !expected.build.is_empty()
        || expected.major > 255
        || expected.minor > 255
        || expected.patch > 65535
    {
        return Err(failure());
    }
    let mut package = msi::Package::open(Cursor::new(bytes)).map_err(|_| failure())?;
    if package.package_type() != msi::PackageType::Installer
        || package.summary_info().arch() != Some("x64")
    {
        return Err(failure());
    }
    for (name, expected) in [
        ("ProductName", "Companion Type"),
        ("ProductVersion", version),
        ("UpgradeCode", UPGRADE_CODE),
    ] {
        let query = msi::Select::table("Property")
            .with(msi::Expr::col("Property").eq(msi::Expr::string(name)));
        let mut rows = package.select_rows(query).map_err(|_| failure())?;
        if rows.len() != 1 {
            return Err(failure());
        }
        let row = rows.next().ok_or_else(failure)?;
        if !matches!(&row["Value"], msi::Value::Str(value) if
            if name == "UpgradeCode" { value.eq_ignore_ascii_case(expected) } else { value == expected })
        {
            return Err(failure());
        }
    }
    Ok(())
}

pub(super) fn fixture(
    name: &str,
    version: &str,
    upgrade_code: &str,
    arch: &str,
) -> Result<Vec<u8>, String> {
    let mut package = msi::Package::create(msi::PackageType::Installer, Cursor::new(Vec::new()))
        .map_err(|_| "Cannot create isolated MSI metadata fixture")?;
    package.summary_info_mut().set_arch(arch);
    package
        .create_table(
            "Property",
            vec![
                msi::Column::build("Property").primary_key().id_string(72),
                msi::Column::build("Value").nullable().formatted_string(255),
            ],
        )
        .map_err(|_| "Cannot create MSI fixture table")?;
    for (property, value) in [
        ("ProductName", name),
        ("ProductVersion", version),
        ("UpgradeCode", upgrade_code),
    ] {
        package
            .insert_rows(
                msi::Insert::into("Property")
                    .row(vec![msi::Value::from(property), msi::Value::from(value)]),
            )
            .map_err(|_| "Cannot create MSI fixture properties")?;
    }
    Ok(package
        .into_inner()
        .map_err(|_| "Cannot finalize MSI fixture")?
        .into_inner())
}
