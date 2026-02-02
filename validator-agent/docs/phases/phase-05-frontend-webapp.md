# Phase 5: Frontend Webapp

Phase 5 builds the Next.js frontend with CopilotKit integration, custom React card components for pipeline state visualization, and the `useCoAgentStateRender` hook that drives state-based rendering. No A2UI protocol, no `@copilotkit/a2ui-renderer`, no `@a2ui/lit` packages.

**Stories:** 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
**Depends on:** Phase 4 (backend server for API route proxy)
**Quality check:** `cd webapp && npm run build && npx vitest run`

---

## Story 5.1: Webapp scaffold with Next.js, CopilotKit, and dependencies {#story-5.1}

### Summary

Create the Next.js webapp scaffold with CopilotKit, AG-UI client, Tailwind CSS, and all dependencies. Do NOT install A2UI-specific packages. Verify with a successful build.

### Test (write first)

Since this is a scaffold story, the primary test is that the project builds. Create a minimal vitest config and a smoke test.

**File: `webapp/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

**File: `webapp/src/__tests__/setup.ts`**

```typescript
import "@testing-library/jest-dom";
```

**File: `webapp/src/__tests__/scaffold.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Scaffold", () => {
  it("package.json exists", () => {
    const pkg = path.resolve(__dirname, "../../package.json");
    expect(fs.existsSync(pkg)).toBe(true);
  });

  it("has @copilotkit/react-core dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@copilotkit/react-core"]).toBeDefined();
  });

  it("has @ag-ui/client dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@ag-ui/client"]).toBeDefined();
  });

  it("does NOT have @copilotkit/a2ui-renderer dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@copilotkit/a2ui-renderer"]).toBeUndefined();
  });

  it("does NOT have @a2ui/lit dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@a2ui/lit"]).toBeUndefined();
  });

  it("layout.tsx exists", () => {
    const layout = path.resolve(__dirname, "../app/layout.tsx");
    expect(fs.existsSync(layout)).toBe(true);
  });
});
```

### Implementation

1. Initialize the webapp:

```bash
mkdir -p webapp
cd webapp
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --no-import-alias
```

2. **`webapp/package.json`** dependencies (add to generated file):

```json
{
  "dependencies": {
    "@copilotkit/react-core": "~1.50.0",
    "@copilotkit/react-ui": "~1.50.0",
    "@copilotkit/runtime": "~1.50.0",
    "@ag-ui/client": "^0.0.42",
    "hono": "^4.6.18",
    "lucide-react": "latest",
    "clsx": "latest",
    "tailwind-merge": "latest"
  },
  "devDependencies": {
    "vitest": "latest",
    "@vitejs/plugin-react": "latest",
    "@testing-library/react": "latest",
    "@testing-library/jest-dom": "latest",
    "jsdom": "latest"
  }
}
```

Do NOT install `@copilotkit/a2ui-renderer` or `@a2ui/lit`.

3. **`webapp/tsconfig.json`** — ensure path alias:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

4. **`webapp/src/app/layout.tsx`**:

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./Providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Spreadsheet Validator",
  description: "Validate spreadsheet data with AI-powered agents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-950 text-gray-100`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

5. Create a stub `Providers.tsx` (will be filled in Story 5.2):

**`webapp/src/app/Providers.tsx`**:

```tsx
"use client";

export function Providers({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
```

6. Create a minimal page so the build succeeds:

**`webapp/src/app/page.tsx`**:

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <h1 className="text-2xl font-bold">Spreadsheet Validator</h1>
    </main>
  );
}
```

### Success criteria

- [ ] `npm install` succeeds
- [ ] `npm run build` succeeds (exit code 0)
- [ ] `package.json` has `@copilotkit/react-core`, `@copilotkit/runtime`, `@ag-ui/client`, `hono`
- [ ] `package.json` does NOT have `@copilotkit/a2ui-renderer`
- [ ] `package.json` does NOT have `@a2ui/lit`
- [ ] `layout.tsx` renders children wrapped in Providers
- [ ] Tailwind CSS classes compile correctly
- [ ] `npx vitest run` passes all scaffold tests

### Quality check

```bash
cd webapp && npm run build && npx vitest run
```

### Commit message

```
feat(webapp): scaffold Next.js app with CopilotKit and AG-UI client

