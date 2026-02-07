"use client";

import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { useCoAgent, useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, Role } from "@copilotkit/runtime-client-gql";
import type { AgentState, RunGlobals } from "@/lib/types";
import { DEFAULT_INITIAL_STATE } from "@/lib/types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";

interface ValidatorContextValue {
  sessionId: string;
  agentState: AgentState;
  setAgentState: React.Dispatch<React.SetStateAction<AgentState>>;
  // File upload
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  triggerUpload: () => void;
  uploading: boolean;
  uploadError: string | null;
  // Pipeline trigger
  startPipeline: (globals: RunGlobals) => void;
}

const ValidatorContext = createContext<ValidatorContextValue | null>(null);

interface ValidatorProviderProps {
  sessionId: string;
  children: React.ReactNode;
}

export function ValidatorProvider({
  sessionId,
  children,
}: ValidatorProviderProps) {
  // Single source of truth for agent state
  const [agentState, setAgentState] = useState<AgentState>(DEFAULT_INITIAL_STATE);

  // File upload state - owned by the provider
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Single useCoAgent call with external state management
  // SSE events (STATE_DELTA/STATE_SNAPSHOT) update this state during active runs
  useCoAgent<AgentState>({
    name: "spreadsheet_validator",
    state: agentState,
    setState: setAgentState,
  });

  const { appendMessage } = useCopilotChat();

  // Trigger file input click
  const triggerUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  // Start pipeline: sync globals into agent state, switch to RUNNING, and send "Begin"
  const startPipeline = useCallback(
    (globals: RunGlobals) => {
      setAgentState((prev) => ({
        ...(prev ?? DEFAULT_INITIAL_STATE),
        globals,
        status: "RUNNING",
      }));
      appendMessage(
        new TextMessage({
          content: "Begin",
          role: Role.User,
        }),
      );
    },
    [appendMessage, setAgentState],
  );

  // Handle file upload
  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setUploading(true);
      setUploadError(null);

      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("session_id", sessionId);

        const resp = await fetch(`${BACKEND_URL}/upload`, {
          method: "POST",
          body: formData,
        });

        if (!resp.ok) {
          let errorMessage = "Upload failed";
          try {
            const data = await resp.json();
            errorMessage = data.detail || data.message || errorMessage;
          } catch {
            const text = await resp.text();
            errorMessage = text || `Upload failed (${resp.status})`;
          }
          throw new Error(errorMessage);
        }

        const data = await resp.json();

        // Update agent state with uploaded file name
        setAgentState((prev) => ({
          ...(prev ?? DEFAULT_INITIAL_STATE),
          file_name: data.file_name,
        }));
      } catch (err) {
        console.error("[ValidatorProvider] Upload error:", err);
        const errorMessage =
          err instanceof Error
            ? err.message
            : typeof err === "string"
              ? err
              : "Upload failed";
        setUploadError(errorMessage);
      } finally {
        setUploading(false);
        // Reset input so same file can be re-selected
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [sessionId],
  );

  // Hydrate state from backend on initial mount
  const hydrateFromBackend = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/runs/${sessionId}`);
      if (!resp.ok) {
        if (resp.status === 404) {
          console.warn("[ValidatorProvider] Session not found, redirecting to home");
          window.location.href = "/";
          return;
        }
        throw new Error("Failed to fetch session");
      }

      const data = await resp.json();
      console.log("[ValidatorProvider] Hydrated state from backend:", {
        status: data.status,
        file_name: data.file_name,
        records_count: data.dataframe_records?.length ?? 0,
      });

      setAgentState((prev) => ({
        ...(prev ?? DEFAULT_INITIAL_STATE),
        file_name: data.file_name ?? prev?.file_name ?? null,
        status: (data.status as AgentState["status"]) ?? prev?.status ?? "IDLE",
        dataframe_records: data.dataframe_records ?? prev?.dataframe_records ?? [],
        dataframe_columns: data.dataframe_columns ?? prev?.dataframe_columns ?? [],
        pending_fixes: data.pending_fixes ?? prev?.pending_fixes ?? [],
        validation_errors: data.validation_errors ?? prev?.validation_errors ?? [],
        artifacts: data.artifacts ?? prev?.artifacts ?? {},
        validation_complete: data.validation_complete ?? prev?.validation_complete ?? false,
      }));
    } catch (e) {
      console.error("[ValidatorProvider] Failed to hydrate from backend:", e);
    }
  }, [sessionId]);

  useEffect(() => {
    hydrateFromBackend();
  }, [hydrateFromBackend]);

  return (
    <ValidatorContext.Provider
      value={{
        sessionId,
        agentState,
        setAgentState,
        fileInputRef,
        triggerUpload,
        uploading,
        uploadError,
        startPipeline,
      }}
    >
      {/* Hidden file input owned by provider */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={handleUpload}
        className="hidden"
      />
      {children}
    </ValidatorContext.Provider>
  );
}

export function useValidator() {
  const ctx = useContext(ValidatorContext);
  if (!ctx) throw new Error("useValidator must be inside ValidatorProvider");
  return ctx;
}
