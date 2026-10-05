import { z } from "zod";

const Company = z.object({
  name: z.string().trim().min(1, "Company name is required").max(60, "Names must be 60 characters or fewer"),
  domain: z.string().trim().max(100).optional(),
});

export const RunInput = z
  .object({
    company: Company,
    competitors: z.array(Company).min(1, "Add at least one competitor").max(4, "Up to 4 competitors"),
    category: z.string().trim().max(80).optional().default(""),
  })
  .refine(
    (v) => new Set([v.company, ...v.competitors].map((c) => c.name.toLowerCase())).size === v.competitors.length + 1,
    { message: "Company and competitor names must all be different" },
  );

export type RunInputT = z.infer<typeof RunInput>;

const clean = (c: { name: string; domain?: string }) => (c.domain ? { name: c.name, domain: c.domain } : { name: c.name });

export const toIntelBody = (v: RunInputT) => ({
  company: clean(v.company),
  competitors: v.competitors.map(clean),
  category: v.category,
});