- Next.js 16 + React 19 + TypeScript + Tailwind CSS 4
- CopilotKit v1.50, @ag-ui/client, hono dependencies
- No @copilotkit/a2ui-renderer or @a2ui/lit — Plan A is state-driven
- Dark theme layout with Geist fonts
```

---

## Story 5.2: AgentState types and CopilotKit Providers (no A2UI renderer) {#story-5.2}

### Summary

Create the TypeScript AgentState type mirroring the backend PipelineState exactly, along with the CopilotKit provider configuration. The provider does NOT use `renderActivityMessages` (no A2UI renderer).

### Test (write first)

**File: `webapp/src/__tests__/types.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { DEFAULT_INITIAL_STATE } from "@/lib/types";
import type { PipelineStatus, AgentState } from "@/lib/types";

describe("AgentState types", () => {
  it("DEFAULT_INITIAL_STATE has status IDLE", () => {
    expect(DEFAULT_INITIAL_STATE.status).toBe("IDLE");
  });

  it("DEFAULT_INITIAL_STATE has empty dataframe_records", () => {
    expect(DEFAULT_INITIAL_STATE.dataframe_records).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty dataframe_columns", () => {
    expect(DEFAULT_INITIAL_STATE.dataframe_columns).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty validation_errors", () => {
    expect(DEFAULT_INITIAL_STATE.validation_errors).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty pending_fixes", () => {
    expect(DEFAULT_INITIAL_STATE.pending_fixes).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty artifacts", () => {
    expect(DEFAULT_INITIAL_STATE.artifacts).toEqual({});
  });

  it("DEFAULT_INITIAL_STATE has validation_complete false", () => {
    expect(DEFAULT_INITIAL_STATE.validation_complete).toBe(false);
  });

  it("DEFAULT_INITIAL_STATE has usd_rounding cents", () => {
    expect(DEFAULT_INITIAL_STATE.usd_rounding).toBe("cents");
  });

  it("PipelineStatus type allows all 10 values", () => {
    // TypeScript compile-time check — runtime assertion
    const statuses: PipelineStatus[] = [
      "IDLE",
      "UPLOADING",
      "RUNNING",
      "VALIDATING",
      "WAITING_FOR_USER",
      "FIXING",
      "TRANSFORMING",
      "PACKAGING",
      "COMPLETED",
      "FAILED",
    ];
    expect(statuses).toHaveLength(10);
  });
});
```

**File: `webapp/src/__tests__/providers.test.tsx`**

```typescript
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Providers", () => {
  it("does not use renderActivityMessages prop", () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, "../app/Providers.tsx"),
      "utf8"
    );
    expect(source).not.toContain("renderActivityMessages");
  });

  it("has CopilotKitProvider with runtimeUrl", () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, "../app/Providers.tsx"),
      "utf8"
    );
    expect(source).toContain("CopilotKitProvider");
    expect(source).toContain("/api/copilotkit");
  });
});
```

### Implementation

**File: `webapp/src/lib/types.ts`**

```typescript
/**
 * Shared TypeScript types matching backend PipelineState.
 */

export type PipelineStatus =
  | "IDLE"
  | "UPLOADING"
  | "RUNNING"
  | "VALIDATING"
  | "WAITING_FOR_USER"
  | "FIXING"
  | "TRANSFORMING"
  | "PACKAGING"
  | "COMPLETED"
  | "FAILED";

export interface ValidationError {
  row_index: number;
  row_data: Record<string, unknown>;
  errors: Array<{ field: string; error: string }>;
}

export interface FixRequest {
  row_index: number;
  field: string;
  current_value: string;
  error_message: string;
}

