//! Prevent unmatched CLI options from falling through to automatic reconnect.

pub(crate) fn help_requested(args: &[String]) -> bool {
    args.iter().skip(1).any(|arg| matches!(arg.as_str(), "--help" | "-h"))
}

/// Called only after every supported CLI command has declined the arguments.
pub(crate) fn unhandled_option(args: &[String]) -> bool {
    args.get(1).is_some_and(|arg| arg.starts_with('-'))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(args: &[&str]) -> Vec<String> { args.iter().map(|s| (*s).into()).collect() }

    #[test]
    fn help_never_falls_through_even_with_an_operation() {
        assert!(help_requested(&a(&["type.exe", "--help"])));
        assert!(help_requested(&a(&["type.exe", "--system-ota-transfer", "file", "-h"])));
        assert!(!help_requested(&a(&["type.exe", "--system-ota-validate", "file"])));
    }

    #[test]
    fn unhandled_options_do_not_start_the_application() {
        assert!(unhandled_option(&a(&["type.exe", "--helpp"])));
        assert!(unhandled_option(&a(&["type.exe", "-z"])));
        assert!(!unhandled_option(&a(&["type.exe"])));
        assert!(!unhandled_option(&a(&["type.exe", "some-path"])));
    }
}
