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
