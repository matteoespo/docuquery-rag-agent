import { documentFileUrl } from '@/services/api';
import type { Source } from '@/types';

// Same format the backend asks the model for: [Source: <file>, Page: <page>] or [Source: <url>]
const CITATION_RE = /\[Source:\s*([^,\]]+?)\s*(?:,\s*Page:\s*([^\]]+?))?\s*\]/gi;

/** Models often rewrite file names (e.g. collapse a double space): compare loosely. */
const norm = (s: string) => s.toLowerCase().replace(/\s+/g, '');
const baseName = (s: string) => s.split(/[\\/]/).pop() ?? s;
const isUrl = (s: string) => /^https?:\/\//i.test(s);

function hostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export const sourceKey = (s: Source) => `${s.source}|${s.page ?? ''}`;

/** The retrieved source a citation refers to, if any (citations to anything else aren't trusted). */
function matchSource(cited: string, page: string | undefined, sources: Source[]): Source | undefined {
  if (isUrl(cited)) return sources.find((s) => s.url === cited);
  const name = norm(baseName(cited));
  const sameFile = sources.filter((s) => !s.url && norm(s.source) === name);
  const firstPage = page?.match(/\d+/)?.[0];
  return sameFile.find((s) => String(s.page) === firstPage) ?? sameFile[0];
}

function sourceUrl(source: Source, page?: string): string {
  if (source.url) return source.url;
  return documentFileUrl(source.source, page?.match(/\d+/)?.[0] ?? source.page);
}

/** Keys of the retrieved sources the answer actually cites. */
export function citedSourceKeys(content: string, sources: Source[]): Set<string> {
  const keys = new Set<string>();
  for (const [, cited, page] of content.matchAll(CITATION_RE)) {
    const source = matchSource(cited, page, sources);
    if (source) keys.add(sourceKey(source));
  }
  return keys;
}

/** Turn citations of retrieved sources into markdown links that open the PDF at the page. */
export function linkifyCitations(content: string, sources: Source[]): string {
  if (!sources.length) return content;
  return content.replace(CITATION_RE, (match, cited: string, page?: string) => {
    const source = matchSource(cited, page, sources);
    if (!source) return match;
    const label = source.url
      ? hostname(source.url)
      : `${source.source}${page ? `, p. ${page}` : source.page ? `, p. ${source.page}` : ''}`;
    // <...> lets the URL contain spaces and parentheses; brackets in the label are escaped.
    return `[${label.replace(/[[\]]/g, '\\$&')}](<${sourceUrl(source, page)}>)`;
  });
}

export function sourceHref(source: Source): string {
  return sourceUrl(source);
}

export function sourceLabel(source: Source): string {
  if (source.url) return hostname(source.url);
  return source.page ? `${source.source}, p. ${source.page}` : source.source;
}
