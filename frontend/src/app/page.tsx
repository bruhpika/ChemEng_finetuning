"use client";

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Send, Settings, BookOpen, Trash2, ChevronDown, ChevronUp, 
  ExternalLink, Bot, User, Plus, Search, Image as ImageIcon, 
  Video, Library, Gem, MessageSquare, Clock, PanelLeft, 
  Mic, Sparkles, Terminal, Cpu, FolderOpen, ArrowUp, Share2, Award
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ChatMessage, ChatResponse, SourceChunk } from '@/types';

// Custom GitHub SVG Icon
const GitHubIcon = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"></path>
    <path d="M9 18c-4.51 2-5-2-7-2"></path>
  </svg>
);

// ── Model Loading Overlay ──────────────────────────────────────────────────────

const CHEM_TIPS = [
  "DWSIM uses the NRTL activity coefficient model for non-ideal liquid mixtures.",
  "Phi-3-mini has 3.8 billion parameters — optimized for constrained environments.",
  "RAG (Retrieval-Augmented Generation) grounds answers in real knowledge base data.",
  "Flash drums separate vapor-liquid mixtures using pressure and temperature changes.",
  "MATLAB's ode45 uses a 4th/5th-order Runge-Kutta adaptive step method.",
  "ChromaDB stores vector embeddings for fast semantic search over your knowledge base.",
  "LoRA fine-tuning only trains a small fraction of parameters, saving GPU memory.",
  "Distillation columns in DWSIM can model up to 500 theoretical stages.",
];

const STAGES = [
  { key: "loading_retriever", label: "Loading Knowledge Base", sublabel: "Connecting ChromaDB vector store…", icon: "🧠" },
  { key: "loading_model",     label: "Loading Language Model",  sublabel: "Initialising Phi-3-mini weights…",   icon: "🤖" },
  { key: "done",              label: "Almost Ready",            sublabel: "Finalising inference pipeline…",      icon: "⚡" },
];