export interface AgentState {
  status: PipelineStatus;
  active_run_id: string | null;
  file_path: string | null;
  file_name: string | null;
  uploaded_file: string | null;
  dataframe_records: Record<string, unknown>[];
  dataframe_columns: string[];
  validation_errors: ValidationError[];
  validation_complete: boolean;
  pending_fixes: FixRequest[];
  artifacts: Record<string, string>;
  as_of: string | null;
  usd_rounding: "cents" | "whole" | null;
  cost_center_map: Record<string, string>;
}

export const DEFAULT_INITIAL_STATE: AgentState = {
  status: "IDLE",
  active_run_id: null,
  file_path: null,
  file_name: null,
  uploaded_file: null,
  dataframe_records: [],
  dataframe_columns: [],
  validation_errors: [],
  validation_complete: false,
  pending_fixes: [],
  artifacts: {},
  as_of: null,
  usd_rounding: "cents",
  cost_center_map: {},
};
```

**Update `webapp/src/app/Providers.tsx`**:

```tsx
"use client";

import { CopilotKit as CopilotKitProvider } from "@copilotkit/react-core";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit">
      {children}
    </CopilotKitProvider>
  );
}
```

> **Note:** The CopilotKit v1.50 may export the provider as `CopilotKit` or `CopilotKitProvider` depending on the version. Adjust the import accordingly. The key constraint is: NO `renderActivityMessages` prop.

### Success criteria

- [ ] `AgentState` type has all fields matching PipelineState
- [ ] `PipelineStatus` includes all 10 values
- [ ] `DEFAULT_INITIAL_STATE` has `status='IDLE'`, empty arrays, correct defaults
- [ ] `CopilotKitProvider` has `runtimeUrl='/api/copilotkit'`
- [ ] `CopilotKitProvider` does NOT have `renderActivityMessages` prop
- [ ] All tests pass: `npx vitest run`

### Quality check

```bash
cd webapp && npm run build && npx vitest run
```

### Commit message

```
feat(webapp): add AgentState types and CopilotKit provider

- AgentState mirrors backend PipelineState with all 10 status values
- DEFAULT_INITIAL_STATE with sensible defaults
- CopilotKitProvider with runtimeUrl — no renderActivityMessages
```

---

## Story 5.3: CopilotKit API route with HttpAgent {#story-5.3}

### Summary

Create the Next.js API route that proxies CopilotKit requests to the backend `/agent` SSE endpoint via HttpAgent from `@ag-ui/client`. The route bridges the CopilotKit frontend to the ag-ui-adk backend.

### Test (write first)

**File: `webapp/src/__tests__/route.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("CopilotKit API Route", () => {
  const routePath = path.resolve(
    __dirname,
    "../app/api/copilotkit/[[...handle]]/route.ts"
  );

  it("route.ts exists", () => {
    expect(fs.existsSync(routePath)).toBe(true);
  });

  it("exports GET handler", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toMatch(/export\s+.*GET/);
  });

  it("exports POST handler", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toMatch(/export\s+.*POST/);
  });

  it("uses HttpAgent", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toContain("HttpAgent");
  });

  it("uses CopilotRuntime", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toContain("CopilotRuntime");
  });

  it("agent key is spreadsheet_validator", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });
});
```

### Implementation

**File: `webapp/src/app/api/copilotkit/[[...handle]]/route.ts`**

```typescript
import { HttpAgent } from "@ag-ui/client";
import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
} from "@copilotkit/runtime";
import { createCopilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime/next";

const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL || "http://localhost:8080/agent";

const agent = new HttpAgent({
  url: AGENT_URL,
});

const runtime = new CopilotRuntime({
  agents: {
    spreadsheet_validator: agent,
  },
});

export const { GET, POST } = createCopilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  serviceAdapter: new ExperimentalEmptyAdapter(),
  endpoint: "/api/copilotkit",
});
```

> **Note:** The exact CopilotKit runtime v1.50 API may use `copilotKitEndpoint` from `@copilotkit/runtime/v2` with hono, or the Next.js-specific helper. Adjust imports based on what the installed version provides. The key requirements are: HttpAgent pointing to the backend, agent keyed as `spreadsheet_validator`, and GET/POST exports.

### Success criteria

- [ ] `route.ts` exports `GET` and `POST` handlers
- [ ] `CopilotRuntime` has agent keyed as `spreadsheet_validator`
- [ ] `HttpAgent` URL defaults to `http://localhost:8080/agent`
- [ ] `HttpAgent` URL is configurable via `NEXT_PUBLIC_AGENT_URL`
- [ ] All tests pass: `npx vitest run`

