import { useEffect, useMemo, useRef } from "react";
import KeyboardOutlinedIcon from "@mui/icons-material/KeyboardOutlined";
import MicNoneOutlinedIcon from "@mui/icons-material/MicNoneOutlined";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import TranslateIcon from "@mui/icons-material/Translate";
import { Box, Chip, Paper, Stack, Typography } from "@mui/material";

import { base64ToAudioBlobUrl } from "../utils/audioRecorder";

export default function MessageBubble({ message, autoPlayLatest }) {
  const isUser = message.role === "user";
  const audioRef = useRef(null);

  const audioUrl = useMemo(() => {
    if (message.audio?.data) {
      return base64ToAudioBlobUrl(message.audio.data, message.audio.mime_type);
    }
    if (message.userAudioBlob) {
      return URL.createObjectURL(message.userAudioBlob);
    }
    return null;
  }, [message.audio, message.userAudioBlob]);

  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  useEffect(() => {
    if (!isUser && audioUrl && autoPlayLatest && audioRef.current) {
      audioRef.current.play().catch(() => {
        // Browser autoplay policies may block uninitiated playback; controls remain usable.
      });
    }
  }, [isUser, audioUrl, autoPlayLatest]);

  const languageLabel = message.languageName
    ? message.languageCode
      ? `${message.languageName} (${message.languageCode})`
      : message.languageName
    : message.languageCode || null;

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
      }}
    >
      <Paper
        elevation={0}
        variant="outlined"
        sx={{
          maxWidth: { xs: "92%", sm: "78%" },
          p: 2,
          borderColor: isUser ? "primary.main" : "divider",
          bgcolor: isUser ? "action.hover" : "background.paper",
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1 }}>
          <Chip
            size="small"
            icon={
              isUser ? (
                message.inputType === "audio" ? (
                  <MicNoneOutlinedIcon />
                ) : (
                  <KeyboardOutlinedIcon />
                )
              ) : (
                <SmartToyOutlinedIcon />
              )
            }
            label={
              isUser
                ? message.inputType === "audio"
                  ? "Voice Input"
                  : "Text Input"
                : "Assistant"
            }
            color={isUser ? "primary" : "secondary"}
            variant="outlined"
          />
          {languageLabel && (
            <Chip
              size="small"
              icon={<TranslateIcon />}
              label={languageLabel}
              variant="outlined"
            />
          )}
        </Stack>

        <Typography
          variant="body1"
          sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word", lineHeight: 1.6 }}
        >
          {message.text}
        </Typography>

        {audioUrl && (
          <Box sx={{ mt: 1.5 }}>
            <audio
              ref={audioRef}
              controls
              src={audioUrl}
              style={{ width: "100%", height: 38 }}
            />
          </Box>
        )}
      </Paper>
    </Box>
  );
}
