import { CheckCircle2, FileSpreadsheet, UploadCloud } from "lucide-react";
import { useValidator } from "@/contexts/ValidatorContext";
import { DEFAULT_INITIAL_STATE } from "@/lib/types";

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

  const { triggerUpload, setAgentState } = useValidator();

  const handleReUpload = () => {
    setAgentState((prev) => ({
      ...(prev ?? DEFAULT_INITIAL_STATE),
      status: "IDLE",
      file_name: null,
      dataframe_records: [],
      dataframe_columns: [],
      pending_fixes: [],
      skipped_fixes: [],
      artifacts: {},
      validation_complete: false,
      total_error_rows: 0,
      waiting_since: undefined,
    }));
    triggerUpload();
  };

  return (
    <div className="animate-card-in rounded-lg border border-gray-300 bg-white p-8 mx-auto my-6 max-w-md space-y-4">
      <div className="flex items-center gap-2 text-emerald-700">
        <CheckCircle2 className="h-5 w-5" />
        <span className="font-semibold">Validation Complete</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-500">Total rows:</span>{" "}
          <span className="font-bold">{totalRows}</span>
        </div>
        <div>
          <span className="text-gray-500">Valid:</span>{" "}
          <span className="font-bold text-emerald-600">{validCount}</span>
        </div>
        <div>
          <span className="text-gray-500">Errors:</span>{" "}
          <span className="font-bold text-red-600">{errorCount}</span>
        </div>
        <div>
          <span className="text-gray-500">Fixed:</span>{" "}
          <span className="font-bold text-burgundy-700">{fixedCount}</span>
        </div>
      </div>
      <div className="space-y-2">
        <div className="text-sm text-gray-500">Download artifacts:</div>
        <div className="flex gap-4">
          {artifactNames.map((name) => (
            <a
              key={name}
              href={`${backendUrl}/artifacts/${name}`}
              className="flex flex-col items-center gap-1 p-3 rounded-lg bg-white border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-colors cursor-pointer"
              download
            >
              <FileSpreadsheet className="h-10 w-10 text-gray-400" />
              <span className="text-xs text-gray-600 text-center">{name}</span>
            </a>
          ))}
        </div>
      </div>
      <div className="pt-3 border-t border-gray-200">
        <button
          onClick={handleReUpload}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#800020] rounded-lg hover:bg-[#6b001a] transition-colors"
        >
          <UploadCloud className="h-4 w-4" />
          Upload Another File
        </button>
        <p className="mt-1 text-xs text-gray-500">
          {errorCount > 0
            ? "Download errors.xlsx, fix the rows, then re-upload for re-validation."
            : "Validate another spreadsheet."}
        </p>
      </div>
    </div>
  );
}