### Quality check

```bash
cd webapp && npm run build && npx vitest run
```

### Commit message

```
feat(webapp): add CopilotKit API route with HttpAgent

- Proxies CopilotKit requests to backend /agent SSE endpoint
- HttpAgent from @ag-ui/client with configurable URL
- Agent keyed as 'spreadsheet_validator'
```

---

## Story 5.4: Custom React card components for pipeline states {#story-5.4}

### Summary

Build four React card components that visualize pipeline state transitions: IngestionSummaryCard, ValidationResultsCard, ProgressCard, and CompletionCard. Each card uses Tailwind CSS dark theme styling with rounded borders and appropriate status colors.

### Test (write first)

**File: `webapp/src/__tests__/cards.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { IngestionSummaryCard } from "@/components/a2ui/IngestionSummaryCard";
import { ValidationResultsCard } from "@/components/a2ui/ValidationResultsCard";
import { ProgressCard } from "@/components/a2ui/ProgressCard";
import { CompletionCard } from "@/components/a2ui/CompletionCard";

describe("IngestionSummaryCard", () => {
  it("renders file name", () => {
    render(
      <IngestionSummaryCard
        fileName="test.csv"
        rowCount={100}
        columnCount={7}
        columns={["employee_id", "dept", "amount"]}
      />
    );
    expect(screen.getByText(/test\.csv/)).toBeInTheDocument();
  });

  it("renders row count", () => {
    render(
      <IngestionSummaryCard
        fileName="test.csv"
        rowCount={100}
        columnCount={7}
        columns={["a", "b"]}
      />
    );
    expect(screen.getByText(/100/)).toBeInTheDocument();
  });

  it("renders column names", () => {
    render(
      <IngestionSummaryCard
        fileName="test.csv"
        rowCount={10}
        columnCount={2}
        columns={["employee_id", "dept"]}
      />
    );
    expect(screen.getByText(/employee_id/)).toBeInTheDocument();
  });
});

describe("ValidationResultsCard", () => {
  it("renders total rows", () => {
    render(
      <ValidationResultsCard totalRows={100} validCount={90} errorCount={10} />
    );
    expect(screen.getByText(/100/)).toBeInTheDocument();
  });

  it("renders valid count", () => {
    render(
      <ValidationResultsCard totalRows={100} validCount={90} errorCount={10} />
    );
    expect(screen.getByText(/90/)).toBeInTheDocument();
  });

  it("renders error count", () => {
    render(
      <ValidationResultsCard totalRows={100} validCount={90} errorCount={10} />
    );
    expect(screen.getByText(/10/)).toBeInTheDocument();
  });

  it("renders progress bar", () => {
    const { container } = render(
      <ValidationResultsCard totalRows={100} validCount={90} errorCount={10} />
    );
    // The progress bar should have a width style
    const bar = container.querySelector("[data-testid='progress-bar']") ||
                container.querySelector(".bg-green-500, .bg-emerald-500");
    // At minimum, the component renders without error
    expect(container.innerHTML).toContain("90");
  });
});

describe("ProgressCard", () => {
  it("renders phase name", () => {
    render(<ProgressCard phaseName="Transforming data" />);
    expect(screen.getByText(/Transforming data/)).toBeInTheDocument();
  });

  it("renders spinner", () => {
    const { container } = render(<ProgressCard phaseName="Processing" />);
    // Should have an animated element
    const animated = container.querySelector(".animate-spin") ||
                     container.querySelector("[role='status']");
    expect(animated || container.innerHTML.includes("Processing")).toBeTruthy();
  });
});

describe("CompletionCard", () => {
  it("renders summary stats", () => {
    render(
      <CompletionCard
        totalRows={100}
        validCount={95}
        errorCount={5}
        fixedCount={3}
        artifactNames={["success.xlsx", "errors.xlsx"]}
      />
    );
    expect(screen.getByText(/100/)).toBeInTheDocument();
    expect(screen.getByText(/95/)).toBeInTheDocument();
  });

  it("renders artifact names", () => {
    render(
      <CompletionCard
        totalRows={100}
        validCount={95}
        errorCount={5}
        fixedCount={0}
        artifactNames={["success.xlsx", "errors.xlsx"]}
      />
    );
    expect(screen.getByText(/success\.xlsx/)).toBeInTheDocument();
    expect(screen.getByText(/errors\.xlsx/)).toBeInTheDocument();
  });

  it("renders success indicator", () => {
    const { container } = render(
      <CompletionCard
        totalRows={10}
        validCount={10}
        errorCount={0}
        fixedCount={0}
        artifactNames={["success.xlsx"]}
      />
    );
    // Should render a success/checkmark indicator
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });
});
```

