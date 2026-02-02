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
