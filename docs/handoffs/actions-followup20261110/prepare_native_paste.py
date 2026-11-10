from pathlib import Path
C=Path(__file__).parent
old=(C.parent/'20261109-core-acceptance/android110/NativeUiStandard110.java').read_text(encoding='utf8')
needle='else throw new IllegalArgumentException("Unsupported action");'
assert old.count(needle)==1
updated=old.replace(needle,'else if(action.equals("paste")){ok=n.performAction(AccessibilityNodeInfo.ACTION_PASTE);}\n    '+needle)
target=C/'NativeUiStandard110.java';assert not target.exists();target.write_text(updated,encoding='utf8')
print('Prepared native paste action restricted to the existing owned-display controls.')
