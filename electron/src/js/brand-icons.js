/** Brand icons for the four registered services.
 *
 * Simple first-party SVG renditions of each service's mark, drawn with the
 * app's 24×24 icon conventions (currentColor, stroke-based where possible)
 * so they match the design language and theme. Rendered as REAL elements
 * via innerHTML on a span — never passed as strings to el() children (that
 * is what prints raw markup on screen).
 */

const BRAND_PATHS = {
  // YouTube: rounded screen + play triangle
  youtube: `<rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/><path d="M10 9.2v5.6l5-2.8z" fill="currentColor" stroke="none"/>`,
  // Telegram: paper plane
  telegram: `<path d="M21 4.5 2.8 11.2c-.8.3-.8 1.4 0 1.7l4.6 1.6 1.7 5c.2.7 1.1.8 1.6.3l2.6-2.5 4.6 3.4c.6.4 1.5.1 1.6-.7L22.6 5.6c.1-.9-.7-1.5-1.6-1.1z"/><path d="M7.4 14.5 20.5 6.4l-9.8 8.4-.4 3.6"/>`,
  // Spotify: circle + three ascending arcs
  spotify: `<circle cx="12" cy="12" r="9"/><path d="M8 9.7c2.6-.8 5.5-.6 8 .7M8.5 12.7c2.1-.6 4.4-.4 6.3.7M9 15.5c1.6-.4 3.3-.3 4.7.5"/>`,
  // TV Time: a TV set with a check (their tracking mark)
  tv_time: `<rect x="3" y="7" width="18" height="13" rx="2.5"/><path d="M8.5 3.5 12 7l3.5-3.5"/><path d="M8.6 13.6l2.3 2.3 4.5-4.8"/>`,
};

/** A span containing the brand SVG for a service id (or null if unknown). */
export function brandIcon(serviceId, cls = "brand-icon") {
  const paths = BRAND_PATHS[serviceId];
  if (!paths) return null;
  const span = document.createElement("span");
  span.className = cls;
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
  return span;
}

export const BRAND_IDS = Object.keys(BRAND_PATHS);
