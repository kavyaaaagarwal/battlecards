import { NextResponse } from "next/server";
import { intel } from "@/lib/intel";
import { RunInput, toIntelBody } from "@/lib/run-schema";

const detail = (e: unknown): string => {
  const d = (e as { detail?: unknown })?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg).replace(/^Value error, /, "");
  return "Something went wrong starting the research run.";
};

export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Body must be JSON" }, { status: 400 }); }
  const parsed = RunInput.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid input" }, { status: 400 });

  const { data, error, response } = await intel.POST("/v1/runs", { body: toIntelBody(parsed.data) });
  if (error || !data) {
    const status = response.status === 422 ? 400 : response.status;
    return NextResponse.json({ error: detail(error) }, { status });
  }
  return NextResponse.json(data, { status: 202 });
}
