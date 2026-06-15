import { useState, useRef, useCallback, useEffect } from "react";

// --- Types ---

interface MediaUploadProps {
  onImagesChange: (imageUris: string[]) => void;
  onFramesChange: (frameUris: string[]) => void;
}

interface ImageFile {
  id: string;
  file: File;
  dataUri: string;
  status: "uploading" | "done" | "error";
  progress: number;
  errorMessage?: string;
}

interface VideoFile {
  id: string;
  file: File;
  status: "uploading" | "extracting" | "done" | "error";
  progress: number;
  errorMessage?: string;
}

// --- Constants ---

const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png"];
const ACCEPTED_VIDEO_TYPES = ["video/mp4", "video/webm"];
const MAX_IMAGE_SIZE_MB = 10;
const MAX_VIDEO_SIZE_MB = 50;
const MAX_VIDEO_DURATION_S = 15;
const MIN_IMAGES = 1;
const MAX_IMAGES = 5;
const MIN_FRAMES = 5;

// --- Helpers ---

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

function extractFramesFromVideo(
  file: File,
  frameCount: number = MIN_FRAMES,
): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    video.src = url;
    video.muted = true;
    video.preload = "auto";

    video.addEventListener("loadedmetadata", () => {
      const duration = video.duration;
      if (duration > MAX_VIDEO_DURATION_S) {
        URL.revokeObjectURL(url);
        reject(
          new Error(
            `Video exceeds maximum duration of ${MAX_VIDEO_DURATION_S}s (got ${duration.toFixed(1)}s)`,
          ),
        );
        return;
      }

      const timestamps: number[] = [];
      const effectiveFrameCount = Math.max(frameCount, MIN_FRAMES);
      for (let i = 0; i < effectiveFrameCount; i++) {
        timestamps.push((duration / (effectiveFrameCount + 1)) * (i + 1));
      }

      const frames: string[] = [];
      let currentIndex = 0;

      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        URL.revokeObjectURL(url);
        reject(new Error("Could not get canvas context"));
        return;
      }

      video.addEventListener("seeked", () => {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        frames.push(canvas.toDataURL("image/jpeg", 0.8));
        currentIndex++;

        if (currentIndex < timestamps.length) {
          video.currentTime = timestamps[currentIndex]!;
        } else {
          URL.revokeObjectURL(url);
          resolve(frames);
        }
      });

      video.currentTime = timestamps[0]!;
    });

    video.addEventListener("error", () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load video"));
    });
  });
}

// Simulate upload progress for demo purposes
function simulateUpload(onProgress: (progress: number) => void): Promise<void> {
  return new Promise((resolve) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 30 + 10;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        onProgress(100);
        resolve();
      } else {
        onProgress(Math.round(progress));
      }
    }, 200);
  });
}

// --- Component ---

