"use client";

import { useState, useMemo, useRef, useCallback } from "react";
import { CopilotKit as CopilotKitProvider } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { Upload, FileSpreadsheet, Loader2 } from "lucide-react";
import { useA2UIStateRender } from "@/hooks/useA2UIStateRender";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";

function ChatWithStateRender() {
  // Activate state-driven card rendering inside CopilotKit context
  useA2UIStateRender();
  return null;
}

export default function Home() {
  const threadId = useMemo(() => crypto.randomUUID(), []);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const ensureSession = useCallback(async () => {
    if (sessionReady) return;
    try {
      await fetch(`${BACKEND_URL}/run?thread_id=${threadId}`, {
        method: "POST",
      });
      setSessionReady(true);
    } catch (e) {
      console.error("Failed to create session:", e);
    }
  }, [threadId, sessionReady]);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setUploading(true);
      setError(null);

      try {
        await ensureSession();

        const formData = new FormData();
        formData.append("file", file);

        const resp = await fetch(
          `${BACKEND_URL}/upload?thread_id=${threadId}`,
          {
            method: "POST",
            body: formData,
          },
        );

        if (!resp.ok) {
          const data = await resp.json();
          throw new Error(data.detail || "Upload failed");
        }

        const data = await resp.json();
        setUploadedFile(data.file_name);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [threadId, ensureSession],
  );

  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit"
      agent="spreadsheet_validator"
      threadId={threadId}
    >
      <ChatWithStateRender />
      <main className="flex min-h-screen flex-col">
        {/* Status bar */}
        <div className="border-b border-gray-800 bg-gray-900 px-4 py-2">
          <div className="flex items-center justify-between max-w-4xl mx-auto">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-blue-400" />
              <span className="font-semibold text-gray-200">
                Spreadsheet Validator
              </span>
            </div>
            <div className="flex items-center gap-3">
              {uploading && (
                <div className="flex items-center gap-2 text-sm text-yellow-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Uploading...
                </div>
              )}
              {uploadedFile && !uploading && (
                <span className="text-sm text-emerald-400">
                  Uploaded: {uploadedFile}
                </span>
              )}
              {error && (
                <span className="text-sm text-red-400">{error}</span>
              )}
            </div>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1">
          <CopilotChat
            className="h-[calc(100vh-48px)]"
            instructions="Help users validate spreadsheet data. When they upload a file, process it through ingestion, validation, and packaging."
            labels={{
              initial: "Upload a CSV or Excel file to start validation.",
            }}
            Input={({ inProgress, onSend }) => (
              <div className="flex items-center gap-2 p-3 border-t border-gray-800">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleUpload}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                  disabled={uploading}
                >
                  <Upload className="h-4 w-4" />
                  Upload File
                </button>
                <input
                  type="text"
                  placeholder="Type a message..."
                  className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={inProgress}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      const value = e.currentTarget.value.trim();
                      if (value) {
                        onSend(value);
                        e.currentTarget.value = "";
                      }
                    }
                  }}
                />
              </div>
            )}
          />
        </div>
      </main>
    </CopilotKitProvider>
  );
}
