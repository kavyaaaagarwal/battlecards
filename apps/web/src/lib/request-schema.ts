import { z } from "zod";

/** A visitor registering interest in beta access. Nothing runs: it is saved for us to review. */
export const ReportRequest = z.object({
  name: z.string().trim().min(1, "Your name is required").max(80),
  email: z.string().trim().email("Enter a valid work email").max(120),
  company: z.string().trim().min(1, "Your company is required").max(80),
  competitors: z.string().trim().max(300).optional().default(""),
  role: z.string().trim().max(80).optional().default(""),
  note: z.string().trim().max(1000).optional().default(""),
  website: z.string().max(200).optional().default(""), // honeypot: people never see it, bots fill it
});

export type ReportRequestT = z.infer<typeof ReportRequest>;
