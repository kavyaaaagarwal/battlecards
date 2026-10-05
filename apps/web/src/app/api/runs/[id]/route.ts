import { NextResponse } from "next/server";
import { intel } from "@/lib/intel";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f]{10}$/.test(id)) return NextResponse.json({ error: "Not found" }, { status: 404 });
  const { data } = await intel.GET("/v1/runs/{run_id}", { params: { path: { run_id: id } }, cache: "no-store" });
  if (!data) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(data, { headers: { "cache-control": "no-store" } });
}
