const HEIC_TYPES = new Set(['image/heic', 'image/heif']);
const HEIC_EXTENSIONS = new Set(['.heic', '.heif']);
const MAX_PREVIEW_CONVERSION_BYTES = 8 * 1024 * 1024;

export function isHeicLike(file: File) {
  const mediaType = file.type.toLowerCase();
  const extension = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : '';
  return HEIC_TYPES.has(mediaType) || (!mediaType && HEIC_EXTENSIONS.has(extension));
}

export async function createHeicPreviewUrl(file: File) {
  if (!isHeicLike(file) || file.size > MAX_PREVIEW_CONVERSION_BYTES) return null;
  try {
    const { default: heic2any } = await import('heic2any');
    const converted = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.86 });
    const blob = Array.isArray(converted) ? converted[0] : converted;
    return blob ? URL.createObjectURL(blob) : null;
  } catch {
    return null;
  }
}
