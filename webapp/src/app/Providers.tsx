"use client";

import { CopilotKit as CopilotKitProvider } from "@copilotkit/react-core";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit">
      {children}
    </CopilotKitProvider>
  );
}
