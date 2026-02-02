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
