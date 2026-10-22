/** Client-side image helpers: previews, rotation and cropping before upload (canvas based). */

export interface PixelArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("image_decode_failed"));
    img.src = src;
  });
}

function canvasToFile(canvas: HTMLCanvasElement, name: string): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) return reject(new Error("canvas_export_failed"));
        resolve(new File([blob], name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
      },
      "image/jpeg",
      0.9,
    );
  });
}

/** Rotate by a multiple of 90° and return a new JPEG file. */
export async function rotateFile(file: File, previewUrl: string, degrees: number): Promise<File> {
  const normalized = ((degrees % 360) + 360) % 360;
  if (normalized === 0) return file;
  const img = await loadImage(previewUrl);
  const canvas = document.createElement("canvas");
  const swap = normalized === 90 || normalized === 270;
  canvas.width = swap ? img.naturalHeight : img.naturalWidth;
  canvas.height = swap ? img.naturalWidth : img.naturalHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas_unavailable");
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.rotate((normalized * Math.PI) / 180);
  ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
  return canvasToFile(canvas, file.name);
}

/** Crop `area` (pixels in the source image) from an already-rotated preview. */
export async function cropFile(file: File, previewUrl: string, area: PixelArea): Promise<File> {
  const img = await loadImage(previewUrl);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(area.width));
  canvas.height = Math.max(1, Math.round(area.height));
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas_unavailable");
  ctx.drawImage(img, area.x, area.y, area.width, area.height, 0, 0, canvas.width, canvas.height);
  return canvasToFile(canvas, file.name);
}

export function isImageFile(file: File): boolean {
  if (file.type) return file.type.startsWith("image/");
  return /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name);
}
