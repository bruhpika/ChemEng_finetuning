"use client";

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Settings, BookOpen, Trash2, ChevronDown, ChevronUp, ExternalLink, Bot, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ChatMessage, ChatResponse, SourceChunk } from '@/types';

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'assistant',
    content: "Welcome to ChemE-LLM!\n\nI am an AI assistant specifically designed to help you with DWSIM and MATLAB chemical engineering simulations.\n\nType your question below to get started, or ask one of the examples like 'How do I configure a Flash Drum in DWSIM?'\n\n— Created by Harshith Bhardwazz",
  }]);
  const [inputValue, setInputValue] = useState('');
  const [software, setSoftware] = useState('Both');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage.content,
          software: software
        }),
      });

      if (!response.ok) throw new Error('Failed to fetch response');

      const data: ChatResponse = await response.json();
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        mode: data.mode
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error:", error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "Sorry, I encountered an error while trying to reach the server. Please make sure the FastAPI backend is running.",
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const clearChat = () => {
    setMessages([{
      id: 'welcome',
      role: 'assistant',
      content: "Chat cleared. What else would you like to know?",
    }]);
  };

  const setExample = (text: string, sw: string) => {
    setInputValue(text);
    setSoftware(sw);
  };

  return (
    <div className="flex flex-col h-screen bg-[#131314] text-[#e3e3e3] font-sans selection:bg-indigo-500/30">
      
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#131314]/80 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4b90ff] to-[#ff5546] flex items-center justify-center shadow-lg">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-medium bg-gradient-to-r from-[#4b90ff] to-[#ff5546] bg-clip-text text-transparent">ChemE-LLM</h1>
            <p className="text-xs text-[#a8c7fa]">AI for DWSIM & MATLAB</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <select 
            value={software}
            onChange={(e) => setSoftware(e.target.value)}
            className="bg-[#1e1e20] border border-white/10 rounded-full px-4 py-1.5 text-sm focus:outline-none focus:border-[#4b90ff] transition-colors"
          >
            <option value="Both">All Software</option>
            <option value="DWSIM">DWSIM</option>
            <option value="MATLAB">MATLAB</option>
          </select>
          <button onClick={clearChat} className="p-2 hover:bg-white/5 rounded-full transition-colors text-white/60 hover:text-white" title="Clear chat">
            <Trash2 size={18} />
          </button>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 md:p-8 flex flex-col items-center">
        <div className="w-full max-w-4xl flex flex-col gap-8 pb-32">
          
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className={`flex gap-4 md:gap-6 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
              >
                <div className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center mt-1 ${
                  msg.role === 'user' ? 'bg-[#1e1e20] border border-white/10' : 'bg-gradient-to-br from-[#4b90ff] to-[#ff5546]'
                }`}>
                  {msg.role === 'user' ? <User size={18} className="text-white/80" /> : <Bot size={18} className="text-white" />}
                </div>

                <div className={`flex flex-col gap-2 max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`px-5 py-4 rounded-2xl ${
                    msg.role === 'user' 
                      ? 'bg-[#1e1e20] border border-white/5 rounded-tr-sm text-white/90' 
                      : 'bg-transparent text-white/90 prose prose-invert max-w-none prose-p:leading-relaxed'
                  }`}>
                    {msg.role === 'user' ? (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    ) : (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    )}
                  </div>

                  {msg.mode && (
                    <span className="text-[11px] text-[#4b90ff] px-2 py-0.5 rounded-full border border-[#4b90ff]/20 bg-[#4b90ff]/5">
                      {msg.mode}
                    </span>
                  )}

                  {msg.sources && msg.sources.length > 0 && (
                    <SourceAccordion sources={msg.sources} />
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-4 md:gap-6"
            >
              <div className="w-8 h-8 shrink-0 rounded-full bg-gradient-to-br from-[#4b90ff] to-[#ff5546] flex items-center justify-center mt-1">
                <Bot size={18} className="text-white animate-pulse" />
              </div>
              <div className="flex gap-1.5 items-center mt-4">
                <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1 }} className="w-2 h-2 rounded-full bg-[#4b90ff]/50" />
                <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }} className="w-2 h-2 rounded-full bg-[#ff5546]/50" />
                <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }} className="w-2 h-2 rounded-full bg-[#4b90ff]/50" />
              </div>
            </motion.div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-[#131314] via-[#131314] to-transparent pt-10 pb-6 px-4 md:px-8 flex flex-col items-center">
        
        {messages.length === 1 && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap justify-center gap-2 mb-4 max-w-3xl"
          >
            {examples.map((ex, i) => (
              <button 
                key={i}
                onClick={() => setExample(ex.text, ex.sw)}
                className="text-xs bg-[#1e1e20] hover:bg-[#28282a] border border-white/5 rounded-full px-4 py-2 transition-colors text-white/70"
              >
                {ex.text}
              </button>
            ))}
          </motion.div>
        )}

        <div className="w-full max-w-4xl relative">
          <form onSubmit={handleSubmit} className="relative flex items-end bg-[#1e1e20] rounded-3xl border border-white/10 focus-within:border-white/20 transition-colors shadow-2xl overflow-hidden">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask ChemE-LLM anything..."
              className="w-full bg-transparent text-[#e3e3e3] px-6 py-5 outline-none resize-none min-h-[64px] max-h-48 scrollbar-thin"
              rows={1}
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="absolute right-3 bottom-3 p-2.5 rounded-full bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-white/5 transition-colors text-white"
            >
              <Send size={20} />
            </button>
          </form>
          <div className="text-center mt-3">
            <span className="text-[10px] text-white/40">ChemE-LLM can make mistakes. Consider verifying critical simulation parameters.</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Subcomponents

const SourceAccordion = ({ sources }: { sources: SourceChunk[] }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-2 w-full border border-white/10 rounded-xl overflow-hidden bg-black/20 backdrop-blur-sm">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors text-sm text-white/80"
      >
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-[#a8c7fa]" />
          <span>Show {sources.length} sources used</span>
        </div>
        {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 flex flex-col gap-3">
              {sources.map((src, i) => (
                <div key={i} className="p-3 bg-white/5 rounded-lg border border-white/5 text-sm">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <h4 className="font-medium text-white/90 flex items-center gap-2">
                      <span className="text-xs bg-white/10 px-1.5 py-0.5 rounded text-white/60">[{src.id}]</span>
                      {src.topic}
                      <span className="text-xs text-white/40 font-normal border border-white/10 px-1.5 py-0.5 rounded-full">{src.software}</span>
                    </h4>
                    <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-[#4b90ff] hover:underline flex items-center gap-1 shrink-0">
                      <span className="text-xs hidden sm:inline">Source</span>
                      <ExternalLink size={12} />
                    </a>
                  </div>
                  <div className="text-xs text-white/60 max-h-32 overflow-y-auto pr-2 custom-scrollbar whitespace-pre-wrap">
                    {src.content}
                  </div>
                  <div className="mt-2 text-[10px] text-white/40">
                    Relevance Score: {src.score.toFixed(4)}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const examples = [
  { text: "How do I configure a Flash Drum?", sw: "DWSIM" },
  { text: "Difference between ode45 and ode15s?", sw: "MATLAB" },
  { text: "How to fix convergence error?", sw: "DWSIM" },
];
