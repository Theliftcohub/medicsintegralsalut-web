import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const seo = z.object({
  title: z.string(),
  description: z.string().default(''),
  canonical: z.string().optional(),
  robots: z.string().default('index, follow'),
  ogImage: z.string().optional(),
  ogTitle: z.string().optional(),
  ogDescription: z.string().optional(),
});

// Una página = un JSON por idioma (src/content/pages/<lang>/...json)
const pages = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/pages' }),
  schema: z.object({
    path: z.string().regex(/^\/.*\/$|^\/$/, 'path con barra final'),
    lang: z.enum(['es', 'ca', 'en', 'fr', 'ru', 'uk']).default('es'),
    i18nGroup: z.string().optional(),
    seo,
    schema: z.array(z.record(z.string(), z.any())).default([]),
    breadcrumbs: z.array(z.object({ name: z.string(), path: z.string() })).optional(),
    blocks: z.array(z.object({ type: z.string() }).passthrough()),
  }),
});

// Un post = un .md; la ruta original se conserva en `path` (en esta web los posts van en la raíz)
const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    path: z.string(),
    lang: z.enum(['es', 'ca', 'en', 'fr', 'ru', 'uk']).default('es'),
    i18nGroup: z.string().optional(),
    title: z.string(),
    description: z.string().default(''),
    date: z.coerce.date(),
    modified: z.coerce.date().optional(),
    author: z.string(),
    authorUrl: z.string().optional(),
    category: z.string().optional(),
    image: z.string().optional(),
    imageAlt: z.string().default(''),
    canonical: z.string().optional(),
    robots: z.string().default('index, follow'),
    h1: z.string().optional(),
  }),
});

export const collections = { pages, posts };
