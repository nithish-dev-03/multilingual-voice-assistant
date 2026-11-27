import { useEffect, useMemo, useRef, useState } from "react";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import MicIcon from "@mui/icons-material/Mic";
import SendIcon from "@mui/icons-material/Send";
import StopIcon from "@mui/icons-material/Stop";
import {
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";

import { formatDuration, startVoiceCapture } from "../utils/audioRecorder";

const LEVEL_BAR_MULTIPLIERS = [0.45, 0.75, 1.0, 0.85, 0.6, 0.9, 0.55];

export default function AudioInputBar({
  isLoading,
  onSendText,
  onSendAudio,
  onError,
}) {
  const [text, setText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [micLevel, setMicLevel] = useState(0);
  const [pendingRecording, setPendingRecording] = useState(null);

  const fileInputRef = useRef(null);
  const captureRef = useRef(null);
  const timerRef = useRef(null);

  const previewUrl = useMemo(() => {
    if (!pendingRecording?.file) {
      return null;
    }
    return URL.createObjectURL(pendingRecording.file);
  }, [pendingRecording]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const clearTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearTimer();
      captureRef.current?.cancel();
      captureRef.current = null;
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

  const handleStartRecording = async () => {
    if (isLoading || isRecording) {
      return;
    }
    setPendingRecording(null);

    try {
      const controller = await startVoiceCapture({
        onLevel: (level) => setMicLevel(level),
      });
      captureRef.current = controller;
      setIsRecording(true);
      setElapsedSeconds(0);
      setMicLevel(0);

      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      clearTimer();
      setIsRecording(false);
      setMicLevel(0);
      onError(err?.message || "Unable to access microphone. Check browser permissions.");
    }
  };

  const finishRecording = async ({ sendImmediately }) => {
    const controller = captureRef.current;
    captureRef.current = null;
    clearTimer();
    setIsRecording(false);
    setMicLevel(0);
    setElapsedSeconds(0);

    if (!controller) {
      return;
    }

    try {
      const result = await controller.stop();
      if (sendImmediately) {
        await onSendAudio(result.file);
      } else {
        setPendingRecording(result);
      }
    } catch (err) {
      onError(err?.message || "Failed to capture audio recording.");
    }
  };

  const handleCancelRecording = async () => {
    const controller = captureRef.current;
    captureRef.current = null;
    clearTimer();
    setIsRecording(false);
    setMicLevel(0);
    setElapsedSeconds(0);

    if (controller) {
      await controller.cancel();
    }
  };

  const handleSendPendingRecording = async () => {
    if (!pendingRecording?.file || isLoading) {
      return;
    }
    const fileToSend = pendingRecording.file;
    setPendingRecording(null);
    await onSendAudio(fileToSend);
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
        <Stack
          direction="row"
          spacing={1.5}
          alignItems="center"
          justifyContent="space-between"
          flexWrap="wrap"
        >
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Chip
              color="error"
              label={`Listening ${formatDuration(elapsedSeconds)}`}
              variant="filled"
            />
            <Stack
              direction="row"
              spacing={0.5}
              alignItems="center"
              sx={{ height: 28 }}
              aria-label="Microphone volume level"
            >
              {LEVEL_BAR_MULTIPLIERS.map((mult, idx) => {
                const heightPx = Math.max(6, Math.round(6 + micLevel * mult * 22));
                return (
                  <Box
                    key={idx}
                    sx={{
                      width: 4,
                      height: heightPx,
                      borderRadius: 2,
                      bgcolor: "error.main",
                      transition: "height 75ms ease-out",
                    }}
                  />
                );
              })}
            </Stack>
          </Stack>

          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="Cancel recording">
              <IconButton onClick={handleCancelRecording} color="default" aria-label="Cancel">
                <CloseIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Stop & preview recording">
              <Button
                variant="outlined"
                color="warning"
                size="small"
                startIcon={<StopIcon />}
                onClick={() => finishRecording({ sendImmediately: false })}
              >
                Preview
              </Button>
            </Tooltip>
            <Tooltip title="Stop & send voice now">
              <Button
                variant="contained"
                color="error"
                size="small"
                endIcon={<SendIcon />}
                onClick={() => finishRecording({ sendImmediately: true })}
              >
                Send Voice
              </Button>
            </Tooltip>
          </Stack>
        </Stack>
      ) : pendingRecording && previewUrl ? (
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems={{ xs: "stretch", sm: "center" }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
            Recorded ({formatDuration(pendingRecording.durationSeconds)})
          </Typography>
          <Box sx={{ flexGrow: 1 }}>
            <audio controls src={previewUrl} style={{ width: "100%", height: 36 }} />
          </Box>
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Tooltip title="Discard recording">
              <IconButton
                onClick={() => setPendingRecording(null)}
                disabled={isLoading}
                color="default"
              >
                <DeleteOutlineIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Re-record">
              <IconButton
                onClick={handleStartRecording}
                disabled={isLoading}
                color="secondary"
              >
                <MicIcon />
              </IconButton>
            </Tooltip>
            <Button
              variant="contained"
              color="primary"
              size="small"
              endIcon={<SendIcon />}
              disabled={isLoading}
              onClick={handleSendPendingRecording}
            >
              Send
            </Button>
          </Stack>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="flex-end">
          <Tooltip title="Attach audio file">
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

          <Tooltip title="Speak / record voice message">
            <span>
              <IconButton
                onClick={handleStartRecording}
                disabled={isLoading}
                color="secondary"
                aria-label="Record voice message"
              >
                <MicIcon />
              </IconButton>
            </span>
          </Tooltip>

          <TextField
            fullWidth
            multiline
            maxRows={4}
            size="small"
            placeholder="Speak with the mic, attach audio, or type in any language..."
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
