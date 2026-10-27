import QRCode from 'qrcode';

// Keep a whole, readable code on a normal desktop viewport. A long checklist
// must use the existing copy/file paths, never a silently shortened QR payload.
export const CHECKLIST_QR_MAX_BYTES = 600;
export type ChecklistPhoneCode =
  | { kind: 'ready'; text: string; dataUrl: string; pixels: number }
  | { kind: 'tooLong'; text: string };

export async function checklistPhoneCode(text: string): Promise<ChecklistPhoneCode> {
  if (!text.trim()) throw new Error('没有可带走的已保存清单。');
  if (new TextEncoder().encode(text).byteLength > CHECKLIST_QR_MAX_BYTES) {
    return { kind: 'tooLong', text };
  }
  const options = { errorCorrectionLevel: 'M' as const, margin: 4, scale: 4 };
  const code = QRCode.create(text, options);
  const pixels = (code.modules.size + 8) * 4;
  const dataUrl = await QRCode.toDataURL(text, options);
  return { kind: 'ready', text, dataUrl, pixels };
}
