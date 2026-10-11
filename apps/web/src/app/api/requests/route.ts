import { NextResponse } from "next/server";
import { intel } from "@/lib/intel";
import { ReportRequest } from "@/lib/request-schema";

export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Body must be JSON" }, { status: 400 }); }
  const parsed = ReportRequest.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid input" }, { status: 400 });
  const { website, ...lead } = parsed.data;
  if (website) return NextResponse.json({ ok: true }, { status: 202 }); // a bot: pretend it worked, keep nothing

  const { error } = await intel.POST("/v1/requests", { body: lead });
  if (error) return NextResponse.json({ error: "We couldn't save your request. Please try again." }, { status: 502 });
  return NextResponse.json({ ok: true }, { status: 202 });
}
