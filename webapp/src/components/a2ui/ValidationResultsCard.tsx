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
