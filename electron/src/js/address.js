/** Address-bar input resolution for the Browser Hub.
 *
 * Pure logic (no DOM) so it is unit-tested by electron/test/address.test.mjs:
 * explicit URLs and bare domains pass through; anything else becomes a
 * search URL built with the CONFIGURED engine. */

export const SEARCH_ENGINES = {
  duckduckgo: "https://duckduckgo.com/?q=",
  google: "https://www.google.com/search?q=",
  bing: "https://www.bing.com/search?q=",
  brave: "https://search.brave.com/search?q=",
  startpage: "https://www.startpage.com/sp/search?query=",
};

export function resolveAddressInput(input, engineUrl) {
  const engine = engineUrl || SEARCH_ENGINES.duckduckgo;
  const text = String(input || "").trim();
  if (!text) return engine;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) return text; // explicit scheme
  if (text.startsWith("localhost")) return `http://${text}`;
  if (/^[\w-]+(\.[\w-]+)+([/:?#].*)?$/i.test(text)) return `https://${text}`; // domain.tld
  return engine + encodeURIComponent(text);
}
