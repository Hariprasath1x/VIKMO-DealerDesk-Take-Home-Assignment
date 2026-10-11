import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Bot,
  User,
  Sparkles,
  Wrench,
  RotateCcw,
  Tag,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { sendAssistantChat } from "../lib/api";
import type { AssistantToolCall } from "../types/api";
import { useDealer } from "../context/DealerContext";
import type { ActiveTab } from "../components/Layout";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: Date;
  toolCalls?: AssistantToolCall[];
  citedSkus?: string[];
}

interface AssistantPageProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const AssistantPage: React.FC<AssistantPageProps> = ({ onNavigate }) => {
  const { currentDealer } = useDealer();

  // Session state
  const [sessionId, setSessionId] = useState<string>(() => {
    const saved = sessionStorage.getItem("dealerdesk_assistant_session");
    if (saved) return saved;
    const newId = `sess-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    sessionStorage.setItem("dealerdesk_assistant_session", newId);
    return newId;
  });

  const [inputMessage, setInputMessage] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome-1",
      sender: "assistant",
      text: "Hello! I am your AI Dealer Assistant powered by Groq and DealerDesk's parts catalogue. I can help you search compatible automotive spare parts, check live warehouse stock levels, and prepare draft purchase orders. What can I look up for you today?",
      timestamp: new Date(),
    },
  ]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleResetSession = () => {
    const newId = `sess-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    sessionStorage.setItem("dealerdesk_assistant_session", newId);
    setSessionId(newId);
    setMessages([
      {
        id: "welcome-reset",
        sender: "assistant",
        text: "Started a fresh conversation session. How can I assist you with catalogue parts or inventory?",
        timestamp: new Date(),
      },
    ]);
    setError(null);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || inputMessage).trim();
    if (!query || isLoading) return;

    if (!currentDealer) {
      setError("Please select an active dealer in the top bar before sending messages.");
      return;
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await sendAssistantChat(sessionId, currentDealer.id, query);

      const assistantMsg: ChatMessage = {
        id: `assist-${Date.now()}`,
        sender: "assistant",
        text: response.reply,
        timestamp: new Date(),
        toolCalls: response.tool_calls,
        citedSkus: response.cited_skus,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message || "Failed to reach AI assistant. Please try again.");
      } else {
        setError("AI assistant encountered an unexpected error.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const toggleToolExpand = (msgId: string) => {
    setExpandedTools((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const quickPrompts = [
    "Do you have brake pads for Hyundai Creta?",
    "Check stock for spark plugs and air filters",
    "Find engine oil filters with price under ₹1000",
    "Show me parts with low stock needing reorder",
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-130px)] max-h-[850px] space-y-4">
      {/* Assistant Header Card */}
      <div className="bg-white border border-slate-200 rounded-xl px-5 py-3.5 flex flex-wrap items-center justify-between gap-3 shadow-2xs dark:bg-slate-900 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center font-bold">
            <Sparkles className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                AI Dealer Assistant
              </h2>
              <span className="text-[10px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-medium dark:bg-blue-950 dark:text-blue-300">
                Llama 3.3 70B & Dense RAG
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-mono">
              Dealer: {currentDealer?.dealer_code} ({currentDealer?.name}) • Session:{" "}
              {sessionId.substring(0, 16)}...
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleResetSession}
          className="text-xs gap-1.5"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          New Session
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" title="Assistant Communication Error">
          {error}
        </Alert>
      )}

      {/* Chat Messages Timeline */}
      <Card className="flex-1 overflow-hidden flex flex-col shadow-2xs">
        <CardContent className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {messages.map((msg) => {
            const isUser = msg.sender === "user";
            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white ${
                    isUser ? "bg-slate-800" : "bg-blue-600"
                  }`}
                >
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Bubble */}
                <div className="space-y-2 max-w-[85%] sm:max-w-[90%]">
                  <div
                    className={`p-4 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                      isUser
                        ? "bg-slate-900 text-white rounded-tr-none dark:bg-blue-700"
                        : "bg-slate-100 text-slate-900 rounded-tl-none border border-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700"
                    }`}
                  >
                    <p className="whitespace-pre-line">{msg.text}</p>
                  </div>

                  {/* Tool Call Activity Card */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs dark:bg-slate-800/40 dark:border-slate-700">
                      <button
                        type="button"
                        onClick={() => toggleToolExpand(msg.id)}
                        className="flex items-center justify-between w-full text-slate-600 font-semibold cursor-pointer dark:text-slate-300"
                      >
                        <span className="flex items-center gap-1.5">
                          <Wrench className="w-3.5 h-3.5 text-blue-600" />
                          Backend Agent Execution ({msg.toolCalls.length} tool{" "}
                          {msg.toolCalls.length > 1 ? "calls" : "call"})
                        </span>
                        {expandedTools[msg.id] ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {expandedTools[msg.id] && (
                        <div className="mt-2.5 space-y-2 border-t border-slate-200 pt-2 dark:border-slate-700">
                          {msg.toolCalls.map((tool, idx) => (
                            <div
                              key={idx}
                              className="bg-white p-2.5 rounded-lg border border-slate-200 dark:bg-slate-900 dark:border-slate-800"
                            >
                              <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold text-blue-600 dark:text-blue-400">
                                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                                {tool.name}()
                              </div>
                              <pre className="mt-1 text-[10px] text-slate-600 dark:text-slate-400 overflow-x-auto bg-slate-50 p-1.5 rounded dark:bg-slate-950">
                                {JSON.stringify(tool.arguments, null, 2)}
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Cited SKUs Interactive Chips */}
                  {msg.citedSkus && msg.citedSkus.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-[11px] text-slate-400 flex items-center gap-1 mr-1">
                        <Tag className="w-3 h-3" /> Cited SKUs:
                      </span>
                      {msg.citedSkus.map((sku) => (
                        <button
                          key={sku}
                          onClick={() => onNavigate("catalogue")}
                          className="font-mono text-[11px] font-bold text-blue-600 bg-blue-50 border border-blue-200 hover:bg-blue-100 px-2 py-0.5 rounded transition-colors cursor-pointer dark:bg-blue-950/60 dark:border-blue-800 dark:text-blue-300"
                        >
                          {sku}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Typing / Agent Processing Indicator */}
          {isLoading && (
            <div className="flex gap-3 max-w-xl mr-auto">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0 text-white">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <div className="p-3.5 rounded-2xl rounded-tl-none bg-slate-100 border border-slate-200 dark:bg-slate-800 dark:border-slate-700 text-xs flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce"></div>
                <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.2s]"></div>
                <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.4s]"></div>
                <span className="text-slate-500 font-medium ml-1">
                  Searching catalogue & reasoning with Groq...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        {/* Suggested Prompts Bar */}
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-900/40 flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-[11px] text-slate-400 font-medium whitespace-nowrap">
            Suggestions:
          </span>
          {quickPrompts.map((prompt, i) => (
            <button
              key={i}
              type="button"
              disabled={isLoading}
              onClick={() => handleSendMessage(prompt)}
              className="text-[11px] whitespace-nowrap bg-white border border-slate-200 px-2.5 py-1 rounded-full text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 sm:p-4 border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputMessage}
              disabled={isLoading}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask about parts compatibility, stock availability, or create orders..."
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
            />
            <Button
              type="submit"
              disabled={!inputMessage.trim() || isLoading}
              isLoading={isLoading}
              className="h-10 px-4 rounded-xl gap-1.5"
            >
              <Send className="w-4 h-4" />
              <span className="hidden sm:inline">Send</span>
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
};
