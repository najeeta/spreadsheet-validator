"use client";

import { use, useRef, useEffect } from "react";
import { CopilotKit as CopilotKitProvider } from "@copilotkit/react-core";
import { CopilotChat, MessagesProps } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { User, Bot, Cog, CheckCircle2, Send } from "lucide-react";
import { FileSpreadsheet, Loader2 } from "lucide-react";
import { useA2UIStateRender } from "@/hooks/useA2UIStateRender";
import { ValidatorProvider, useValidator } from "@/contexts/ValidatorContext";
import { StateCanvas } from "@/components/StateCanvas";
import { RunsDropdown } from "@/components/RunsDropdown";

// Error handler to suppress expected reconnection errors on page refresh
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleCopilotError(errorEvent: { error?: any; type: string }) {
    const errorMessage = errorEvent.error?.message || String(errorEvent.error || "");
    // Suppress "RUN_ERROR" cascade errors - expected on page refresh
    if (errorMessage.includes("RUN_ERROR") || errorMessage.includes("already errored")) {
        console.debug("[CopilotKit] Suppressed reconnection error");
        return;
    }
    console.error("[CopilotKit] Error:", errorEvent);
}

// Helper to get friendly tool name
function getFriendlyToolName(toolName: string): string {
    // Map tool names to user-friendly descriptions
    const toolLabels: Record<string, string> = {
        "IngestionAgent": "Ingestion Agent",
        "ValidationAgent": "Validation Agent",
        "ProcessingAgent": "Processing Agent",
        "ingest_uploaded_file": "Ingesting File",
        "load_spreadsheet": "Loading Spreadsheet",
        "confirm_ingestion": "Confirming Ingestion",
        "validate_data": "Validating Data",
        "request_user_fix": "Requesting Fix",
        "write_fix": "Applying Fix",
        "batch_write_fixes": "Applying Fixes",
        "skip_row": "Skipping Row",
        "skip_fixes": "Skipping Remaining Fixes",
        "transform_data": "Transforming Data",
        "auto_add_computed_columns": "Adding Computed Columns",
        "package_results": "Packaging Results",
        "process_results": "Processing Results",
    };
    return toolLabels[toolName] || toolName;
}

// Component for rendering a tool call with its result
function ToolCallMessage({
    toolCall,
    toolResult,
    isLast,
    inProgress
}: {
    toolCall: { id: string; function: { name: string; arguments: string } };
    toolResult?: { content: string };
    isLast: boolean;
    inProgress: boolean;
}) {
    const toolName = getFriendlyToolName(toolCall.function.name);
    const isRunning = isLast && inProgress && !toolResult;

    return (
        <div className="flex items-center gap-2 py-1.5 px-2 rounded-md bg-gray-50 border border-gray-100">
            <div className="flex-shrink-0">
                {isRunning ? (
                    <Loader2 className="h-3.5 w-3.5 text-amber-500 animate-spin" />
                ) : toolResult ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                    <Cog className="h-3.5 w-3.5 text-gray-400" />
                )}
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-gray-700">
                        {isRunning ? `Running ${toolName}...` : toolName}
                    </span>
                </div>
            </div>
        </div>
    );
}

// [PATCH] Updated CustomMessages to display tool calls with proper UI
function CustomMessages({ messages, inProgress, RenderMessage }: MessagesProps) {
    // Build a map of toolCallId -> tool result message
    const toolResultMap = new Map<string, any>();
    messages.forEach((msg) => {
        const msgAny = msg as any;
        if (msg.role === "tool" && msgAny.toolCallId) {
            toolResultMap.set(msgAny.toolCallId, msgAny);
        }
    });

    // Process messages: group tool calls with their results
    const processedMessages: Array<{
        type: "user" | "assistant" | "tool-group";
        message?: any;
        toolCalls?: Array<{ call: any; result?: any }>;
        agentName?: string;
        content?: string;
    }> = [];

    messages.forEach((message, idx) => {
        const msgAny = message as any;

        if (message.role === "user") {
            processedMessages.push({ type: "user", message });
        } else if (message.role === "assistant") {
            const content = msgAny.content;
            const toolCalls = msgAny.toolCalls;
            const hasContent = content && typeof content === "string" && content.trim();
            const hasToolCalls = toolCalls && toolCalls.length > 0;

            // If has content, add as assistant message
            if (hasContent) {
                processedMessages.push({
                    type: "assistant",
                    message,
                    agentName: msgAny.name,
                    content: content.trim(),
                });
            }

            // If has tool calls, add as tool-group
            if (hasToolCalls) {
                const toolCallsWithResults = toolCalls.map((tc: any) => ({
                    call: tc,
                    result: toolResultMap.get(tc.id),
                }));
                processedMessages.push({
                    type: "tool-group",
                    toolCalls: toolCallsWithResults,
                    agentName: msgAny.name,
                });
            }
        }
        // Skip standalone tool messages - they're handled via toolResultMap
    });

    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [processedMessages.length, inProgress]);

    return (
        <div className="flex flex-col gap-3 p-4 flex-1 overflow-y-auto min-h-0">
            {processedMessages.map((item, index) => {
                if (item.type === "user") {
                    return (
                        <div key={item.message.id || index} className="flex flex-col gap-1">
                            <div className="flex items-center gap-1.5 text-xs font-medium text-burgundy-700">
                                <User className="h-3 w-3" />
                                <span>You</span>
                            </div>
                            <RenderMessage
                                message={item.message}
                                messages={messages}
                                inProgress={inProgress}
                                index={index}
                                isCurrentMessage={index === processedMessages.length - 1}
                            />
                        </div>
                    );
                }

                if (item.type === "assistant") {
                    const displayName = item.agentName &&
                        item.agentName !== "model" &&
                        item.agentName !== "assistant"
                        ? item.agentName
                        : "Assistant";

                    return (
                        <div key={item.message.id || index} className="flex flex-col gap-1">
                            <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
                                <Bot className="h-3 w-3" />
                                <span>{displayName}</span>
                            </div>
                            <RenderMessage
                                message={item.message}
                                messages={messages}
                                inProgress={inProgress}
                                index={index}
                                isCurrentMessage={index === processedMessages.length - 1}
                            />
                        </div>
                    );
                }

                if (item.type === "tool-group" && item.toolCalls) {
                    const isLastGroup = index === processedMessages.length - 1;
                    return (
                        <div key={`tools-${index}`} className="flex flex-col gap-1.5">
                            {item.toolCalls.map((tc, tcIdx) => (
                                <ToolCallMessage
                                    key={tc.call.id || tcIdx}
                                    toolCall={tc.call}
                                    toolResult={tc.result}
                                    isLast={isLastGroup && tcIdx === item.toolCalls!.length - 1}
                                    inProgress={inProgress}
                                />
                            ))}
                        </div>
                    );
                }

                return null;
            })}
            <div ref={bottomRef} />
        </div>
    );
}

