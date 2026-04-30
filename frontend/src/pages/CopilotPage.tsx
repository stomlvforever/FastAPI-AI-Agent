import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StatusView } from "../components/StatusView.tsx";
import { agentApi } from "../lib/api.ts";
import { getErrorMessage } from "../lib/format.ts";

type ChatMessage = {
  id: string;
  role: string;
  content: string;
};

function createMessageId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function CopilotPage() {
  const queryClient = useQueryClient();
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState("");
  const [hasHydratedHistory, setHasHydratedHistory] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  const historyQuery = useQuery({
    queryKey: ["agent-history"],
    queryFn: agentApi.history,
  });

  const clearMutation = useMutation({
    mutationFn: agentApi.clearHistory,
    onSuccess: async () => {
      setMessages([]);
      setHasHydratedHistory(true);
      await queryClient.invalidateQueries({ queryKey: ["agent-history"] });
    },
  });

  useEffect(() => {
    if (!historyQuery.data || hasHydratedHistory) {
      return;
    }

    setMessages(
      historyQuery.data.messages.map((message, index) => ({
        id: `${message.role}-${message.timestamp ?? index}`,
        role: message.role,
        content: message.content,
      })),
    );
    setHasHydratedHistory(true);
  }, [hasHydratedHistory, historyQuery.data]);

  useEffect(() => {
    const node = transcriptRef.current;
    if (!node) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [messages]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = prompt.trim();
    if (!message) {
      return;
    }

    const assistantId = createMessageId("assistant");
    setPrompt("");
    setMessages((current) => [
      ...current,
      {
        id: createMessageId("user"),
        role: "user",
        content: message,
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
      },
    ]);

    setIsStreaming(true);

    try {
      await agentApi.streamChat(message, (chunk) => {
        setMessages((current) =>
          current.map((entry) =>
            entry.id === assistantId
              ? {
                  ...entry,
                  content: `${entry.content}${chunk}`,
                }
              : entry,
          ),
        );
      });
      await queryClient.invalidateQueries({ queryKey: ["agent-history"] });
    } catch (error) {
      setMessages((current) =>
        current.map((entry) =>
          entry.id === assistantId
            ? {
                ...entry,
                content: `Copilot request failed.\n\n${getErrorMessage(error)}`,
              }
            : entry,
        ),
      );
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="page-stack">
      <section className="hero-card">
        <span className="eyebrow">Dedicated agent route</span>
        <h1>Copilot lives in its own workspace, not inside the article hero.</h1>
        <p className="hero-copy">
          This page consumes the existing streaming Agent API, keeps history isolated, and avoids
          blending administrative chat with the main article reading experience.
        </p>
        <div className="hero-actions">
          <button
            className="button button-secondary"
            disabled={clearMutation.isPending}
            onClick={() => clearMutation.mutate()}
            type="button"
          >
            {clearMutation.isPending ? "Clearing..." : "Clear history"}
          </button>
        </div>
      </section>

      {historyQuery.isError ? (
        <StatusView
          title="Copilot history failed to load"
          detail={getErrorMessage(historyQuery.error)}
          tone="error"
        />
      ) : null}

      <div className="split-layout">
        <section className="panel copilot-panel">
          <div className="section-heading">
            <span className="eyebrow">Conversation stream</span>
            <h2>Directly backed by /api/v1/agent/chat/stream</h2>
          </div>

          <div className="transcript" ref={transcriptRef}>
            {messages.length === 0 ? (
              <StatusView
                title="No conversation yet"
                detail="Ask about users, articles, system state, or use this as the future assistant entry point."
              />
            ) : null}

            {messages.map((message) => (
              <article
                className={`message-bubble ${message.role === "user" ? "is-user" : "is-assistant"}`}
                key={message.id}
              >
                <span className="message-role">{message.role}</span>
                <p>{message.content || (isStreaming ? "Streaming..." : "")}</p>
              </article>
            ))}
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <label className="input-shell textarea-shell">
              <span>Prompt</span>
              <textarea
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Ask Copilot about articles, profiles, or operational data"
                rows={4}
                value={prompt}
              />
            </label>
            <button className="button button-primary" disabled={isStreaming} type="submit">
              {isStreaming ? "Streaming response..." : "Send prompt"}
            </button>
          </form>
        </section>

        <aside className="panel sidebar-panel">
          <div className="section-heading">
            <span className="eyebrow">Placement guidance</span>
            <h2>Why the agent route is separate</h2>
          </div>
          <div className="feature-grid compact-grid">
            <div className="feature-card">
              <strong>No homepage collision</strong>
              <p>The public-facing article stream stays editorial instead of chat-first.</p>
            </div>
            <div className="feature-card">
              <strong>Room for role-based access</strong>
              <p>Later you can split user Copilot and admin Copilot without reworking the site map.</p>
            </div>
            <div className="feature-card">
              <strong>Direct API mapping</strong>
              <p>History, clear-history, and streaming chat already exist in the backend today.</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
