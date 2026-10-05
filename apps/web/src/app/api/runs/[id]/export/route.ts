import { intelUrl } from "@/lib/intel";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f]{10}$/.test(id)) return new Response("Not found", { status: 404 });
  const res = await fetch(`${intelUrl()}/v1/runs/${id}/export.md`, { cache: "no-store" });
  if (!res.ok) return new Response("Not found", { status: res.status === 409 ? 409 : 404 });
  return new Response(await res.text(), {
    headers: { "content-type": "text/markdown; charset=utf-8", "content-disposition": `attachment; filename="battlecards-${id}.md"` },
  });
}