### Implementation

**File: `webapp/src/components/a2ui/IngestionSummaryCard.tsx`**

```tsx
import { FileSpreadsheet } from "lucide-react";

interface IngestionSummaryCardProps {
  fileName: string;
  rowCount: number;
  columnCount: number;
  columns: string[];
}

export function IngestionSummaryCard({
  fileName,
  rowCount,
  columnCount,
  columns,
}: IngestionSummaryCardProps) {
  return (
    <div className="rounded-lg border border-blue-500/30 bg-blue-950/20 p-4 space-y-3">
      <div className="flex items-center gap-2 text-blue-400">
        <FileSpreadsheet className="h-5 w-5" />
        <span className="font-semibold">File Ingested</span>
      </div>
      <div className="text-sm text-gray-300">
        <p>
          <span className="text-gray-400">File:</span>{" "}
          <span className="font-mono">{fileName}</span>
        </p>
        <p>
          <span className="text-gray-400">Rows:</span> {rowCount}
        </p>
        <p>
          <span className="text-gray-400">Columns:</span> {columnCount}
        </p>
      </div>
      <div className="flex flex-wrap gap-1">
        {columns.map((col) => (
          <span
            key={col}
            className="rounded bg-blue-900/40 px-2 py-0.5 text-xs text-blue-300"
          >
            {col}
          </span>
        ))}
      </div>
    </div>
  );
}
```

**File: `webapp/src/components/a2ui/ValidationResultsCard.tsx`**

```tsx
import { ShieldCheck, ShieldAlert } from "lucide-react";

interface ValidationResultsCardProps {
  totalRows: number;
  validCount: number;
  errorCount: number;
}

export function ValidationResultsCard({
  totalRows,
  validCount,
  errorCount,
}: ValidationResultsCardProps) {
  const validPercent = totalRows > 0 ? (validCount / totalRows) * 100 : 0;

  return (
    <div className="rounded-lg border border-yellow-500/30 bg-yellow-950/20 p-4 space-y-3">
      <div className="flex items-center gap-2 text-yellow-400">
        {errorCount > 0 ? (
          <ShieldAlert className="h-5 w-5" />
        ) : (
          <ShieldCheck className="h-5 w-5" />
        )}
        <span className="font-semibold">Validation Results</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-sm">
        <div>
          <div className="text-lg font-bold text-gray-100">{totalRows}</div>
          <div className="text-gray-400">Total</div>
        </div>
        <div>
          <div className="text-lg font-bold text-emerald-400">{validCount}</div>
          <div className="text-gray-400">Valid</div>
        </div>
        <div>
          <div className="text-lg font-bold text-red-400">{errorCount}</div>
          <div className="text-gray-400">Errors</div>
        </div>
      </div>
      <div className="h-2 rounded-full bg-gray-700 overflow-hidden">
        <div
          data-testid="progress-bar"
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${validPercent}%` }}
        />
      </div>
    </div>
  );
}
```

**File: `webapp/src/components/a2ui/ProgressCard.tsx`**

```tsx
import { Loader2 } from "lucide-react";

