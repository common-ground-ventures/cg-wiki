// Fact binding for wiki pages. The only source of a figure, title or name on
// a fact-bound page is src/data/cg-facts/registry.json, the slice of the
// cg-facts export this site prints (written by the cg-facts publish step,
// never by hand).
import registry from '../data/cg-facts/registry.json';

type Fact = { value: string; subject: string; rows: string[]; surface: string; source?: string };
const facts = registry as Record<string, Fact>;

const TOKEN = /\{\{(fact|fact-json|cited):([^}]+)\}\}/g;

// A figure is a dollar amount, a percent, or a number followed by a counted
// noun. Keep this list in step with tools/migrate_pilot.py.
const NOUNS =
  'projects?|years?|homes|condominiums|stores|doors|people|employees|clients|units|pages|rooms|sites|agents|tools|skills|elements|citations|findings|cities|countries|states|offices|practices|locations|deals|companies|brands|SKUs|styles|accounts|athletes|events|markets|parking stalls|stalls|SF|square feet|days|weeks|months|hours|percent|times|stars|reviews|members|partners|properties|buildings|acres|beds|keys|miles|students|kids|families|volunteers|teams|leagues|games|jobs|trades|subcontractors|bids|sheets|drawings|line items|items|workflows|apps|users|visits|views|followers';
const NUM = String.raw`(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?`;
const FIGURE = new RegExp(
  String.raw`\$\s?${NUM}(?:\s?(?:K|M|B|MM)\b|\s(?:thousand|million|billion)\b)?(?:\+|-plus)?` +
    String.raw`|\b${NUM}\s?%` +
    String.raw`|\b${NUM}\+?\s+(?:${NOUNS})\b`,
  'g',
);
const YEARISH = /^(?:19|20)\d\d\s/;

export class FactError extends Error {}

export function has(id: string): boolean {
  return id in facts;
}

export function fact(id: string, where: string): string {
  const f = facts[id];
  if (!f) throw new FactError(`cg-facts: ${where} cites fact "${id}", which the export does not have.`);
  return f.value;
}

const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');

/** Fail the build when a figure sits in the template outside a token. */
export function lint(template: string, where: string): void {
  const text = template
    .replace(TOKEN, ' ')
    .replace(/\s(?:href|src|srcset)="[^"]*"/g, ' ')
    .replace(/<link\b[^>]*>/g, ' ')
    .replace(/https?:\/\/[^\s"<]+/g, ' ');
  const found: string[] = [];
  for (const m of text.matchAll(FIGURE)) {
    if (YEARISH.test(m[0]) && !m[0].startsWith('$')) continue;
    found.push(m[0]);
  }
  if (found.length) {
    throw new FactError(
      `cg-facts: ${where} has ${found.length} figure(s) typed into the page instead of cited by fact id: ` +
        found.map((f) => JSON.stringify(f)).join(', ') +
        '. Add the fact to cg-facts with its source row and cite it as {{fact:ID}}.',
    );
  }
}

/** Replace every token with its fact value, escaped for where it sits. */
export function bind(template: string, where: string): string {
  return template.replace(TOKEN, (_, kind: string, arg: string) => {
    if (kind === 'cited') return arg; // a third-party figure, cited on the page
    const value = fact(arg, where);
    return kind === 'fact-json' ? JSON.stringify(value).slice(1, -1) : escapeHtml(value);
  });
}

export function personFact(slug: string, field: string, where: string): string {
  return fact(`person.${slug}.${field}`, where);
}
