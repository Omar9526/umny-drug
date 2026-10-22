"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import Cropper, { type Area } from "react-easy-crop";
import {
  Camera,
  Crop,
  ImageUp,
  Keyboard,
  RotateCw,
  Send,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { FullScreenLoader } from "@/components/feedback/FullScreenLoader";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAppMeta } from "@/features/auth/useAppMeta";
import { useUploadMutation } from "@/features/assignments/api";
import { useDashboard } from "@/features/dashboard/api";
import { getErrorMessage } from "@/lib/api/client";
import { cropFile, isImageFile, rotateFile } from "@/lib/image";

interface Item {
  id: string;
  file: File;
  url: string;
  rotation: number;
}

function CaptureScreen() {
  const t = useTranslations("capture");
  const tr = useTranslations("recognize");
  const router = useRouter();
  const search = useSearchParams();
  const meta = useAppMeta();
  const upload = useUploadMutation();
  const maxImages = meta.data?.upload.max_images ?? 5;
  const maxMb = meta.data?.upload.max_image_mb ?? 10;

  const dashboard = useDashboard();
  const photoAllowed = dashboard.data?.student.allow_photo_upload ?? true;
  const [requestedMode, setMode] = useState<"photo" | "text">(
    search.get("source") === "text" ? "text" : "photo",
  );
  // Parents can switch photos off; the backend rejects photo uploads regardless of the UI.
  const mode = photoAllowed ? requestedMode : "text";
  const [items, setItems] = useState<Item[]>([]);
  const [text, setText] = useState("");
  const [cropping, setCropping] = useState<Item | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const autoOpened = useRef(false);

  useEffect(() => {
    if (autoOpened.current || mode !== "photo") return;
    autoOpened.current = true;
    const source = search.get("source");
    if (source === "camera") cameraRef.current?.click();
    if (source === "gallery") galleryRef.current?.click();
  }, [mode, search]);

  // Object URLs are revoked when an item is removed/replaced and once on unmount (not on every change).
  const itemsRef = useRef<Item[]>([]);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);
  useEffect(
    () => () => itemsRef.current.forEach((i) => URL.revokeObjectURL(i.url)),
    [],
  );

  function addFiles(list: FileList | null) {
    if (!list) return;
    const next: Item[] = [];
    for (const file of Array.from(list)) {
      if (!isImageFile(file)) {
        toast.error(t("badType"));
        continue;
      }
      if (file.size > maxMb * 1024 * 1024) {
        toast.error(t("tooLarge", { mb: maxMb }));
        continue;
      }
      next.push({
        id: `${Date.now()}-${Math.random()}`,
        file,
        url: URL.createObjectURL(file),
        rotation: 0,
      });
    }
    setItems((prev) => {
      const merged = [...prev, ...next];
      if (merged.length > maxImages)
        toast.error(t("tooMany", { max: maxImages }));
      return merged.slice(0, maxImages);
    });
  }

  function remove(id: string) {
    setItems((prev) => {
      prev
        .filter((i) => i.id === id)
        .forEach((i) => URL.revokeObjectURL(i.url));
      return prev.filter((i) => i.id !== id);
    });
  }

  function rotate(id: string) {
    setItems((prev) =>
      prev.map((i) =>
        i.id === id ? { ...i, rotation: (i.rotation + 90) % 360 } : i,
      ),
    );
  }

  async function submitPhotos() {
    if (items.length === 0) return;
    try {
      const files = await Promise.all(
        items.map((i) => rotateFile(i.file, i.url, i.rotation)),
      );
      const result = await upload.mutateAsync({
        source: search.get("source") === "gallery" ? "gallery" : "camera",
        files,
      });
      router.replace(`/assignments/uploads/${result.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function submitText() {
    if (text.trim().length < 3) return;
    try {
      const result = await upload.mutateAsync({
        source: "text",
        typedText: text.trim(),
      });
      router.replace(`/assignments/uploads/${result.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  const busy = upload.isPending;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={mode === "photo" ? t("title") : t("textTitle")}
        backHref="/home"
      />
      {!photoAllowed && (
        <p className="rounded-2xl bg-warning/10 px-4 py-3 text-sm font-semibold text-warning">
          {t("photoDisabled")}
        </p>
      )}

      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="hidden"
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/*,.heic,.heif"
        multiple
        className="hidden"
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {busy && (
        <div className="rise-in rounded-[28px] bg-lime p-6 text-center">
          <p className="text-xl font-extrabold text-teal">{tr("processing")}</p>
          <p className="mt-1 text-base text-ink/80">{tr("processingHint")}</p>
          <div className="mx-auto mt-4 h-2 w-40 overflow-hidden rounded-full bg-white/70">
            <div className="h-full w-1/2 animate-[rise-in_1.2s_ease-in-out_infinite_alternate] rounded-full bg-teal" />
          </div>
        </div>
      )}

      {mode === "photo" && !busy && (
        <>
          <p className="text-base text-muted-foreground">
            {t("hint", { max: maxImages })}
          </p>
          {items.length === 0 ? (
            <div className="flex flex-col gap-3">
              <Button
                size="xl"
                className="w-full"
                onClick={() => cameraRef.current?.click()}
              >
                <Camera /> {t("take")}
              </Button>
              <Button
                size="lg"
                variant="soft"
                className="w-full"
                onClick={() => galleryRef.current?.click()}
              >
                <ImageUp /> {t("gallery")}
              </Button>
              <Button
                size="lg"
                variant="ghost"
                className="w-full"
                onClick={() => setMode("text")}
              >
                <Keyboard /> {t("typeInstead")}
              </Button>
            </div>
          ) : (
            <>
              <ul className="grid grid-cols-2 gap-3">
                {items.map((item, index) => (
                  <li
                    key={item.id}
                    className="rise-in overflow-hidden rounded-3xl bg-white shadow-card ring-1 ring-line"
                  >
                    <div className="relative aspect-[3/4] overflow-hidden bg-muted">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={item.url}
                        alt={`${index + 1}`}
                        className="size-full object-contain transition-transform"
                        style={{ transform: `rotate(${item.rotation}deg)` }}
                      />
                      <span className="absolute top-2 left-2 rounded-full bg-teal px-2 py-0.5 text-xs font-bold text-white">
                        {index + 1}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 divide-x divide-line">
                      <button
                        type="button"
                        onClick={() => rotate(item.id)}
                        className="tap-target flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold text-teal"
                      >
                        <RotateCw className="size-4" /> {t("rotate")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setCropping(item)}
                        className="tap-target flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold text-teal"
                      >
                        <Crop className="size-4" /> {t("crop")}
                      </button>
                      <button
                        type="button"
                        onClick={() => remove(item.id)}
                        className="tap-target flex flex-col items-center gap-0.5 py-2 text-[11px] font-semibold text-destructive"
                      >
                        <Trash2 className="size-4" /> {t("remove")}
                      </button>
                    </div>
                  </li>
                ))}
                {items.length < maxImages && (
                  <li>
                    <button
                      type="button"
                      onClick={() => cameraRef.current?.click()}
                      className="flex aspect-[3/4] w-full flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-line bg-white/60 text-teal"
                    >
                      <Camera className="size-7" />
                      <span className="text-sm font-semibold">
                        {t("addMore")}
                      </span>
                    </button>
                  </li>
                )}
              </ul>
              <Button size="xl" className="w-full" onClick={submitPhotos}>
                <Send /> {t("recognize")}
              </Button>
            </>
          )}
        </>
      )}

      {mode === "text" && !busy && (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void submitText();
          }}
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={7}
            autoFocus
            placeholder={t("textPlaceholder")}
            className="w-full resize-y rounded-3xl border border-line bg-white px-4 py-3 text-base outline-none focus-visible:ring-4 focus-visible:ring-teal/20"
          />
          <p className="text-sm text-muted-foreground">{t("textHint")}</p>
          <Button
            type="submit"
            size="xl"
            className="w-full"
            disabled={text.trim().length < 3}
          >
            <Send /> {t("send")}
          </Button>
          {photoAllowed && (
            <Button
              type="button"
              variant="ghost"
              size="lg"
              onClick={() => setMode("photo")}
            >
              <Camera /> {t("photoInstead")}
            </Button>
          )}
        </form>
      )}

      {cropping && (
        <CropOverlay
          item={cropping}
          onCancel={() => setCropping(null)}
          onApply={async (area) => {
            try {
              const rotated = await rotateFile(
                cropping.file,
                cropping.url,
                cropping.rotation,
              );
              const rotatedUrl = URL.createObjectURL(rotated);
              const file = await cropFile(rotated, rotatedUrl, area);
              URL.revokeObjectURL(rotatedUrl);
              const url = URL.createObjectURL(file);
              setItems((prev) =>
                prev.map((i) => {
                  if (i.id !== cropping.id) return i;
                  URL.revokeObjectURL(i.url);
                  return { ...i, file, url, rotation: 0 };
                }),
              );
            } catch (error) {
              toast.error(getErrorMessage(error));
            } finally {
              setCropping(null);
            }
          }}
        />
      )}
    </div>
  );
}

function CropOverlay({
  item,
  onCancel,
  onApply,
}: {
  item: Item;
  onCancel: () => void;
  onApply: (area: Area) => void;
}) {
  const t = useTranslations("capture");
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState<Area | null>(null);
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-ink"
      role="dialog"
      aria-modal="true"
      aria-label={t("cropTitle")}
    >
      <div className="relative flex-1">
        <Cropper
          image={item.url}
          crop={crop}
          zoom={zoom}
          rotation={item.rotation}
          aspect={undefined}
          onCropChange={setCrop}
          onZoomChange={setZoom}
          onCropComplete={(_, pixels) => setArea(pixels)}
          showGrid
        />
      </div>
      <div className="safe-bottom flex items-center gap-3 bg-ink px-4 py-3">
        <p className="flex-1 text-base font-semibold text-white">
          {t("cropTitle")}
        </p>
        <Button
          variant="ghost"
          className="text-white hover:bg-white/10"
          onClick={onCancel}
        >
          {t("cropCancel")}
        </Button>
        <Button
          variant="lime"
          onClick={() => area && onApply(area)}
          disabled={!area}
        >
          {t("cropApply")}
        </Button>
      </div>
    </div>
  );
}

export default function NewAssignmentPage() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <CaptureScreen />
    </Suspense>
  );
}
