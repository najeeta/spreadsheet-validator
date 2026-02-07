import { Loader2 } from "lucide-react";

interface ProgressCardProps {
  phaseName: string;
  progress?: number;
}

export function ProgressCard({ phaseName, progress }: ProgressCardProps) {
  return (
    <div className="animate-card-in rounded-lg border border-burgundy-200 bg-burgundy-50 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Loader2 className="h-5 w-5 animate-spin text-burgundy-600" />
        <span className="font-semibold text-burgundy-700">{phaseName}</span>
      </div>
      {progress !== undefined && (
        <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
          <div
            className="h-full rounded-full bg-burgundy-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