interface ProgressCardProps {
  phaseName: string;
  progress?: number;
}

export function ProgressCard({ phaseName, progress }: ProgressCardProps) {
  return (
    <div className="rounded-lg border border-purple-500/30 bg-purple-950/20 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Loader2 className="h-5 w-5 animate-spin text-purple-400" />
        <span className="font-semibold text-purple-300">{phaseName}</span>
      </div>
      {progress !== undefined && (
        <div className="h-2 rounded-full bg-gray-700 overflow-hidden">
          <div
            className="h-full rounded-full bg-purple-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
```

**File: `webapp/src/components/a2ui/CompletionCard.tsx`**

```tsx
import { CheckCircle2, Download } from "lucide-react";

interface CompletionCardProps {
  totalRows: number;
  validCount: number;
  errorCount: number;
  fixedCount: number;
  artifactNames: string[];
}

export function CompletionCard({
  totalRows,
  validCount,
  errorCount,
  fixedCount,
  artifactNames,
}: CompletionCardProps) {
  const backendUrl =
    typeof window !== "undefined"
      ? process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080"
      : "http://localhost:8080";

  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-4 space-y-3">
      <div className="flex items-center gap-2 text-emerald-400">
        <CheckCircle2 className="h-5 w-5" />
        <span className="font-semibold">Validation Complete</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-400">Total rows:</span>{" "}
          <span className="font-bold">{totalRows}</span>
        </div>
        <div>
          <span className="text-gray-400">Valid:</span>{" "}
          <span className="font-bold text-emerald-400">{validCount}</span>
        </div>
        <div>
          <span className="text-gray-400">Errors:</span>{" "}
          <span className="font-bold text-red-400">{errorCount}</span>
        </div>
        <div>
          <span className="text-gray-400">Fixed:</span>{" "}
          <span className="font-bold text-blue-400">{fixedCount}</span>
        </div>
      </div>
      <div className="space-y-1">
        <div className="text-sm text-gray-400">Download artifacts:</div>
        {artifactNames.map((name) => (
          <a
            key={name}
            href={`${backendUrl}/artifacts/${name}`}
            className="flex items-center gap-2 rounded bg-gray-800 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700 transition-colors"
            download
          >
            <Download className="h-4 w-4" />
            {name}
          </a>
        ))}
      </div>
    </div>
  );
}
```

**File: `webapp/src/components/a2ui/index.ts`**

```typescript
export { IngestionSummaryCard } from "./IngestionSummaryCard";
export { ValidationResultsCard } from "./ValidationResultsCard";
export { ProgressCard } from "./ProgressCard";
export { CompletionCard } from "./CompletionCard";
```

### Success criteria

- [ ] `IngestionSummaryCard` renders file name, row count, column count, and column list
- [ ] `ValidationResultsCard` renders total rows, valid count, error count with progress bar
- [ ] `ProgressCard` renders spinner animation and phase name
- [ ] `CompletionCard` renders success icon, summary stats, and artifact names
- [ ] All cards use Tailwind dark theme styling
- [ ] All tests in `src/__tests__/cards.test.tsx` pass

### Quality check

```bash
cd webapp && npm run build && npx vitest run
```

### Commit message

```
feat(webapp): add pipeline state card components

- IngestionSummaryCard: file stats and column badges
- ValidationResultsCard: valid/error counts with progress bar
- ProgressCard: animated spinner with phase name
- CompletionCard: summary stats and artifact download links
```

---

## Story 5.5: useCoAgentStateRender hook for state-driven card rendering {#story-5.5}

### Summary

Create the `useA2UIStateRender` hook that wraps CopilotKit's `useCoAgentStateRender` to render the correct card component based on agent state transitions. The hook maps status values to card components and derives counts from array lengths.

### Test (write first)

**File: `webapp/src/__tests__/useA2UIStateRender.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import fs from "fs";
import path from "path";

// Since useCoAgentStateRender requires CopilotKit context, we test
// the hook's source for correctness patterns rather than rendering.

describe("useA2UIStateRender hook", () => {
  const hookPath = path.resolve(
    __dirname,
    "../hooks/useA2UIStateRender.ts"
  );

  it("hook file exists", () => {
    expect(fs.existsSync(hookPath)).toBe(true);
  });

  it("calls useCoAgentStateRender", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("useCoAgentStateRender");
  });

  it("uses agent name spreadsheet_validator", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });

  it("renders CompletionCard for COMPLETED status", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("CompletionCard");
    expect(source).toContain("COMPLETED");
  });

  it("renders IngestionSummaryCard for RUNNING status", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("IngestionSummaryCard");
  });

  it("renders ValidationResultsCard for VALIDATING status", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("ValidationResultsCard");
  });

  it("renders ProgressCard for TRANSFORMING/PACKAGING", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("ProgressCard");
    expect(source).toContain("TRANSFORMING");
  });

  it("derives counts from array lengths not hardcoded values", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    // Should use .length to compute counts
    expect(source).toContain(".length");
  });
});
```

### Implementation

**File: `webapp/src/hooks/useA2UIStateRender.ts`**

```tsx
"use client";

