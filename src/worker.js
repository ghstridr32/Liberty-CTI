const ACCESS_COOKIE = "lcti_atb_access";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 180;
const FULL_BRIEF_RE = /^\/atb\/2026\/\d{2}-\d{2}-\d{4}\/full(?:\.html)?\/?$/;
const CANONICAL_ISSUE_RE = /^\/atb\/issues\/\d{2}-\d{2}-\d{4}(?:\.html)?\/?$/;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/api/atb/register") {
      return handleRegister(request, env);
    }

    if (request.method === "POST" && url.pathname === "/api/atb/login") {
      return handleLogin(request, env);
    }

    if (request.method === "POST" && url.pathname === "/api/atb/logout") {
      return handleLogout();
    }

    if (request.method === "GET" && url.pathname === "/api/atb/status") {
      const session = await readSession(request, env);
      return json({ registered: Boolean(session), emailHash: session?.emailHash || null });
    }

    if (
      (request.method === "GET" || request.method === "HEAD") &&
      (FULL_BRIEF_RE.test(url.pathname) || CANONICAL_ISSUE_RE.test(url.pathname))
    ) {
      const session = await readSession(request, env);
      if (!session) {
        const next = encodeURIComponent(url.pathname + url.search);
        return redirect(`/members/subscribe.html?next=${next}`);
      }
    }

    return env.ASSETS.fetch(request);
  },
};

async function handleRegister(request, env) {
  const form = await readBody(request);
  const next = safeNext(form.next);

  if (!env.ATB_REGISTRATIONS) {
    return problem(request, "Registration storage is not configured yet.", 503);
  }
  if (!hasSessionSecret(env, request)) {
    return problem(request, "Registration signing is not configured yet.", 503);
  }

  if (String(form.website || "").trim() !== "") {
    return problem(request, "Registration could not be accepted.", 400);
  }

  const email = normalizeEmail(form.email);
  const fullName = cleanText(form.fullName, 120);
  const organization = cleanText(form.organization, 160);
  const role = cleanText(form.role, 140);
  const sector = cleanText(form.sector, 80);
  const updates = form.updates === "on" || form.updates === "true" || form.updates === true;
  const consent = form.consent === "on" || form.consent === "true" || form.consent === true;

  if (!fullName || fullName.length < 2) {
    return problem(request, "Enter your name.", 400, { field: "fullName" });
  }
  if (!isEmail(email)) {
    return problem(request, "Enter a valid work email address.", 400, { field: "email" });
  }
  if (!organization) {
    return problem(request, "Enter your organization.", 400, { field: "organization" });
  }
  if (!consent) {
    return problem(request, "Confirm the access terms to continue.", 400, { field: "consent" });
  }

  const emailHash = await sha256Hex(email);
  const now = new Date().toISOString();
  const existing = await env.ATB_REGISTRATIONS.get(registrantKey(emailHash), "json");
  const record = {
    email,
    emailHash,
    fullName,
    organization,
    role,
    sector,
    updates,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    lastLoginAt: now,
    registrationPath: safePath(new URL(request.url).pathname),
    referrer: cleanText(request.headers.get("Referer") || "", 500),
  };

  await env.ATB_REGISTRATIONS.put(registrantKey(emailHash), JSON.stringify(record));

  const token = await signSession({ emailHash, exp: Math.floor(Date.now() / 1000) + COOKIE_MAX_AGE }, env, request);
  const headers = authHeaders(token);
  if (wantsHtml(request)) {
    headers.set("Location", next);
    return new Response(null, { status: 303, headers });
  }

  return json({ ok: true, next }, 200, headers);
}

async function handleLogin(request, env) {
  const form = await readBody(request);
  const next = safeNext(form.next);

  if (!env.ATB_REGISTRATIONS) {
    return problem(request, "Registration storage is not configured yet.", 503);
  }
  if (!hasSessionSecret(env, request)) {
    return problem(request, "Registration signing is not configured yet.", 503);
  }

  const email = normalizeEmail(form.email);
  if (!isEmail(email)) {
    return problem(request, "Enter a valid email address.", 400, { field: "email" });
  }

  const emailHash = await sha256Hex(email);
  const existing = await env.ATB_REGISTRATIONS.get(registrantKey(emailHash), "json");
  if (!existing) {
    return problem(request, "That email is not registered for ATB access yet.", 404, { field: "email" });
  }

  existing.lastLoginAt = new Date().toISOString();
  await env.ATB_REGISTRATIONS.put(registrantKey(emailHash), JSON.stringify(existing));

  const token = await signSession({ emailHash, exp: Math.floor(Date.now() / 1000) + COOKIE_MAX_AGE }, env, request);
  const headers = authHeaders(token);
  if (wantsHtml(request)) {
    headers.set("Location", next);
    return new Response(null, { status: 303, headers });
  }

  return json({ ok: true, next }, 200, headers);
}

