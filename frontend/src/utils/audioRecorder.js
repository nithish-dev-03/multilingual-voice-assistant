const CANDIDATE_MIME_TYPES = [
  { mimeType: "audio/webm;codecs=opus", extension: "webm" },
  { mimeType: "audio/webm", extension: "webm" },
  { mimeType: "audio/ogg;codecs=opus", extension: "ogg" },
  { mimeType: "audio/mp4", extension: "m4a" },
];

export function selectRecorderFormat() {
  if (typeof MediaRecorder === "undefined") {
    return null;
  }
  for (const candidate of CANDIDATE_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(candidate.mimeType)) {
      return candidate;
    }
  }
  return { mimeType: "", extension: "webm" };
}

export function base64ToAudioBlobUrl(base64Data, mimeType = "audio/wav") {
  const binaryString = atob(base64Data);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i += 1) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: mimeType });
  return URL.createObjectURL(blob);
}

export function formatDuration(seconds) {
  const mins = String(Math.floor(seconds / 60)).padStart(2, "0");
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}