export default function MediaUpload({
  onImagesChange,
  onFramesChange,
}: MediaUploadProps) {
  const [images, setImages] = useState<ImageFile[]>([]);
  const [video, setVideo] = useState<VideoFile | null>(null);
  const [frames, setFrames] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const imageInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);

  // Notify parent when images change
  useEffect(() => {
    const doneImages = images
      .filter((img) => img.status === "done")
      .map((img) => img.dataUri);
    onImagesChange(doneImages);
  }, [images, onImagesChange]);

  // Notify parent when frames change
  useEffect(() => {
    onFramesChange(frames);
  }, [frames, onFramesChange]);

  // --- Image handling ---

  const validateImageFile = useCallback(
    (file: File): string | null => {
      if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
        return `Invalid format: ${file.type || "unknown"}. Only JPEG and PNG are accepted.`;
      }
      if (file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024) {
        return `File too large: ${formatFileSize(file.size)}. Maximum is ${MAX_IMAGE_SIZE_MB} MB.`;
      }
      if (images.length >= MAX_IMAGES) {
        return `Maximum ${MAX_IMAGES} images allowed.`;
      }
      return null;
    },
    [images.length],
  );

  const addImageFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      const remainingSlots = MAX_IMAGES - images.length;
      if (remainingSlots <= 0) {
        setError(`Maximum ${MAX_IMAGES} images already uploaded.`);
        return;
      }

      const filesToProcess = files.slice(0, remainingSlots);
      if (files.length > remainingSlots) {
        setError(
          `Only ${remainingSlots} more image(s) can be added. Extra files were ignored.`,
        );
      }

      for (const file of filesToProcess) {
        const validationError = validateImageFile(file);
        if (validationError) {
          setError(validationError);
          continue;
        }

        const id = generateId();
        const newImage: ImageFile = {
          id,
          file,
          dataUri: "",
          status: "uploading",
          progress: 0,
        };

        setImages((prev) => [...prev, newImage]);

        try {
          // Simulate upload progress
          await simulateUpload((progress) => {
            setImages((prev) =>
              prev.map((img) => (img.id === id ? { ...img, progress } : img)),
            );
          });

          // Convert to data URI (simulates "uploaded" file)
          const dataUri = await fileToDataUri(file);

          setImages((prev) =>
            prev.map((img) =>
              img.id === id
                ? { ...img, dataUri, status: "done", progress: 100 }
                : img,
            ),
          );
        } catch {
          setImages((prev) =>
            prev.map((img) =>
              img.id === id
                ? { ...img, status: "error", errorMessage: "Upload failed" }
                : img,
            ),
          );
        }
      }
    },
    [images.length, validateImageFile],
  );

  const retryImage = useCallback(
    async (id: string) => {
      const img = images.find((i) => i.id === id);
      if (!img) return;

      setImages((prev) =>
        prev.map((i) =>
          i.id === id
            ? {
                ...i,
                status: "uploading",
                progress: 0,
                errorMessage: undefined,
              }
            : i,
        ),
      );

      try {
        await simulateUpload((progress) => {
          setImages((prev) =>
            prev.map((i) => (i.id === id ? { ...i, progress } : i)),
          );
        });

        const dataUri = await fileToDataUri(img.file);
        setImages((prev) =>
          prev.map((i) =>
            i.id === id ? { ...i, dataUri, status: "done", progress: 100 } : i,
          ),
        );
      } catch {
        setImages((prev) =>
          prev.map((i) =>
            i.id === id
              ? { ...i, status: "error", errorMessage: "Upload failed" }
              : i,
          ),
        );
      }
    },
    [images],
  );

  const removeImage = useCallback((id: string) => {
    setImages((prev) => prev.filter((img) => img.id !== id));
  }, []);

  // --- Video handling ---

  const addVideoFile = useCallback(async (file: File) => {
    setError(null);

    if (!ACCEPTED_VIDEO_TYPES.includes(file.type)) {
      setError(
        `Invalid video format: ${file.type || "unknown"}. Only MP4 and WebM are accepted.`,
      );
      return;
    }
    if (file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024) {
      setError(
        `Video too large: ${formatFileSize(file.size)}. Maximum is ${MAX_VIDEO_SIZE_MB} MB.`,
      );
      return;
    }

    const id = generateId();
    setVideo({ id, file, status: "uploading", progress: 0 });
    setFrames([]);

    try {
      // Simulate upload
      await simulateUpload((progress) => {
        setVideo((prev) => (prev ? { ...prev, progress } : null));
      });

      setVideo((prev) =>
        prev ? { ...prev, status: "extracting", progress: 100 } : null,
      );

      // Extract frames client-side
      const extractedFrames = await extractFramesFromVideo(file);
      setFrames(extractedFrames);
      setVideo((prev) => (prev ? { ...prev, status: "done" } : null));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Video processing failed";
      setVideo((prev) =>
        prev ? { ...prev, status: "error", errorMessage: message } : null,
      );
    }
  }, []);

  const retryVideo = useCallback(() => {
    if (!video) return;
    addVideoFile(video.file);
  }, [video, addVideoFile]);

  const removeVideo = useCallback(() => {
    setVideo(null);
    setFrames([]);
  }, []);

  // --- Drag and drop ---

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const files = Array.from(e.dataTransfer.files);
      const imageFiles = files.filter((f) =>
        ACCEPTED_IMAGE_TYPES.includes(f.type),
      );
      const videoFiles = files.filter((f) =>
        ACCEPTED_VIDEO_TYPES.includes(f.type),
      );

      if (imageFiles.length > 0) {
        addImageFiles(imageFiles);
      }
      if (videoFiles.length > 0 && !video) {
        addVideoFile(videoFiles[0]!);
      }
    },
    [addImageFiles, addVideoFile, video],
  );

  // --- Render ---

  const imageCount = images.length;
  const canAddMoreImages = imageCount < MAX_IMAGES;

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && (
        <div
          className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Image upload section */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          Images{" "}
          <span className="text-gray-400 font-normal">
            ({imageCount}/{MAX_IMAGES}, JPEG/PNG, max {MAX_IMAGE_SIZE_MB} MB
            each)
          </span>
        </h3>

        {/* Drop zone */}
        <div
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
            dragOver
              ? "border-blue-400 bg-blue-50"
              : canAddMoreImages
                ? "border-gray-300 hover:border-gray-400 bg-white"
                : "border-gray-200 bg-gray-50 cursor-not-allowed"
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => canAddMoreImages && imageInputRef.current?.click()}
          role="button"
          aria-label="Upload images"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              canAddMoreImages && imageInputRef.current?.click();
            }
          }}
        >
          <svg
            className="mx-auto h-10 w-10 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
          <p className="mt-2 text-sm text-gray-600">
            {canAddMoreImages
              ? "Drag & drop images here, or click to browse"
              : "Maximum images reached"}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            {MIN_IMAGES}–{MAX_IMAGES} images required
          </p>
        </div>

        <input
          ref={imageInputRef}
          type="file"
          accept=".jpg,.jpeg,.png"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              addImageFiles(Array.from(e.target.files));
              e.target.value = "";
            }
          }}
          aria-label="Select image files"
        />

        {/* Image previews */}
        {images.length > 0 && (
          <div className="mt-3 grid grid-cols-5 gap-3">
            {images.map((img) => (
              <div
                key={img.id}
                className="relative rounded-lg overflow-hidden border border-gray-200 aspect-square bg-gray-100"
              >
                {img.dataUri && (
                  <img
                    src={img.dataUri}
                    alt="Uploaded item"
                    className="w-full h-full object-cover"
                  />
                )}

                {/* Progress overlay */}
                {img.status === "uploading" && (
                  <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center">
                    <div className="w-3/4 bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-blue-500 h-1.5 rounded-full transition-all"
                        style={{ width: `${img.progress}%` }}
                      />
                    </div>
                    <span className="text-white text-xs mt-1">
                      {img.progress}%
                    </span>
                  </div>
                )}

                {/* Error overlay */}
                {img.status === "error" && (
                  <div className="absolute inset-0 bg-red-900/60 flex flex-col items-center justify-center gap-1">
                    <span className="text-white text-xs">
                      {img.errorMessage}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        retryImage(img.id);
                      }}
                      className="text-xs text-white underline hover:no-underline"
                    >
                      Retry
                    </button>
                  </div>
                )}

                {/* Remove button */}
                {img.status !== "uploading" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeImage(img.id);
                    }}
                    className="absolute top-1 right-1 bg-black/50 hover:bg-black/70 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs"
                    aria-label="Remove image"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Video upload section */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          Video{" "}
          <span className="text-gray-400 font-normal">
            (optional, max {MAX_VIDEO_DURATION_S}s, max {MAX_VIDEO_SIZE_MB} MB,
            MP4/WebM)
          </span>
        </h3>

        {!video ? (
          <button
            onClick={() => videoInputRef.current?.click()}
            className="w-full border border-gray-300 rounded-lg p-4 text-sm text-gray-600 hover:border-gray-400 hover:bg-gray-50 transition-colors"
          >
            + Add optional video
          </button>
        ) : (
          <div className="border border-gray-200 rounded-lg p-4 bg-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <svg
                  className="h-5 w-5 text-gray-400 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9.75a2.25 2.25 0 002.25-2.25V7.5a2.25 2.25 0 00-2.25-2.25H4.5A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"
                  />
                </svg>
                <span className="text-sm text-gray-700 truncate">
                  {video.file.name}
                </span>
                <span className="text-xs text-gray-400">
                  ({formatFileSize(video.file.size)})
                </span>
              </div>

              <button
                onClick={removeVideo}
                className="text-gray-400 hover:text-red-500 ml-2 flex-shrink-0"
                aria-label="Remove video"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Video status */}
            {video.status === "uploading" && (
              <div className="mt-3">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Uploading...</span>
                  <span>{video.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className="bg-blue-500 h-1.5 rounded-full transition-all"
                    style={{ width: `${video.progress}%` }}
                  />
                </div>
              </div>
            )}

            {video.status === "extracting" && (
              <div className="mt-3">
                <p className="text-xs text-blue-600 flex items-center gap-1">
                  <svg
                    className="animate-spin h-3 w-3"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Extracting frames...
                </p>
              </div>
            )}

            {video.status === "done" && (
              <p className="mt-2 text-xs text-green-600">
                ✓ {frames.length} frames extracted
              </p>
            )}

            {video.status === "error" && (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-red-600">
                  {video.errorMessage}
                </span>
                <button
                  onClick={retryVideo}
                  className="text-xs text-blue-600 underline hover:no-underline"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        )}

        <input
          ref={videoInputRef}
          type="file"
          accept=".mp4,.webm"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              addVideoFile(e.target.files[0]);
              e.target.value = "";
            }
          }}
          aria-label="Select video file"
        />

        {/* Extracted frames preview */}
        {frames.length > 0 && (
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-2">Extracted frames:</p>
            <div className="flex gap-2 overflow-x-auto pb-2">
              {frames.map((frame, i) => (
                <img
                  key={i}
                  src={frame}
                  alt={`Frame ${i + 1}`}
                  className="h-16 w-auto rounded border border-gray-200 flex-shrink-0"
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