// Main app component - consumes context for upload state
function ValidatorAppInner() {
    const { sessionId, uploading, uploadError, agentState } = useValidator();
    useA2UIStateRender();

    const uploadedFile = agentState?.file_name ?? null;

    return (
        <main className="flex h-screen bg-white">
            {/* Left panel: canvas */}
            <div className="flex-1 flex flex-col min-w-0 bg-white">
                {/* Header bar */}
                <div className="border-b border-gray-200 bg-white px-4 py-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2">
                                <FileSpreadsheet className="h-5 w-5 text-burgundy-700" />
                                <span className="font-semibold text-gray-800">
                                    Spreadsheet Validator
                                </span>
                            </div>

                            {/* Runs Dropdown */}
                            <div className="h-6 w-px bg-gray-200"></div>
                            <RunsDropdown currentRunId={sessionId} />
                        </div>

                        <div className="flex items-center gap-3">
                            {uploading && (
                                <div className="flex items-center gap-2 text-sm text-amber-600">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Uploading...
                                </div>
                            )}
                            {uploadedFile && !uploading && (
                                <span className="text-sm text-emerald-600">
                                    Uploaded: {uploadedFile}
                                </span>
                            )}
                            {uploadError && (
                                <span className="text-sm text-red-600">{uploadError}</span>
                            )}
                        </div>
                        <div
                            className="flex items-center gap-3 text-xs text-gray-400 font-mono"
                            suppressHydrationWarning
                        >
                            <span suppressHydrationWarning>
                                session: {sessionId.slice(0, 8)}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Canvas area */}
                <div className="flex-1 bg-white overflow-y-auto">
                    <StateCanvas />
                </div>
            </div>

            {/* Right panel: chat sidebar */}
            <div className="chat-sidebar w-[400px] border-l border-gray-200 flex flex-col min-h-0">
                <CopilotChat
                    className="h-full"
                    instructions="Help users validate spreadsheet data. When they upload a file, process it through ingestion, validation, and packaging."
                    labels={{
                        initial: "Upload a CSV or Excel file to start validation.",
                    }}
                    Messages={CustomMessages}
                    Input={({ inProgress, onSend }) => {
                        let inputRef: HTMLInputElement | null = null;
                        const handleSubmit = () => {
                            if (inputRef) {
                                const value = inputRef.value.trim();
                                if (value) {
                                    onSend(value);
                                    inputRef.value = "";
                                }
                            }
                        };
                        return (
                            <div className="flex items-center gap-3 p-4 border-t border-gray-200 bg-white flex-shrink-0">
                                <input
                                    ref={(el) => { inputRef = el; }}
                                    type="text"
                                    placeholder="Type a message..."
                                    className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-burgundy-500"
                                    disabled={inProgress}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" && !e.shiftKey) {
                                            e.preventDefault();
                                            handleSubmit();
                                        }
                                    }}
                                />
                                <button
                                    onClick={handleSubmit}
                                    disabled={inProgress}
                                    className="flex items-center justify-center h-11 w-11 rounded-lg bg-burgundy-800 text-white hover:bg-burgundy-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    {inProgress ? (
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                    ) : (
                                        <Send className="h-5 w-5" />
                                    )}
                                </button>
                            </div>
                        );
                    }}
                />
            </div>
        </main>
    );
}

// Page component - sets up providers and renders app
export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
    const { runId } = use(params);

    return (
        <CopilotKitProvider
            runtimeUrl="/api/copilotkit"
            agent="spreadsheet_validator"
            threadId={runId}
            onError={handleCopilotError}
            showDevConsole={false}
        >
            <ValidatorProvider sessionId={runId}>
                <ValidatorAppInner />
            </ValidatorProvider>
        </CopilotKitProvider>
    );
}
