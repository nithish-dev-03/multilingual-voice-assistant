import { useEffect, useRef, useState } from "react";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import CloseIcon from "@mui/icons-material/Close";
import MicIcon from "@mui/icons-material/Mic";
import SendIcon from "@mui/icons-material/Send";
import StopIcon from "@mui/icons-material/Stop";
import {
  Chip,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
} from "@mui/material";

import { formatDuration, selectRecorderFormat } from "../utils/audioRecorder";

export default function AudioInputBar({
  isLoading,
  onSendText,
  onSendAudio,
  onError,
}) {
  const [text, setText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const fileInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const cancelledRef = useRef(false);

  const cleanupRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    setIsRecording(false);
    setElapsedSeconds(0);
  };

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      cleanupRecording();
    };
  }, []);

  const handleSubmitText = async () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || isRecording) {
      return;
    }
    setText("");
    await onSendText(trimmed);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmitText();
    }
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    await onSendAudio(file);
  };

  const startRecording = async () => {
    const format = selectRecorderFormat();
    if (!format || !navigator.mediaDevices?.getUserMedia) {
      onError("Microphone recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const options = format.mimeType ? { mimeType: format.mimeType } : undefined;
      const recorder = new MediaRecorder(stream, options);

      cancelledRef.current = false;
      chunksRef.current = [];
      streamRef.current = stream;
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const shouldSend = !cancelledRef.current;
        const mimeType = recorder.mimeType || format.mimeType || "audio/webm";
        const recordedChunks = [...chunksRef.current];
        cleanupRecording();

        if (!shouldSend || recordedChunks.length === 0) {
          return;
        }
        const blob = new Blob(recordedChunks, { type: mimeType });
        const ext = mimeType.includes("ogg")
          ? "ogg"
          : mimeType.includes("mp4")
            ? "m4a"
            : format.extension;
        const audioFile = new File([blob], `recording.${ext}`, { type: mimeType });
        await onSendAudio(audioFile);
      };

      recorder.start();
      setIsRecording(true);
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      cleanupRecording();
      onError(err?.message || "Unable to access microphone. Check browser permissions.");
    }
  };

  const stopAndSendRecording = () => {
    cancelledRef.current = false;
    mediaRecorderRef.current?.stop();
  };

  const cancelRecording = () => {
    cancelledRef.current = true;
    mediaRecorderRef.current?.stop();
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        bgcolor: "background.paper",
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        hidden
        accept=".wav,.mp3,.m4a,.aac,.ogg,.oga,.opus,.flac,.webm,audio/*"
        onChange={handleFileChange}
      />

      {isRecording ? (
        <Stack direction="row" spacing={1.5} alignItems="center" justifyContent="space-between">
          <Chip
            color="error"
            label={`Recording ${formatDuration(elapsedSeconds)}`}
            variant="filled"
          />
          <Stack direction="row" spacing={1}>
            <Tooltip title="Cancel recording">
              <IconButton onClick={cancelRecording} color="default">
                <CloseIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Stop & send audio">
              <IconButton onClick={stopAndSendRecording} color="error" size="large">
                <StopIcon />
              </IconButton>
            </Tooltip>
          </Stack>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="flex-end">
          <Tooltip title="Upload audio file">
            <span>
              <IconButton
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                color="primary"
              >
                <AttachFileIcon />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Record voice message">
            <span>
              <IconButton onClick={startRecording} disabled={isLoading} color="secondary">
                <MicIcon />
              </IconButton>
            </span>
          </Tooltip>

          <TextField
            fullWidth
            multiline
            maxRows={4}
            size="small"
            placeholder="Type a message in any language (Enter to send, Shift+Enter for newline)..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />

          <Tooltip title="Send message">
            <span>
              <IconButton
                onClick={handleSubmitText}
                disabled={isLoading || !text.trim()}
                color="primary"
              >
                <SendIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      )}
    </Paper>
  );
}