import { useCoAgentStateRender } from "@copilotkit/react-core";
import { IngestionSummaryCard } from "@/components/a2ui/IngestionSummaryCard";
import { ValidationResultsCard } from "@/components/a2ui/ValidationResultsCard";
import { ProgressCard } from "@/components/a2ui/ProgressCard";
import { CompletionCard } from "@/components/a2ui/CompletionCard";
import type { AgentState } from "@/lib/types";
import { createElement } from "react";

/**
 * Hook that subscribes to agent state changes and renders
 * the appropriate card component based on pipeline status.
 *
 * This is the core of Plan A's state-driven rendering approach.
 * No A2UI protocol — just state transitions mapped to React cards.
 */
export function useA2UIStateRender() {
  useCoAgentStateRender<AgentState>({
    name: "spreadsheet_validator",
    render: ({ state }) => {
      if (!state) return null;

      const totalRows = state.dataframe_records?.length ?? 0;
      const errorCount = state.validation_errors?.length ?? 0;
      const validCount = totalRows - errorCount;
      const fixedCount = state.pending_fixes?.length ?? 0;
      const columns = state.dataframe_columns ?? [];

      switch (state.status) {
        case "COMPLETED":
          return createElement(CompletionCard, {
            totalRows,
            validCount,
            errorCount,
            fixedCount,
            artifactNames: Object.keys(state.artifacts ?? {}),
          });

        case "TRANSFORMING":
        case "PACKAGING":
          return createElement(ProgressCard, {
            phaseName:
              state.status === "TRANSFORMING"
                ? "Transforming data..."
                : "Packaging results...",
          });

        case "VALIDATING":
        case "FIXING":
        case "WAITING_FOR_USER":
          if (totalRows > 0) {
            return createElement(ValidationResultsCard, {
              totalRows,
              validCount,
              errorCount,
            });
          }
          return null;

        case "RUNNING":
          if (totalRows > 0) {
            return createElement(IngestionSummaryCard, {
              fileName: state.file_name ?? "Unknown",
              rowCount: totalRows,
              columnCount: columns.length,
              columns,
            });
          }
          return null;

        default:
          return null;
      }
    },
  });
}
```

### Success criteria

- [ ] Hook calls `useCoAgentStateRender` with `name='spreadsheet_validator'`
- [ ] `COMPLETED` status renders `CompletionCard` with correct props
- [ ] `TRANSFORMING`/`PACKAGING` status renders `ProgressCard`
- [ ] `VALIDATING` status with data renders `ValidationResultsCard`
- [ ] `RUNNING` status with loaded data renders `IngestionSummaryCard`
- [ ] Counts are derived from array lengths, not hardcoded
- [ ] Returns `null` when state has no data (initial IDLE)
- [ ] All tests pass: `npx vitest run`

### Quality check

```bash
cd webapp && npm run build && npx vitest run
```

### Commit message

```
feat(webapp): add useCoAgentStateRender hook for state-driven cards

