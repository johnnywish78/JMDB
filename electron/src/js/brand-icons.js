/** Brand icons for the four registered services — official colorful marks.
 *
 * First-party SVG renditions of each service's official icon, drawn with the
 * services' official brand colors (NOT currentColor): YouTube red #FF0000,
 * Telegram blue #229ED9, Spotify green #1DB954, TV Time blue #104D9C
 * (brand color per TV Time's brand palette). Rendered as REAL elements via
 * innerHTML on a span — never passed as strings to el() children (that is
 * what prints raw markup on screen).
 */

const BRAND_PATHS = {
  // YouTube: red rounded screen + white play triangle (official mark)
  youtube: `<rect x="1.5" y="4.5" width="21" height="15" rx="4.2" fill="#FF0000"/><path d="M10 9.1v5.8l5-2.9z" fill="#ffffff"/>`,
  // Telegram: official blue circle + white paper plane
  telegram: `<circle cx="12" cy="12" r="10" fill="#229ED9"/><path d="M17.9 7.4 4.9 12.5c-.6.2-.6 1.1.05 1.3l3.2 1 1.2 3.7c.15.5.75.6 1.1.25l1.8-1.7 3.3 2.4c.45.35 1.1.1 1.2-.5l2.2-10.3c.1-.65-.55-1.15-1.15-.9zM8.6 14.1l8.3-5.1-6.6 5.6-.25 2.3z" fill="#ffffff"/>`,
  // Spotify: official green circle + black sound waves
  spotify: `<circle cx="12" cy="12" r="10" fill="#1DB954"/><path d="M7.4 9.5c3.1-.95 6.6-.7 9.5.85.4.2.45.75.1 1-.3.25-.75.3-1.1.1-2.4-1.3-5.4-1.5-8.1-.7-.4.1-.85-.05-1-.45-.15-.4.05-.7.6-.8zM8 12.6c2.5-.75 5.2-.5 7.5.75.35.2.45.65.25 1s-.65.45-1 .25c-1.95-1.1-4.3-1.3-6.4-.65-.4.1-.8-.1-.9-.5-.1-.4.15-.75.55-.85zM8.6 15.6c1.9-.55 3.9-.35 5.6.6.3.2.4.55.25.85s-.5.4-.8.25c-1.45-.8-3.1-.95-4.7-.5-.35.1-.7-.05-.8-.4-.1-.35.1-.7.45-.8z" fill="#191414"/>`,
  // TV Time: official brand blue (#104D9C) rounded square + white TV with
  // the tracking checkmark (their mark)
  tv_time: `<rect x="1.5" y="1.5" width="21" height="21" rx="5" fill="#104D9C"/><path d="M8.2 4.8 12 8.6l3.8-3.8c.4-.4 1-.4 1.4 0 .4.4.4 1 0 1.4L14 9.4h2.4c1 0 1.8.8 1.8 1.8v6c0 1-.8 1.8-1.8 1.8H7.6c-1 0-1.8-.8-1.8-1.8v-6c0-1 .8-1.8 1.8-1.8H10L6.8 6.2c-.4-.4-.4-1 0-1.4.4-.4 1-.4 1.4 0z" fill="#ffffff"/><path d="m9.4 14.3 1.9 1.9 3.6-3.9" fill="none" stroke="#104D9C" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>`,
};

/** Brand colors for hover/glow accents in the service grid. */
export const BRAND_COLORS = {
  youtube: "#FF0000",
  telegram: "#229ED9",
  spotify: "#1DB954",
  tv_time: "#104D9C",
};

/** A span containing the official-color brand SVG for a service id (or null). */
export function brandIcon(serviceId, cls = "brand-icon") {
  const paths = BRAND_PATHS[serviceId];
  if (!paths) return null;
  const span = document.createElement("span");
  span.className = cls;
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="none">${paths}</svg>`;
  return span;
}

export const BRAND_IDS = Object.keys(BRAND_PATHS);
