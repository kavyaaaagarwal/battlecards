import "server-only";
import createClient from "openapi-fetch";
import type { paths } from "./intel-api";

/** On Vercel INTEL_URL comes from the Services binding; locally it's the uvicorn server. */
export const intelUrl = () => process.env.INTEL_URL ?? "http://127.0.0.1:8000";

export const intel = createClient<paths>({ baseUrl: intelUrl() });