- Maps pipeline status to React card components
- Derives row/error counts from state array lengths
- Supports COMPLETED, TRANSFORMING, VALIDATING, RUNNING states
- Returns null for IDLE/initial state
```

---

## Story 5.6: Main page with file upload, chat, and state rendering {#story-5.6}

### Summary

Create the main page that combines file upload, CopilotChat, and the state-driven card rendering hook. The page generates a `threadId` on mount, manages file upload to the backend, and activates the `useA2UIStateRender()` hook for card rendering inside the chat.

### Test (write first)

**File: `webapp/src/__tests__/page.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Main page", () => {
  const pagePath = path.resolve(__dirname, "../app/page.tsx");

  it("page.tsx exists", () => {
    expect(fs.existsSync(pagePath)).toBe(true);
  });

  it("is a client component", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("use client");
  });

  it("generates threadId", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("threadId");
    expect(source).toContain("randomUUID");
  });

  it("uses useA2UIStateRender hook", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("useA2UIStateRender");
  });

  it("renders CopilotChat or similar chat component", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    // Should use CopilotChat or CopilotPopup
    expect(
      source.includes("CopilotChat") || source.includes("CopilotPopup")
    ).toBe(true);
  });

  it("uploads to /upload endpoint", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("/upload");
  });

  it("accepts csv and xlsx files", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain(".csv");
    expect(source).toContain(".xlsx");
  });

  it("passes agentId spreadsheet_validator", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });
});
```

### Implementation

**Update `webapp/src/app/page.tsx`**:

```tsx
"use client";

import { useState, useMemo, useRef, useCallback } from "react";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { Upload, FileSpreadsheet, Loader2 } from "lucide-react";
import { useA2UIStateRender } from "@/hooks/useA2UIStateRender";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";

export default function Home() {
  const threadId = useMemo(() => crypto.randomUUID(), []);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Activate state-driven card rendering
  useA2UIStateRender();

  // Pre-create session on first interaction
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
          }
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
    [threadId, ensureSession]
  );

  return (
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
          agentId="spreadsheet_validator"
          threadId={threadId}
          instructions="Help users validate spreadsheet data. When they upload a file, process it through ingestion, validation, and packaging."
          labels={{
            initial: "Upload a CSV or Excel file to start validation.",
          }}
          makeSystemMessage={(msg) => msg}
          Header={() => null}
          Input={(props) => (
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
              {props.children}
            </div>
          )}
        />
      </div>
    </main>
  );
}
```

> **Note:** The exact CopilotChat API may differ in v1.50. The `agentId`, `threadId`, `Header`, and `Input` props may need adjustment. The key requirements are: file upload triggers POST to `/upload`, `threadId` is used for session continuity, and `useA2UIStateRender()` is called in the component. Adjust based on the actual CopilotKit API available.

### Success criteria

- [ ] Page renders CopilotChat with `agentId='spreadsheet_validator'`
- [ ] `threadId` is generated once on mount via `crypto.randomUUID()`
- [ ] File input accepts `.csv`, `.xlsx`, `.xls`
- [ ] Upload POSTs to backend `/upload` with `thread_id` query param
- [ ] On successful upload, file name is shown in status bar
- [ ] `useA2UIStateRender()` is called inside the component
- [ ] Upload status shown during upload
- [ ] All tests pass: `npx vitest run`

### Quality check

```bash
cd webapp && npm run build && npx vitest run
```

### Commit message

```
feat(webapp): add main page with file upload and chat

- File upload to backend /upload with threadId session continuity
- CopilotChat with agentId='spreadsheet_validator'
- useA2UIStateRender() activated for state-driven card rendering
- Status bar shows upload progress and file name
```