const ModelLoadingOverlay = ({
  loadingStep,
  retrieverReady,
  modelReady,
}: {
  loadingStep: string;
  retrieverReady: boolean;
  modelReady: boolean;
}) => {
  const [tipIndex, setTipIndex] = useState(0);
  const [tipVisible, setTipVisible] = useState(true);

  // Cycle tips every 4 seconds
  useEffect(() => {
    const iv = setInterval(() => {
      setTipVisible(false);
      setTimeout(() => {
        setTipIndex((i) => (i + 1) % CHEM_TIPS.length);
        setTipVisible(true);
      }, 400);
    }, 4000);
    return () => clearInterval(iv);
  }, []);

  // Progress percentage
  const progress =
    modelReady     ? 100 :
    retrieverReady ? 60  :
    loadingStep === "loading_retriever" ? 20 :
    loadingStep === "loading_model"     ? 60 : 5;

  const currentStageIndex =
    modelReady     ? 2 :
    retrieverReady ? 1 :
    loadingStep === "loading_retriever" ? 0 : 0;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 1.04 }}
      transition={{ duration: 0.5, ease: "easeInOut" }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#0d0d0e]/95 backdrop-blur-2xl"
    >
      {/* Animated background orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.15, 0.25, 0.15] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-violet-600/20 blur-[120px]"
        />
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.10, 0.20, 0.10] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-indigo-500/20 blur-[100px]"
        />
        <motion.div
          animate={{ scale: [1, 1.1, 1], opacity: [0.08, 0.15, 0.08] }}
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-fuchsia-500/10 blur-[150px]"
        />
      </div>

      <div className="relative flex flex-col items-center gap-10 max-w-lg w-full px-8 text-center">

        {/* Logo + title */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="flex flex-col items-center gap-4"
        >
          <div className="relative w-20 h-20">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-500 border-r-indigo-400"
            />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
              className="absolute inset-2 rounded-full border-2 border-transparent border-t-fuchsia-400 border-b-pink-400"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-3xl">⚗️</span>
            </div>
          </div>

          <div>
            <h1 className="text-3xl font-semibold bg-gradient-to-r from-violet-400 via-indigo-300 to-pink-400 bg-clip-text text-transparent tracking-tight">
              ChemE-LLM
            </h1>
            <p className="text-sm text-white/40 mt-1">Initialising your engineering AI…</p>
          </div>
        </motion.div>

        {/* Progress bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="w-full flex flex-col gap-2"
        >
          <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 via-indigo-400 to-fuchsia-400"
              initial={{ width: "5%" }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 1.2, ease: "easeOut" }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-white/30">
            <span>Starting up</span>
            <span>{progress}%</span>
          </div>
        </motion.div>

        {/* Stage indicators */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="w-full flex flex-col gap-3"
        >
          {STAGES.map((stage, i) => {
            const isDone   = i < currentStageIndex || modelReady;
            const isActive = i === currentStageIndex && !modelReady;
            return (
              <div
                key={stage.key}
                className={`flex items-center gap-4 px-4 py-3 rounded-xl border transition-all duration-500 ${
                  isDone
                    ? "bg-emerald-500/10 border-emerald-500/25 text-emerald-300"
                    : isActive
                    ? "bg-violet-500/10 border-violet-500/30 text-violet-200"
                    : "bg-white/3 border-white/5 text-white/30"
                }`}
              >
                <span className="text-xl">{stage.icon}</span>
                <div className="flex-1 text-left">
                  <div className="text-sm font-medium">{stage.label}</div>
                  <div className="text-xs opacity-60">{stage.sublabel}</div>
                </div>
                <div className="shrink-0">
                  {isDone ? (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="text-emerald-400 text-lg"
                    >✓</motion.span>
                  ) : isActive ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="w-4 h-4 border-2 border-violet-400/60 border-t-violet-400 rounded-full"
                    />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-white/10" />
                  )}
                </div>
              </div>
            );
          })}
        </motion.div>

        {/* Rotating fun-facts tip */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="w-full bg-white/3 border border-white/8 rounded-2xl px-5 py-4 min-h-[72px] flex items-center justify-center"
        >
          <AnimatePresence mode="wait">
            {tipVisible && (
              <motion.p
                key={tipIndex}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.35 }}
                className="text-xs text-white/50 leading-relaxed"
              >
                <span className="text-violet-400 font-medium">Did you know? </span>
                {CHEM_TIPS[tipIndex]}
              </motion.p>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Bottom caption */}
        <p className="text-[11px] text-white/20">
          Large language models take a moment to initialise. Hang tight!
        </p>
      </div>
    </motion.div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────

// Cursor Follow Color Gradient Animation Component
const CursorGlow = () => {
  const [mousePosition, setMousePosition] = useState({ x: -1000, y: -1000 });
  
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <motion.div
        className="absolute w-[550px] h-[550px] rounded-full bg-gradient-to-r from-violet-600/25 via-fuchsia-500/20 to-cyan-500/25 blur-[110px] -translate-x-1/2 -translate-y-1/2"
        animate={{
          x: mousePosition.x,
          y: mousePosition.y,
        }}
        transition={{
          type: "spring",
          damping: 30,
          stiffness: 200,
          mass: 0.5,
        }}
      />
      <motion.div
        className="absolute w-[750px] h-[750px] rounded-full bg-gradient-to-br from-blue-600/15 via-indigo-600/15 to-purple-600/15 blur-[150px] -translate-x-1/2 -translate-y-1/2"
        animate={{
          x: mousePosition.x,
          y: mousePosition.y,
        }}
        transition={{
          type: "spring",
          damping: 45,
          stiffness: 150,
          mass: 0.8,
        }}
      />
    </div>
  );
};

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'assistant',
    content: "Welcome to **ChemE-LLM** integrated with Gemini AI aesthetics!\n\nI am designed to assist you with DWSIM and MATLAB chemical engineering simulations.\n\nType your question below or pick a simulation prompt to begin.\n\n— *Developed by Harshith Bhardwaz*",
  }]);
  const [inputValue, setInputValue] = useState('');
  const [software, setSoftware] = useState('Both');
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [backendStatus, setBackendStatus] = useState<"loading" | "ready" | "fallback">("loading");
  const [loadingStep, setLoadingStep] = useState<"idle" | "loading_retriever" | "loading_model" | "done">("idle");
  const [retrieverReady, setRetrieverReady] = useState(false);
  const [modelReady, setModelReady] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/status");
        if (res.ok) {
          const data = await res.json();
          setBackendStatus(data.status);
          setLoadingStep(data.loading_step ?? "idle");
          setRetrieverReady(data.retriever_ready ?? false);
          setModelReady(data.model_ready ?? false);
        } else {
          setBackendStatus("loading");
        }
      } catch (err) {
        console.error("Error polling backend status:", err);
        setBackendStatus("loading");
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputValue.trim() || isLoading || backendStatus === "loading") return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: inputValue.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 30000);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMessage.content,
          software: software
        }),
        signal: abortController.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) throw new Error('Failed to fetch response');

      const data: ChatResponse = await response.json();
      
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        mode: data.mode
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error:", error);
      const isTimeout = error instanceof Error && error.name === 'AbortError';
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: isTimeout 
          ? "Request timed out. The server took too long to respond."
          : "Sorry, I encountered an error while trying to reach the server. Please make sure the FastAPI backend is running.",
      }]);
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (backendStatus !== "loading") {
        handleSubmit();
      }
    }
  };

  const clearChat = () => {
    setMessages([{
      id: 'welcome',
      role: 'assistant',
      content: "Chat cleared. What else would you like to explore?",
    }]);
  };

  const setExample = (text: string, sw: string) => {
    setInputValue(text);
    setSoftware(sw);
  };

  const isInitialState = messages.length === 1 && messages[0].id === 'welcome';

  return (
    <div className="flex h-screen bg-[#131314] text-[#e3e3e3] font-sans overflow-hidden selection:bg-indigo-500/30 relative">
      {/* Interactive Cursor Color Gradient Animation */}
      <CursorGlow />

      {/* Model Loading Overlay */}
      <AnimatePresence>
        {backendStatus === "loading" && (
          <ModelLoadingOverlay
            loadingStep={loadingStep}
            retrieverReady={retrieverReady}
            modelReady={modelReady}
          />
        )}
      </AnimatePresence>

      {/* Gemini Left Sidebar */}
      <motion.aside 
        initial={false}
        animate={{ width: isSidebarOpen ? 280 : 0, opacity: isSidebarOpen ? 1 : 0 }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className="h-full bg-[#1e1f20]/90 border-r border-white/5 flex flex-col z-20 shrink-0 overflow-hidden backdrop-blur-md"
      >
        <div className="p-4 flex flex-col h-full justify-between min-w-[280px]">
          {/* Top Section */}
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between px-2">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-violet-600 via-indigo-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                  <Sparkles size={18} className="text-white animate-pulse" />
                </div>
                <span className="text-lg font-medium tracking-wide bg-gradient-to-r from-white via-white/90 to-white/70 bg-clip-text text-transparent">Gemini</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">ChemE</span>
              </div>
              <button 
                onClick={() => setIsSidebarOpen(false)}
                className="p-2 hover:bg-white/5 rounded-full transition-colors text-white/60 hover:text-white"
                title="Collapse sidebar"
              >
                <PanelLeft size={18} />
              </button>
            </div>

            {/* New Chat Button */}
            <button 
              onClick={clearChat}
              className="flex items-center gap-3 px-4 py-3 rounded-full bg-[#131314] hover:bg-[#282a2c] border border-white/10 text-sm font-medium text-white/90 shadow-sm transition-all group"
            >
              <Plus size={18} className="text-violet-400 group-hover:rotate-90 transition-transform duration-300" />
              <span>New chat</span>
            </button>

            {/* Navigation Menu */}
            <nav className="flex flex-col gap-1 text-sm text-white/70">
              <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors">
                <Search size={18} className="text-white/50" />
                <span>Search chats</span>
              </a>
              <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors">
                <ImageIcon size={18} className="text-white/50" />
                <span>Images</span>
              </a>
              <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors">
                <Video size={18} className="text-white/50" />
                <span>Videos</span>
              </a>
              <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors">
                <Library size={18} className="text-white/50" />
                <span>Library</span>
              </a>
              <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors">
                <Gem size={18} className="text-white/50" />
                <span>Gems</span>
              </a>
            </nav>

            {/* Notebooks Section */}
            <div className="flex flex-col gap-2 pt-2 border-t border-white/5">
              <span className="text-xs font-semibold text-white/40 px-3 uppercase tracking-wider">Notebooks</span>
              <div className="flex flex-col gap-1 text-sm text-white/70">
                <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors text-violet-400 font-medium">
                  <Plus size={16} />
                  <span>New notebook</span>
                </a>
                <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors">
                  <Terminal size={16} className="text-white/40" />
                  <span>master prompter</span>
                </a>
                <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors">
                  <Cpu size={16} className="text-white/40" />
                  <span>Pybamm</span>
                </a>
                <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors text-xs text-white/50">
                  <FolderOpen size={16} className="text-white/40" />
                  <span>All notebooks</span>
                </a>
              </div>
            </div>

            {/* Recent Chats Section */}
            <div className="flex flex-col gap-2 pt-2 border-t border-white/5 overflow-y-auto max-h-[160px] custom-scrollbar">
              <span className="text-xs font-semibold text-white/40 px-3 uppercase tracking-wider">Recent</span>
              <div className="flex flex-col gap-1 text-xs text-white/70">
                <button onClick={() => setExample("Configure Flash Drum in DWSIM", "DWSIM")} className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors text-left truncate">
                  <MessageSquare size={14} className="text-white/40 shrink-0" />
                  <span className="truncate">Flash Drum Configuration</span>
                </button>
                <button onClick={() => setExample("Difference between ode45 and ode15s?", "MATLAB")} className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors text-left truncate">
                  <MessageSquare size={14} className="text-white/40 shrink-0" />
                  <span className="truncate">MATLAB ODE Solvers</span>
                </button>
                <button onClick={() => setExample("How to fix convergence error?", "DWSIM")} className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors text-left truncate">
                  <MessageSquare size={14} className="text-white/40 shrink-0" />
                  <span className="truncate">Convergence Error Fixes</span>
                </button>
              </div>
            </div>
          </div>

          {/* Bottom Profile Section */}
          <div className="pt-4 border-t border-white/5 flex items-center justify-between px-2">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-amber-500 via-rose-500 to-indigo-500 flex items-center justify-center font-bold text-white text-xs shadow-md shrink-0">
                HB
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="text-sm font-medium text-white truncate">Harshith Bhardwaz Kenkary</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-gradient-to-r from-violet-500 to-indigo-500 text-white">Pro</span>
                  <span className="text-[11px] text-white/40 truncate">Author</span>
                </div>
              </div>
            </div>
            <button className="p-2 hover:bg-white/5 rounded-full text-white/60 hover:text-white shrink-0">
              <Settings size={18} />
            </button>
          </div>
        </div>
      </motion.aside>

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col h-full relative z-10 overflow-hidden">
        
        {/* Top Navbar */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#131314]/60 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            {!isSidebarOpen && (
              <button 
                onClick={() => setIsSidebarOpen(true)}
                className="p-2 hover:bg-white/5 rounded-full transition-colors text-white/60 hover:text-white mr-1"
                title="Expand sidebar"
              >
                <PanelLeft size={18} />
              </button>
            )}
            <div className="flex items-center gap-2">
              <select 
                value={software}
                onChange={(e) => setSoftware(e.target.value)}
                className="bg-[#1e1f20] border border-white/10 rounded-full px-4 py-1.5 text-xs md:text-sm font-medium focus:outline-none focus:border-violet-500 text-white/80 transition-colors cursor-pointer shadow-sm"
              >
                <option value="Both">Pro v (All Software)</option>
                <option value="DWSIM">DWSIM Model v</option>
                <option value="MATLAB">MATLAB Engine v</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Contribute Button with GitHub Link */}
            <a 
              href="https://github.com/bruhpika/ChemEng_finetuning-main"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs md:text-sm font-medium text-white transition-all hover:scale-105 hover:border-white/20 shadow-sm"
            >
              <GitHubIcon className="w-4 h-4 text-violet-400" />
              <span>Contribute</span>
            </a>

            {/* Credits / Portfolio Button */}
            <a 
              href="https://harshithport.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-gradient-to-r from-violet-600/20 to-pink-600/20 hover:from-violet-600/30 hover:to-pink-600/30 border border-violet-500/30 text-xs md:text-sm font-medium text-violet-200 transition-all hover:scale-105 shadow-sm"
            >
              <Award size={15} className="text-pink-400" />
              <span className="hidden sm:inline">Author:</span> Harshith Bhardwaz
            </a>

            {/* Clear Chat */}
            <button onClick={clearChat} className="p-2 hover:bg-white/5 rounded-full transition-colors text-white/60 hover:text-white" title="Clear chat">
              <Trash2 size={18} />
            </button>
          </div>
        </header>


        {backendStatus === "fallback" && (
          <div className="bg-blue-500/10 border-b border-blue-500/20 px-6 py-3 text-xs md:text-sm text-blue-200 flex items-center gap-3">
            <span className="flex h-2 w-2 relative">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            <span>RAG-only fallback mode active. Answers will be based directly on matching knowledge base documents without LLM generation.</span>
          </div>
        )}

        {/* Main Content / Chat Body */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8 flex flex-col items-center">
          
          {isInitialState ? (
            /* Gemini Greeting State */
            <div className="flex-1 flex flex-col items-center justify-center max-w-3xl w-full text-center px-4 my-auto">
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="mb-8"
              >
                <h1 className="text-3xl md:text-5xl lg:text-6xl font-medium tracking-tight bg-gradient-to-r from-violet-400 via-indigo-200 to-pink-400 bg-clip-text text-transparent pb-2">
                  Hi Harshith Bhardwaz, what&apos;s the plan?
                </h1>
                <p className="text-sm md:text-base text-white/50 mt-3 max-w-xl mx-auto">
                  Your specialized engineering AI ready for DWSIM simulation modeling and MATLAB numerical analysis.
                </p>
              </motion.div>

              {/* Example Suggestion Cards */}
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full max-w-2xl"
              >
                {examples.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => setExample(ex.text, ex.sw)}
                    className="p-4 rounded-2xl bg-[#1e1f20]/60 hover:bg-[#282a2c]/80 border border-white/5 hover:border-violet-500/30 transition-all text-left flex flex-col justify-between h-28 group shadow-lg backdrop-blur-sm"
                  >
                    <span className="text-xs font-medium text-white/80 group-hover:text-white line-clamp-2">{ex.text}</span>
                    <span className="text-[10px] font-bold text-violet-400 mt-2 flex items-center gap-1 self-end">
                      {ex.sw} <ArrowUp size={12} className="rotate-45" />
                    </span>
                  </button>
                ))}
              </motion.div>
            </div>
          ) : (
            /* Chat Messages List */
            <div className="w-full max-w-4xl flex flex-col gap-8 pb-36">
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <MessageItem key={msg.id} msg={msg} />
                ))}
              </AnimatePresence>

              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-4 md:gap-6"
                >
                  <div className="w-8 h-8 shrink-0 rounded-full bg-gradient-to-tr from-violet-600 via-indigo-500 to-pink-500 flex items-center justify-center mt-1 shadow-md">
                    <Sparkles size={18} className="text-white animate-spin" />
                  </div>
                  <div className="flex gap-1.5 items-center mt-4">
                    <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ repeat: Infinity, duration: 1 }} className="w-2.5 h-2.5 rounded-full bg-violet-400" />
                    <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }} className="w-2.5 h-2.5 rounded-full bg-indigo-400" />
                    <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }} className="w-2.5 h-2.5 rounded-full bg-pink-400" />
                  </div>
                </motion.div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>

        {/* Gemini Bottom Prompt Input Bar */}
        <div className="p-4 md:p-6 bg-gradient-to-t from-[#131314] via-[#131314]/90 to-transparent flex flex-col items-center shrink-0 z-20">
          <div className="w-full max-w-4xl relative">
            <form 
              onSubmit={handleSubmit} 
              className="relative flex flex-col bg-[#1e1f20]/90 rounded-3xl border border-white/10 focus-within:border-violet-500/50 transition-all shadow-2xl backdrop-blur-xl overflow-hidden p-3 gap-2"
            >
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={backendStatus === "loading" ? "ChemE-LLM is warming up..." : "Ask ChemE-LLM anything..."}
                disabled={backendStatus === "loading"}
                className="w-full bg-transparent text-[#e3e3e3] px-3 py-2 outline-none resize-none min-h-[48px] max-h-48 text-sm md:text-base placeholder-white/40 custom-scrollbar disabled:opacity-50 disabled:cursor-not-allowed"
                rows={1}
              />
              
              {/* Bottom Controls inside Input Pill */}
              <div className="flex items-center justify-between px-1 pt-1 border-t border-white/5">
                <div className="flex items-center gap-2">
                  <button type="button" className="p-2 rounded-full hover:bg-white/5 text-white/60 hover:text-white transition-colors" title="Add attachment">
                    <Plus size={18} />
                  </button>
                  <span className="text-xs text-white/40 hidden sm:inline px-2 py-0.5 rounded-full bg-white/5 border border-white/5">
                    {software === 'Both' ? 'All Software' : software}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button type="button" className="p-2 rounded-full hover:bg-white/5 text-white/60 hover:text-white transition-colors" title="Voice input">
                    <Mic size={18} />
                  </button>
                  <button
                    type="submit"
                    disabled={!inputValue.trim() || isLoading || backendStatus === "loading"}
                    className="p-2.5 rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-30 disabled:hover:from-violet-600 disabled:hover:to-indigo-600 disabled:cursor-not-allowed transition-all text-white shadow-md hover:scale-105"
                  >
                    <ArrowUp size={18} />
                  </button>
                </div>
              </div>
            </form>

            <div className="text-center mt-2.5 flex items-center justify-center gap-4 text-[11px] text-white/40">
              <span>ChemE-LLM can make mistakes. Verify simulation parameters.</span>
              <span className="hidden md:inline">•</span>
              <a href="https://harshithport.vercel.app/" target="_blank" rel="noopener noreferrer" className="hover:text-violet-400 underline transition-colors hidden md:inline">
                Credits to Harshith Bhardwaz
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Subcomponents

