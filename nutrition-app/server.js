/**
 * Nutrition Food Guide — Local Server
 * ════════════════════════════════════════════════════════════
 * Serves the pre-built React app and proxies ML API requests
 * to the Flask backend. Uses ONLY Node.js built-ins — no npm
 * install required.
 *
 * ──────────────────────────────────────────────────────────
 * QUICK START
 * ──────────────────────────────────────────────────────────
 *
 *  1. Start the Flask ML backend (separate terminal):
 *       cd flask-ml
 *       pip install flask flask-cors scikit-learn pandas
 *       python app.py
 *
 *  2. Start this server:
 *       node server.js
 *
 *  3. Open in your browser:
 *       http://localhost:3000
 *
 * ──────────────────────────────────────────────────────────
 * SERVE WITH APACHE / NGINX INSTEAD
 * ──────────────────────────────────────────────────────────
 *  Point your web server's document root at the  dist/public/
 *  folder inside this package. All files are pre-built static
 *  assets — no compilation needed.
 *
 * ──────────────────────────────────────────────────────────
 * ENV VARS  (all optional)
 * ──────────────────────────────────────────────────────────
 *   PORT        Port for this server          (default: 3000)
 *   FLASK_URL   Flask ML backend base URL     (default: http://localhost:5000)
 */

const http  = require("http");
const https = require("https");
const fs    = require("fs");
const path  = require("path");
const url   = require("url");

const PORT      = parseInt(process.env.PORT || "3000", 10);
const FLASK_URL = (process.env.FLASK_URL || "http://localhost:5000").replace(/\/$/, "");
const DIST_DIR  = path.resolve(__dirname, "dist", "public");

// ── MIME types ───────────────────────────────────────────────────────────────
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js":   "application/javascript",
  ".mjs":  "application/javascript",
  ".css":  "text/css",
  ".json": "application/json",
  ".png":  "image/png",
  ".jpg":  "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif":  "image/gif",
  ".svg":  "image/svg+xml",
  ".ico":  "image/x-icon",
  ".woff": "font/woff",
  ".woff2":"font/woff2",
  ".ttf":  "font/ttf",
  ".webp": "image/webp",
};

// ── Health-check Flask on startup ────────────────────────────────────────────
function checkFlask() {
  const target = new URL("/ml-api/health", FLASK_URL);
  const lib = target.protocol === "https:" ? https : http;
  lib.get(target.href, (res) => {
    let body = "";
    res.on("data", c => body += c);
    res.on("end", () => {
      try {
        const j = JSON.parse(body);
        const acc = j.accuracy != null ? `  accuracy=${(j.accuracy*100).toFixed(1)}%` : "";
        console.log(`  [flask] ✓  model_loaded=${j.model_loaded}${acc}`);
      } catch {
        console.log(`  [flask] ✓  reachable (HTTP ${res.statusCode})`);
      }
    });
  }).on("error", () => {
    console.warn("  [flask] ✗  not reachable on " + FLASK_URL);
    console.warn("  [flask]    Diet predictions will use rule-based fallback.");
  });
}

// ── Proxy /ml-api/* → Flask ──────────────────────────────────────────────────
function proxyToFlask(req, res) {
  const target = new URL(req.url, FLASK_URL);
  const lib    = target.protocol === "https:" ? https : http;
  const opts   = {
    hostname: target.hostname,
    port:     target.port || (target.protocol === "https:" ? 443 : 80),
    path:     target.pathname + (target.search || ""),
    method:   req.method,
    headers:  { ...req.headers, host: target.host },
  };
  const proxy = lib.request(opts, (flaskRes) => {
    res.writeHead(flaskRes.statusCode, flaskRes.headers);
    flaskRes.pipe(res, { end: true });
  });
  proxy.on("error", () => {
    res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ diet: "Balanced Diet" }));
  });
  req.pipe(proxy, { end: true });
}

// ── Serve a static file ──────────────────────────────────────────────────────
function serveFile(res, filePath, status = 200) {
  const ext  = path.extname(filePath).toLowerCase();
  const mime = MIME[ext] || "application/octet-stream";
  res.writeHead(status, {
    "Content-Type":  mime,
    "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=31536000, immutable",
  });
  fs.createReadStream(filePath).pipe(res);
}

// ── Main handler ─────────────────────────────────────────────────────────────
const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(url.parse(req.url).pathname);

  // Proxy ML API calls to Flask
  if (pathname.startsWith("/ml-api")) return proxyToFlask(req, res);

  // Resolve file inside dist/public
  let filePath = path.resolve(DIST_DIR, "." + pathname);

  // Block path traversal
  if (!filePath.startsWith(DIST_DIR)) {
    res.writeHead(403); return res.end("Forbidden");
  }

  // Directory → index.html inside it
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, "index.html");
  }

  if (fs.existsSync(filePath)) return serveFile(res, filePath);

  // SPA fallback — let React Router handle the route
  const index = path.join(DIST_DIR, "index.html");
  if (fs.existsSync(index)) return serveFile(res, index, 200);

  // dist/public missing
  res.writeHead(503, { "Content-Type": "text/html" });
  res.end(`<h2>dist/public not found</h2><p>The pre-built files are missing from this package.</p>`);
});

server.listen(PORT, () => {
  console.log("═══════════════════════════════════════════════");
  console.log("  Nutrition Food Guide");
  console.log(`  Local URL   →  http://localhost:${PORT}`);
  console.log(`  Flask proxy →  ${FLASK_URL}`);
  console.log("═══════════════════════════════════════════════");
  checkFlask();
});
