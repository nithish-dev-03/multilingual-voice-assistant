import { useEffect, useRef } from "react";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import { Box, Chip, CircularProgress, Paper, Stack, Typography } from "@mui/material";

import MessageBubble from "./MessageBubble";

const SAMPLE_PROMPTS = [
  { label: "English", text: "Hello! What can you help me with today?" },
  { label: "Tamil", text: "இன்று வானிலை எப்படி இருக்கிறது?" },
  { label: "Hindi", text: "आज मौसम कैसा है?" },
  { label: "Tanglish", text: "இன்று meeting எத்தனை மணிக்கு start ஆகும்?" },
];

export default function ConversationThread({
  messages,
  isLoading,
  autoPlay,
  onSelectPrompt,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <Paper
        variant="outlined"
        sx={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          p: 4,
          gap: 2,
        }}
      >
        <GraphicEqIcon color="primary" sx={{ fontSize: 48 }} />
        <Typography variant="h6" fontWeight={700}>
          Speak or type in any language
        </Typography>
        <Typography variant="body2" color="text.secondary" maxWidth={520}>
          Record from your microphone, upload an audio file (WAV, MP3, M4A, OGG, FLAC, WebM),
          or type a message below. The assistant detects the language and replies in both text
          and synthesized speech.
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent="center" useFlexGap>
          {SAMPLE_PROMPTS.map((sample) => (
            <Chip
              key={sample.label}
              label={`${sample.label}: ${sample.text}`}
              onClick={() => onSelectPrompt(sample.text)}
              variant="outlined"
              clickable
              sx={{ my: 0.5 }}
            />
          ))}
        </Stack>
      </Paper>
    );
  }

  return (
    <Box
      sx={{
        flexGrow: 1,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 2,
        py: 1,
        pr: 0.5,
      }}
    >
      {messages.map((msg, index) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          autoPlayLatest={autoPlay && index === messages.length - 1}
        />
      ))}

      {isLoading && (
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ px: 1 }}>
          <CircularProgress size={18} />
          <Typography variant="body2" color="text.secondary">
            Processing with Gemini...
          </Typography>
        </Stack>
      )}
      <div ref={bottomRef} />
    </Box>
  );
}
