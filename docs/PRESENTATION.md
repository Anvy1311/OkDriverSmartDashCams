# Browser Presentation Notes

The dashboard is deliberately dependency-light: FastAPI serves the HTML, CSS, and JavaScript in `static/`, while Leaflet is loaded from a pinned CDN version. There is no Node build step for the prototype.

For a production frontend, the same API contract can be moved into React, Vue, or Next.js. Recommended production changes are code-splitting the map, server-side rendering for the shell, a component library, automated accessibility tests, a CSP with a pinned Leaflet tile policy, and a build pipeline with dependency scanning.

The near-live feed tiles request authenticated SVG frames from the backend and refresh periodically. A production media gateway should replace those image requests with signed WebRTC/HLS sessions and should not expose raw RTSP credentials to the browser.
