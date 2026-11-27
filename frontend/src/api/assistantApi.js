const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function parseErrorResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // Non-JSON response body
  }

  if (payload?.error?.message) {
    const code = payload.error.code ? `[${payload.error.code}] ` : "";
    return `${code}${payload.error.message}`;
  }
  if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
    return payload.detail.map((item) => item.msg).join("; ");
  }
  return `Request failed with status ${response.status}`;
}

export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }
  return response.json();
}

export async function sendChatMessage({ message, conversationId, generateAudio }) {
  const response = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || null,
      generate_audio: generateAudio,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }
  return response.json();
}

export async function sendVoiceAudio({ audioFile, conversationId, generateAudio = true }) {
  const formData = new FormData();
  formData.append("audio", audioFile);
  formData.append("generate_audio", String(Boolean(generateAudio)));
  if (conversationId) {
    formData.append("conversation_id", conversationId);
  }

  const response = await fetch(`${API_BASE}/api/v1/voice`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }
  return response.json();
}
