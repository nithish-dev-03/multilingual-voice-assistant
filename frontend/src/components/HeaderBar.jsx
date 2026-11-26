import AddCommentOutlinedIcon from "@mui/icons-material/AddCommentOutlined";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import VolumeUpOutlinedIcon from "@mui/icons-material/VolumeUpOutlined";
import {
  AppBar,
  Box,
  Chip,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";

export default function HeaderBar({
  healthStatus,
  conversationId,
  generateAudio,
  onToggleGenerateAudio,
  autoPlay,
  onToggleAutoPlay,
  themeMode,
  onToggleTheme,
  onNewConversation,
  onCopyConversationId,
}) {
  const isOnline = healthStatus?.status === "ok" && healthStatus?.gemini_client_ready;

  return (
    <AppBar
      position="sticky"
      elevation={0}
      color="default"
      sx={{
        borderBottom: 1,
        borderColor: "divider",
        bgcolor: "background.paper",
      }}
    >
      <Toolbar sx={{ gap: 1.5, flexWrap: "wrap", py: 1 }}>
        <Stack direction="row" spacing={1.25} alignItems="center" sx={{ flexGrow: 1 }}>
          <Box
            sx={{
              width: 38,
              height: 38,
              borderRadius: 2,
              display: "grid",
              placeItems: "center",
              bgcolor: "primary.main",
              color: "primary.contrastText",
            }}
          >
            <GraphicEqIcon fontSize="small" />
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} lineHeight={1.2}>
              Multilingual Voice Assistant
            </Typography>
            <Typography variant="caption" color="text.secondary">
              FastAPI + Gemini Transcribe, Flash-Lite &amp; TTS
            </Typography>
          </Box>
          <Chip
            size="small"
            label={isOnline ? "Backend Online" : "Backend Offline"}
            color={isOnline ? "success" : "warning"}
            variant="outlined"
            sx={{ ml: 1 }}
          />
        </Stack>

        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          {conversationId && (
            <Tooltip title={`Session ID: ${conversationId} (click to copy)`}>
              <Chip
                size="small"
                variant="outlined"
                icon={<ContentCopyIcon fontSize="small" />}
                label={`Session: ${conversationId.slice(0, 8)}...`}
                onClick={onCopyConversationId}
              />
            </Tooltip>
          )}

          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={generateAudio}
                onChange={(e) => onToggleGenerateAudio(e.target.checked)}
              />
            }
            label={
              <Stack direction="row" spacing={0.5} alignItems="center">
                <VolumeUpOutlinedIcon fontSize="small" />
                <Typography variant="caption">TTS</Typography>
              </Stack>
            }
            sx={{ mr: 0.5 }}
          />

          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={autoPlay}
                onChange={(e) => onToggleAutoPlay(e.target.checked)}
              />
            }
            label={<Typography variant="caption">Auto-play</Typography>}
            sx={{ mr: 0.5 }}
          />

          <Tooltip title="New conversation">
            <IconButton onClick={onNewConversation} size="small" color="primary">
              <AddCommentOutlinedIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title={`Switch to ${themeMode === "dark" ? "light" : "dark"} mode`}>
            <IconButton onClick={onToggleTheme} size="small">
              {themeMode === "dark" ? <LightModeOutlinedIcon /> : <DarkModeOutlinedIcon />}
            </IconButton>
          </Tooltip>
        </Stack>
      </Toolbar>
    </AppBar>
  );
}
