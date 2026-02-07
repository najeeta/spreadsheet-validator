export function ProcessingSkeleton() {
  return (
    <div className="animate-card-in rounded-lg border border-burgundy-200 bg-white p-6 space-y-5 max-w-xl mx-auto w-full">
      {/* Header skeleton */}
      <div className="flex items-center gap-3">
        <div className="h-5 w-5 rounded bg-burgundy-200 animate-pulse" />
        <div className="h-4 w-40 rounded bg-burgundy-100 animate-pulse" />
      </div>

      {/* Form field 1 — label + full-width input */}
      <div className="space-y-2">
        <div className="h-3 w-24 rounded bg-gray-200 animate-pulse" />
        <div className="h-9 w-full rounded-md bg-gray-100 animate-pulse" />
      </div>

      {/* Form field 2 — label + full-width input */}
      <div className="space-y-2">
        <div className="h-3 w-32 rounded bg-gray-200 animate-pulse" />
        <div className="h-9 w-full rounded-md bg-gray-100 animate-pulse" />
      </div>

      {/* Form field 3 — label + shorter input (select-like) */}
      <div className="space-y-2">
        <div className="h-3 w-20 rounded bg-gray-200 animate-pulse" />
        <div className="h-9 w-2/3 rounded-md bg-gray-100 animate-pulse" />
      </div>

      {/* Two-column row (like paired fields) */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="h-3 w-16 rounded bg-gray-200 animate-pulse" />
          <div className="h-9 w-full rounded-md bg-gray-100 animate-pulse" />
        </div>
        <div className="space-y-2">
          <div className="h-3 w-20 rounded bg-gray-200 animate-pulse" />
          <div className="h-9 w-full rounded-md bg-gray-100 animate-pulse" />
        </div>
      </div>

      {/* Submit button skeleton */}
      <div className="h-10 w-full rounded-lg bg-burgundy-100 animate-pulse" />

      {/* Processing label */}
      <div className="text-center text-xs text-gray-400">
        Analyzing spreadsheet&hellip;
      </div>
    </div>
  );
}