function handleLogout() {
  const headers = new Headers();
  headers.set(
    "Set-Cookie",
    `${ACCESS_COOKIE}=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax`
  );
  return json({ ok: true }, 200, headers);
}

async function readSession(request, env) {
  const token = parseCookies(request.headers.get("Cookie") || "")[ACCESS_COOKIE];
  if (!token) return null;

  const payload = await verifySession(token, env, request);
  if (!payload || payload.exp < Math.floor(Date.now() / 1000)) return null;

  if (env.ATB_REGISTRATIONS) {
    const record = await env.ATB_REGISTRATIONS.get(registrantKey(payload.emailHash), "json");
    if (!record) return null;
  }

  return payload;
}

async function readBody(request) {
  const contentType = request.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return request.json();
  }

  const formData = await request.formData();
  return Object.fromEntries(formData.entries());
}

function authHeaders(token) {
  const headers = new Headers();
  headers.set(
    "Set-Cookie",
    `${ACCESS_COOKIE}=${token}; Max-Age=${COOKIE_MAX_AGE}; Path=/; HttpOnly; Secure; SameSite=Lax`
  );
  return headers;
}

function json(body, status = 200, headers = new Headers()) {
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "no-store");
  return new Response(JSON.stringify(body), { status, headers });
}

function problem(request, message, status, extra = {}) {
  if (wantsHtml(request)) {
    return new Response(message, {
      status,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  return json({ ok: false, error: message, ...extra }, status);
}

function redirect(location) {
  return new Response(null, {
    status: 302,
    headers: {
      Location: location,
      "Cache-Control": "no-store",
    },
  });
}

function wantsHtml(request) {
  const accept = request.headers.get("Accept") || "";
  return accept.includes("text/html") && !accept.includes("application/json");
}

function normalizeEmail(email) {
  return String(email || "").trim().toLowerCase();
}

function cleanText(value, maxLength) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function isEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 254;
}

function registrantKey(emailHash) {
  return `registrant:${emailHash}`;
}

function safeNext(next) {
  const value = String(next || "/atb/index.html").trim();
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\") || value.includes("\n")) {
    return "/atb/index.html";
  }
  return value;
}

function safePath(path) {
  return String(path || "").replace(/[^\w./-]/g, "").slice(0, 200);
}

function parseCookies(cookieHeader) {
  const cookies = {};
  for (const part of cookieHeader.split(";")) {
    const [rawName, ...rawValue] = part.trim().split("=");
    if (!rawName) continue;
    cookies[rawName] = rawValue.join("=");
  }
  return cookies;
}

async function signSession(payload, env, request) {
  const encodedPayload = base64urlEncode(JSON.stringify(payload));
  const signature = await hmac(encodedPayload, sessionSecret(env, request));
  return `${encodedPayload}.${base64urlEncode(signature)}`;
}

async function verifySession(token, env, request) {
  const parts = token.split(".");
  if (parts.length !== 2) return null;

  const [encodedPayload, encodedSignature] = parts;
  if (!hasSessionSecret(env, request)) return null;
  const expected = await hmac(encodedPayload, sessionSecret(env, request));
  const actual = base64urlDecode(encodedSignature);
  if (!constantTimeEqual(expected, actual)) return null;

  try {
    return JSON.parse(base64urlDecodeToString(encodedPayload));
  } catch {
    return null;
  }
}

function hasSessionSecret(env, request) {
  return Boolean(env.REGISTRATION_SECRET) || isLocalRequest(request);
}

function sessionSecret(env, request) {
  if (env.REGISTRATION_SECRET) return env.REGISTRATION_SECRET;
  if (isLocalRequest(request)) return "local-development-registration-secret";
  throw new Error("REGISTRATION_SECRET is required outside local development");
}

function isLocalRequest(request) {
  const hostname = new URL(request.url).hostname;
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

async function hmac(value, secret) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)));
}

async function sha256Hex(value) {
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
  return Array.from(hash, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function base64urlEncode(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64urlDecode(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function base64urlDecodeToString(value) {
  return new TextDecoder().decode(base64urlDecode(value));
}

function constantTimeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a[i] ^ b[i];
  return diff === 0;
}
