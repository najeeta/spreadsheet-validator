"use client";

import { Upload } from "lucide-react";
import { useValidator } from "@/contexts/ValidatorContext";

export function UploadCard() {
  const { triggerUpload } = useValidator();

  return (
    <div className="animate-card-in rounded-lg border border-burgundy-200 bg-burgundy-50 p-4 space-y-3">
      <div className="flex items-center gap-2 text-burgundy-700">
        <Upload className="h-5 w-5" />
        <span className="font-semibold">File Upload Required</span>
      </div>
      <p className="text-sm text-gray-600">
        Upload a CSV or Excel spreadsheet to begin validation.
      </p>
      <button
        onClick={triggerUpload}
        className="flex items-center gap-2 rounded-lg bg-burgundy-800 px-4 py-2 text-sm font-medium text-white hover:bg-burgundy-700 transition-colors"
      >
        <Upload className="h-4 w-4" />
        Choose File
      </button>
    </div>
  );
}