const MessageItem = React.memo(({ msg }: { msg: ChatMessage }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`flex gap-4 md:gap-6 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <div className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center mt-1 shadow-md ${
        msg.role === 'user' ? 'bg-[#282a2c] border border-white/10' : 'bg-gradient-to-tr from-violet-600 via-indigo-500 to-pink-500'
      }`}>
        {msg.role === 'user' ? <User size={18} className="text-white/80" /> : <Sparkles size={18} className="text-white" />}
      </div>

      <div className={`flex flex-col gap-2 max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
        <div className={`px-5 py-4 rounded-2xl ${
          msg.role === 'user' 
            ? 'bg-[#1e1f20] border border-white/10 rounded-tr-sm text-white/95 shadow-md' 
            : 'bg-transparent text-white/90 prose prose-invert max-w-none prose-p:leading-relaxed'
        }`}>
          {msg.role === 'user' ? (
            <p className="whitespace-pre-wrap">{msg.content}</p>
          ) : (
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          )}
        </div>

        {msg.mode && (
          <span className="text-[11px] font-medium text-violet-300 px-2.5 py-0.5 rounded-full border border-violet-500/30 bg-violet-500/10 shadow-sm">
            Mode: {msg.mode}
          </span>
        )}

        {msg.sources && msg.sources.length > 0 && (
          <SourceAccordion sources={msg.sources} />
        )}
      </div>
    </motion.div>
  );
});
MessageItem.displayName = 'MessageItem';

const SourceAccordion = ({ sources }: { sources: SourceChunk[] }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-2 w-full border border-white/10 rounded-xl overflow-hidden bg-[#1e1f20]/50 backdrop-blur-sm shadow-sm">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors text-sm text-white/80"
      >
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-violet-400" />
          <span className="font-medium">Show {sources.length} sources used</span>
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
                      <span className="text-xs bg-violet-500/20 text-violet-300 px-1.5 py-0.5 rounded border border-violet-500/20">[{src.id}]</span>
                      {src.topic}
                      <span className="text-xs text-white/40 font-normal border border-white/10 px-1.5 py-0.5 rounded-full">{src.software}</span>
                    </h4>
                    <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-violet-400 hover:underline flex items-center gap-1 shrink-0">
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
