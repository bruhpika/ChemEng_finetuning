export interface SourceChunk {
  id: number;
  topic: string;
  software: string;
  url: string;
  score: number;
  content: string;
}

export interface ChatResponse {
  answer: string;
  sources_md: string;
  mode: string;
  sources: SourceChunk[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceChunk[];
  mode?: string;
  isTyping?: boolean;
}
