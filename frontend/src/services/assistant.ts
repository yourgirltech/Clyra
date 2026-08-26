const BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export type ChatRole = 'user' | 'assistant'

export type ChatHistoryMessage = {
  role: ChatRole
  content: string
}

export type AssistantToolCall = {
  tool: string
  input: Record<string, unknown>
  result: Record<string, unknown>
}

export type AssistantResponse = {
  reply: string
  tool_calls: AssistantToolCall[]
  ok: boolean
}

export async function askAssistant(message: string, history: ChatHistoryMessage[]) {
  const res = await fetch(`${BASE}/api/ai/assistant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  if (!res.ok) throw new Error('Failed to reach the AI Assistant')
  return (await res.json()) as AssistantResponse
}
