'use client';

import React, { useState, useRef, useTransition } from 'react';
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Lock,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  StopCircle,
  Trash2,
  User,
} from 'lucide-react';
import { deleteAssistantThread, getAssistantThreadMessages } from '@/lib/api';
import { AssistantCitationItem, AssistantMessageItem, AssistantThreadItem } from '@/lib/types';
import { useAuth } from '@/context/AuthContext';

interface Props {
  initialThreads: AssistantThreadItem[];
  canPersistThreads: boolean;
  canGroundSop: boolean;
}

export function AssistantClient({ initialThreads, canPersistThreads, canGroundSop }: Props) {
  const { openUpgradeModal } = useAuth();
  const [threads, setThreads] = useState<AssistantThreadItem[]>(initialThreads);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AssistantMessageItem[]>([
    {
      role: 'assistant',
      content:
        'Hello! I am ComplianceOS’s dedicated AI compliance assistant. Ask me questions regarding Bangladeshi NBR VAT regulations, corporate policies, filing deadlines, or statutory trade requirements.',
      citations: [],
    },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSelectThread = (threadId: string) => {
    setActiveThreadId(threadId);
    startTransition(async () => {
      try {
        const res = await getAssistantThreadMessages(threadId);
        if (res.messages && res.messages.length > 0) {
          setMessages(res.messages);
        }
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to load thread history.');
      }
    });
  };

  const handleNewChat = () => {
    setActiveThreadId(null);
    setMessages([
      {
        role: 'assistant',
        content:
          'Started a fresh inquiry. What compliance or regulatory topic would you like to review?',
        citations: [],
      },
    ]);
  };

  const handleDeleteThread = (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    startTransition(async () => {
      try {
        await deleteAssistantThread(threadId);
        setThreads((prev) => prev.filter((t) => t.id !== threadId));
        if (activeThreadId === threadId) {
          handleNewChat();
        }
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : 'Failed to delete thread.');
      }
    });
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || isStreaming) return;

    setInput('');
    setErrorMsg(null);

    // Append user message
    const userMsg: AssistantMessageItem = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMsg]);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    setIsStreaming(true);

    try {
      const res = await fetch('/api/assistant/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: query, thread_id: activeThreadId }),
        signal: abortController.signal,
      });

      if (!res.ok) {
        if (res.status === 429) {
          throw new Error('Monthly AI question quota reached. Upgrade your plan for more queries.');
        }
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to communicate with the compliance assistant.');
      }

      if (!res.body) throw new Error('Response stream unavailable.');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const rawEvent of events) {
          if (!rawEvent.trim()) continue;
          const dataLine = rawEvent
            .split('\n')
            .find((l) => l.startsWith('data:'));
          if (!dataLine) continue;

          const data = JSON.parse(dataLine.slice(5).trim());
          if (data.type === 'completed') {
            const assistantMsg: AssistantMessageItem = {
              role: 'assistant',
              content: data.answer,
              citations: data.citations,
            };
            setMessages((prev) => [...prev, assistantMsg]);
            if (data.thread_id && !activeThreadId) {
              setActiveThreadId(data.thread_id);
              setThreads((prev) => [
                { id: data.thread_id, title: query.slice(0, 35) + '...', created_at: new Date().toISOString() },
                ...prev,
              ]);
            }
            scrollToBottom();
          } else if (data.type === 'error') {
            setErrorMsg(data.message);
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setErrorMsg(err.message);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-semibold mb-2 border border-indigo-200">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>Grounded Legal Intelligence</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">AI Compliance Assistant</h1>
          <p className="text-xs text-slate-500 mt-1">
            Grounded in official Bangladeshi gazettes, NBR VAT directives, and company SOP benchmarks.
          </p>
        </div>

        {/* Feature badge */}
        <div className="flex items-center gap-2">
          {!canGroundSop ? (
            <div className="px-3 py-1.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 text-xs flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-slate-400" />
              <span>Free Plan (Regulations only)</span>
            </div>
          ) : (
            <div className="px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Grounded in Company SOP Chunks</span>
            </div>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-600 font-bold">×</button>
        </div>
      )}

      {/* Main chat layout */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 min-h-[550px]">
        {/* Threads sidebar (Starter+) */}
        <div className="hidden md:flex flex-col bg-white rounded-2xl border border-slate-200 p-4 shadow-xs space-y-3">
          <button
            type="button"
            onClick={handleNewChat}
            className="w-full py-2 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center justify-center gap-1.5 shadow-xs"
          >
            <Plus className="w-4 h-4" />
            <span>New Inquiry</span>
          </button>

          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider pt-2">
            Audit History
          </div>

          {!canPersistThreads ? (
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-xs space-y-2">
              <div className="flex items-center gap-1.5 text-slate-700 font-semibold">
                <Lock className="w-3.5 h-3.5 text-indigo-600" />
                <span>Thread Retention Locked</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Upgrade to Starter or higher to automatically save thread history and return to past inquiries.
              </p>
              <button
                type="button"
                onClick={() => openUpgradeModal('Thread History & SOP Grounding', 'starter')}
                className="w-full py-1 text-center font-bold text-indigo-600 hover:underline"
              >
                Upgrade Plan
              </button>
            </div>
          ) : threads.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-400">No saved threads yet</div>
          ) : (
            <div className="space-y-1.5 overflow-y-auto max-h-[400px]">
              {threads.map((t) => (
                <div
                  key={t.id}
                  onClick={() => handleSelectThread(t.id)}
                  className={`group p-2.5 rounded-xl text-xs font-medium cursor-pointer flex items-center justify-between transition-all ${
                    activeThreadId === t.id
                      ? 'bg-indigo-50 text-indigo-900 font-bold border border-indigo-200'
                      : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <MessageSquare className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="truncate">{t.title}</span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDeleteThread(t.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 transition-opacity"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Chat area */}
        <div className="md:col-span-3 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col h-[600px]">
          {/* Messages stream */}
          <div
            aria-live="polite"
            className="flex-1 p-5 overflow-y-auto space-y-4"
          >
            {messages.map((m, idx) => {
              const isUser = m.role === 'user';
              return (
                <div
                  key={idx}
                  className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  {!isUser && (
                    <div className="w-7 h-7 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-xl rounded-2xl p-4 text-xs leading-relaxed space-y-3 ${
                      isUser
                        ? 'bg-indigo-600 text-white font-medium rounded-tr-xs'
                        : 'bg-slate-50 border border-slate-200 text-slate-800 rounded-tl-xs shadow-2xs'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{m.content}</p>

                    {/* Citations block */}
                    {!isUser && m.citations && m.citations.length > 0 && (
                      <div className="pt-2 border-t border-slate-200/80 space-y-2">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                          Verified Statutory & SOP Citations
                        </span>
                        <div className="space-y-1.5">
                          {m.citations.map((c, cIdx) => (
                            <div
                              key={cIdx}
                              className="p-2 rounded-lg bg-white border border-slate-200 text-[11px] space-y-1"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">
                                  {c.source} • {c.section}
                                </span>
                                <span
                                  className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                                    c.is_verified
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                                  }`}
                                >
                                  {c.is_verified ? (
                                    <>
                                      <CheckCircle2 className="w-2.5 h-2.5" />
                                      <span>Verified ({Math.round(c.confidence * 100)}%)</span>
                                    </>
                                  ) : (
                                    <>
                                      <AlertCircle className="w-2.5 h-2.5" />
                                      <span>Flagged</span>
                                    </>
                                  )}
                                </span>
                              </div>
                              <blockquote className="text-slate-600 italic border-l-2 border-indigo-400 pl-2">
                                &ldquo;{c.quote}&rdquo;
                              </blockquote>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {isUser && (
                    <div className="w-7 h-7 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              );
            })}

            {isStreaming && (
              <div className="flex items-center gap-2 text-xs text-indigo-600 font-semibold py-2">
                <Sparkles className="w-4 h-4 animate-spin" />
                <span>Evaluating regulatory context and cross-referencing citations...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Prompt input */}
          <form onSubmit={handleSubmit} className="p-3 border-t border-slate-200 bg-slate-50/50 rounded-b-2xl flex items-center gap-2">
            <input
              type="text"
              required
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a compliance question (e.g. When is our Mushak-9.1 filing deadline?)..."
              disabled={isStreaming}
              className="flex-1 px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={handleStop}
                className="px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-xs"
              >
                <StopCircle className="w-4 h-4" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-xs"
              >
                <Send className="w-4 h-4" />
                <span>Ask</span>
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
