const TARGET_SAMPLE_RATE = 16000;

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
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const mins = String(Math.floor(safeSeconds / 60)).padStart(2, "0");
  const secs = String(safeSeconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function mergeFloat32Chunks(chunks) {
  let totalLength = 0;
  for (const chunk of chunks) {
    totalLength += chunk.length;
  }
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function downsampleBuffer(samples, inputSampleRate, targetSampleRate) {
  if (inputSampleRate <= targetSampleRate) {
    return { samples, sampleRate: inputSampleRate };
  }
  const ratio = inputSampleRate / targetSampleRate;
  const outputLength = Math.max(1, Math.round(samples.length / ratio));
  const output = new Float32Array(outputLength);

  for (let i = 0; i < outputLength; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let j = start; j < end; j += 1) {
      sum += samples[j];
      count += 1;
    }
    output[i] = count > 0 ? sum / count : samples[Math.min(start, samples.length - 1)];
  }

  return { samples: output, sampleRate: targetSampleRate };
}

function encodePcm16Wav(samples, sampleRate) {
  const dataLength = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  const writeAscii = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true); // PCM fmt chunk size
  view.setUint16(20, 1, true); // AudioFormat = 1 (PCM)
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // ByteRate = sampleRate * channels * 2
  view.setUint16(32, 2, true); // BlockAlign
  view.setUint16(34, 16, true); // BitsPerSample
  writeAscii(36, "data");
  view.setUint32(40, dataLength, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(offset, int16, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

/**
 * Start microphone voice capture using Web Audio API (encoding 16 kHz mono WAV
 * with live volume level updates), falling back to MediaRecorder if unavailable.
 */
export async function startVoiceCapture({ onLevel } = {}) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone recording is not supported in this browser.");
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (AudioCtx) {
    const audioContext = new AudioCtx();
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 64;
    const freqData = new Uint8Array(analyser.frequencyBinCount);

    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;

    const pcmChunks = [];
    processor.onaudioprocess = (event) => {
      const channelData = event.inputBuffer.getChannelData(0);
      pcmChunks.push(new Float32Array(channelData));
    };

    source.connect(analyser);
    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(audioContext.destination);

    let rafId = null;
    let closed = false;

    const pumpLevel = () => {
      if (closed) {
        return;
      }
      analyser.getByteFrequencyData(freqData);
      let sum = 0;
      for (let i = 0; i < freqData.length; i += 1) {
        sum += freqData[i];
      }
      const avg = freqData.length > 0 ? sum / (freqData.length * 255) : 0;
      onLevel?.(Math.min(1, avg * 2.2));
      rafId = requestAnimationFrame(pumpLevel);
    };
    rafId = requestAnimationFrame(pumpLevel);

    const teardown = async () => {
      if (closed) {
        return;
      }
      closed = true;
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      processor.onaudioprocess = null;
      try {
        source.disconnect();
        analyser.disconnect();
        processor.disconnect();
        silentGain.disconnect();
      } catch {
        // Ignore already-disconnected audio nodes
      }
      stream.getTracks().forEach((track) => track.stop());
      try {
        await audioContext.close();
      } catch {
        // Ignore close errors
      }
    };

    return {
      stop: async () => {
        const inputRate = audioContext.sampleRate || 48000;
        await teardown();
        const merged = mergeFloat32Chunks(pcmChunks);
        const rawDuration = merged.length / inputRate;
        if (merged.length === 0 || rawDuration < 0.25) {
          throw new Error("Recording was too short. Please speak for at least half a second.");
        }
        const { samples, sampleRate } = downsampleBuffer(
          merged,
          inputRate,
          TARGET_SAMPLE_RATE
        );
        const wavBlob = encodePcm16Wav(samples, sampleRate);
        const file = new File([wavBlob], "voice-recording.wav", { type: "audio/wav" });
        return {
          file,
          durationSeconds: samples.length / sampleRate,
        };
      },
      cancel: async () => {
        pcmChunks.length = 0;
        await teardown();
      },
    };
  }

  // Fallback for browsers without AudioContext
  const format = selectRecorderFormat();
  if (!format) {
    stream.getTracks().forEach((track) => track.stop());
    throw new Error("Microphone recording is not supported in this browser.");
  }

  const options = format.mimeType ? { mimeType: format.mimeType } : undefined;
  const recorder = new MediaRecorder(stream, options);
  const chunks = [];
  const startedAt = Date.now();

  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      chunks.push(event.data);
    }
  };

  recorder.start(250);

  return {
    stop: () =>
      new Promise((resolve, reject) => {
        recorder.onstop = () => {
          stream.getTracks().forEach((track) => track.stop());
          const durationSeconds = (Date.now() - startedAt) / 1000;
          if (chunks.length === 0 || durationSeconds < 0.25) {
            reject(new Error("Recording was too short. Please speak for at least half a second."));
            return;
          }
          const mimeType = recorder.mimeType || format.mimeType || "audio/webm";
          const ext = mimeType.includes("ogg")
            ? "ogg"
            : mimeType.includes("mp4")
              ? "m4a"
              : format.extension;
          const blob = new Blob(chunks, { type: mimeType });
          const file = new File([blob], `voice-recording.${ext}`, { type: mimeType });
          resolve({ file, durationSeconds });
        };
        recorder.stop();
      }),
    cancel: async () => {
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
      };
      if (recorder.state !== "inactive") {
        recorder.stop();
      } else {
        stream.getTracks().forEach((track) => track.stop());
      }
    },
  };
}
