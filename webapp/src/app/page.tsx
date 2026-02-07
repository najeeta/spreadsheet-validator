import { redirect } from 'next/navigation';

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";

export default async function Home() {
  // Create a new run (session) on the backend
  let runId;
  try {
    const res = await fetch(`${BACKEND_URL}/run`, {
      method: "POST",
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`Failed to create run: ${res.status}`);
    }
    const data = await res.json();
    runId = data.session_id;
  } catch (e) {
    console.error("Failed to create run", e);
    // Fallback? Or shows error page. For now let's just error boundary.
    // Ideally we might want a client component to handle this with better UX,
    // but a server component redirect is cleanest for "Starting..."
    throw e;
  }

  redirect(`/runs/${runId}`);
}
