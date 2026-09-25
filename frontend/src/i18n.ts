import english from './locales/en.json';

export const languages = [{ id: 'vi', name: 'Tiếng Việt' }, { id: 'en', name: 'English' }] as const;
export type Language = typeof languages[number]['id'];
let currentLanguage: Language = 'vi';
export const setLanguage = (language: Language) => { currentLanguage = language; document.documentElement.lang = language; };
const dictionaries: Record<string, Record<string, string>> = { en: english };
/** Vietnamese source keys keep existing UI copy readable. Add a dictionary and a language entry to extend. */
export function t(source: string, values?: Record<string, string | number>): string {
  let text = dictionaries[currentLanguage]?.[source] ?? source;
  if (values) for (const [key, value] of Object.entries(values)) text = text.replaceAll(`{${key}}`, String(value));
  return text;
}
