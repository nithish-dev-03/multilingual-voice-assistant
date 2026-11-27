import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Container,
  CssBaseline,
  Snackbar,
  ThemeProvider,
} from "@mui/material";

import { checkHealth, sendChatMessage, sendVoiceAudio } from "./api/assistantApi";
import AudioInputBar from "./components/AudioInputBar";
import ConversationThread from "./components/ConversationThread";
import HeaderBar from "./components/HeaderBar";
import { buildTheme } from "./theme";

export default function App() {
  const [themeMode, setThemeMode] = useState("dark");
  const [healthStatus, setHealthStatus] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [generateAudio, setGenerateAudio] = useState(true);
  const [autoPlay, setAutoPlay] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [copiedNotice, setCopiedNotice] = useState(false);

  const theme = useMemo(() => buildTheme(themeMode), [themeMode]);

  useEffect(() => {
    let active = true;
    const loadHealth = async () => {
      try {
        const data = await checkHealth();
        if (active) {
          setHealthStatus(data);
        }
      } catch {
        if (active) {
          setHealthStatus(null);
        }
      }
    };
    loadHealth();
    const interval = setInterval(loadHealth, 30000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleSendText = async (text) => {
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const response = await sendChatMessage({
        message: text,
        conversationId,
        generateAudio,
      });
      setConversationId(response.conversation_id);
      const turnId = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setMessages((prev) => [
        ...prev,
        {
          id: `${turnId}-user`,
          role: "user",
          inputType: "text",
          text: response.input.message,
          languageCode: response.input.language_code,
          languageName: response.input.language_name,
        },
        {
          id: `${turnId}-assistant`,
          role: "assistant",
          text: response.assistant.text,
          audio: response.audio,
        },
      ]);
    } catch (err) {
      setErrorMessage(err?.message || "Failed to send message.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendAudio = async (audioFile) => {
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const response = await sendVoiceAudio({
        audioFile,
        conversationId,
        generateAudio,
      });
      setConversationId(response.conversation_id);
      const turnId = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setMessages((prev) => [
        ...prev,
        {
          id: `${turnId}-user`,
          role: "user",
          inputType: "audio",
          text: response.input.transcription,
          languageCode: response.input.language_code,
          languageName: response.input.language_name,
          userAudioBlob: audioFile,
        },
        {
          id: `${turnId}-assistant`,
          role: "assistant",
          text: response.assistant.text,
          audio: response.audio,
        },
      ]);
    } catch (err) {
      setErrorMessage(err?.message || "Failed to process audio.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setErrorMessage(null);
  };

  const handleCopyConversationId = async () => {
    if (!conversationId || !navigator.clipboard) {
      return;
    }
    try {
      await navigator.clipboard.writeText(conversationId);
      setCopiedNotice(true);
    } catch {
      // Ignore clipboard write restrictions
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <HeaderBar
          healthStatus={healthStatus}
          conversationId={conversationId}
          generateAudio={generateAudio}
          onToggleGenerateAudio={setGenerateAudio}
          autoPlay={autoPlay}
          onToggleAutoPlay={setAutoPlay}
          themeMode={themeMode}
          onToggleTheme={() => setThemeMode((prev) => (prev === "dark" ? "light" : "dark"))}
          onNewConversation={handleNewConversation}
          onCopyConversationId={handleCopyConversationId}
        />

        <Container
          maxWidth="md"
          sx={{
            flexGrow: 1,
            display: "flex",
            flexDirection: "column",
            gap: 2,
            py: 2.5,
            minHeight: 0,
          }}
        >
          {errorMessage && (
            <Alert severity="error" onClose={() => setErrorMessage(null)}>
              {errorMessage}
            </Alert>
          )}

          <ConversationThread
            messages={messages}
            isLoading={isLoading}
            autoPlay={autoPlay}
            onSelectPrompt={handleSendText}
          />

          <AudioInputBar
            isLoading={isLoading}
            onSendText={handleSendText}
            onSendAudio={handleSendAudio}
            onError={setErrorMessage}
          />
        </Container>

        <Snackbar
          open={copiedNotice}
          autoHideDuration={2000}
          onClose={() => setCopiedNotice(false)}
          message="Conversation ID copied"
        />
      </Box>
    </ThemeProvider>
  );
}
