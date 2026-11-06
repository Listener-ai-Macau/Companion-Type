//! Product names used when the advertisement does not carry service UUIDs.
pub(crate) fn product_name(value:&str)->bool {
    let name=value.trim().to_ascii_lowercase();
    name.contains("companion")||name=="capture"||name.starts_with("capture ")||name.starts_with("capture-")
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]fn recognize_screenless_and_existing_product_names_without_service_advertisement(){
        for name in ["Capture","CAPTURE"," Capture ","Capture Alice","Capture-001","Companion","My Companion"] {assert!(product_name(name),"{name}");}
        for name in ["","Camera","Screen Capture Tool","Recapture"] {assert!(!product_name(name),"{name}");}
    }
}
