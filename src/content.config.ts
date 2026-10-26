import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Wiki pages whose facts come from cg-facts. Each entry is the page as
// written, with every figure replaced by a {{fact:ID}} token. src/lib/facts.ts
// binds the tokens at build time and fails the build on a missing id or on a
// figure typed straight into the text.
const wiki = defineCollection({
  loader: glob({ pattern: '*.json', base: './src/content/wiki' }),
  schema: z.object({
    path: z.string().regex(/^[a-z0-9-]+(\/[a-z0-9-]+)*$/),
    kind: z.enum(['person', 'project']),
    subject: z.string(),
    head: z.string().min(1),
    body: z.string().min(1),
  }),
});

export const collections = { wiki };
