// Mint Kiri License token fixtures for the Python verifier's tests.
//
// Run from the kiri-license checkout (it needs that repo's src/token.js):
//   node tools/make_license_token_fixtures.mjs
//
// The output is pasted into tests/test_license_token.py. Signing here — with
// the Worker's own token.js — means the Python verifier is tested against
// real WebCrypto ECDSA P-256 signatures rather than tokens this test suite
// made up, which is the only way a format mismatch can be caught.

import { webcrypto } from "node:crypto";
import { writeFileSync } from "node:fs";

import { base64UrlEncode, signEntitlement } from "../src/token.js";

if (!globalThis.crypto) globalThis.crypto = webcrypto;

const APP = "ng.kiri.ktvplayer";
const base = {
  iss: "license.kiri.ng",
  v: 1,
  ent: "fixture-entitlement",
  app: APP,
  product: "lifetime",
  scope: "universal",
  mode: "one_time",
  status: "active",
  paid_through: null,
  iat: 1758600000,
  exp: null,
};

const pair = await crypto.subtle.generateKey(
  { name: "ECDSA", namedCurve: "P-256" },
  true,
  ["sign", "verify"],
);
const privateKey = await crypto.subtle.exportKey("pkcs8", pair.privateKey);
const publicKey = new Uint8Array(await crypto.subtle.exportKey("spki", pair.publicKey));

const tokens = {};
for (const [name, overrides] of Object.entries({
  LIFETIME: {},
  YEARLY_ACTIVE: {
    product: "yearly",
    mode: "recurring",
    status: "active",
    paid_through: 1790000000000,
    exp: 1790000000,
  },
  EXPIRED: { status: "expired", exp: 1700000000 },
  REVOKED: { status: "revoked", exp: null },
  GRACE: { status: "grace", exp: 1790000000 },
  WRONG_APP: { app: "com.someone.else" },
  BAD_ISSUER: { iss: "evil.example" },
  UNSUPPORTED_VERSION: { v: 2 },
  EXPIRING_SOON: { exp: 1758600060 },
})) {
  tokens[name] = await signEntitlement({ ...base, ...overrides }, privateKey);
}

const out = `"""Token fixtures minted by tools/make_license_token_fixtures.mjs.

Regenerate with that script (it uses the license Worker's own token.js) if
the token format ever changes. The key pair is throwaway and exists only to
prove the Python verifier accepts real WebCrypto signatures.
"""

PUBLIC_KEY = "{${base64UrlEncode(publicKey)}}"

TOKENS = {${Object.entries(tokens)
  .map(([name, token]) => `    "${name}": "${token}",`)
  .join("\n")}}
`;

writeFileSync(new URL("../tests/license_fixtures.py", import.meta.url), out, "utf8");
console.log("wrote tests/license_fixtures.py");
console.log(out.split("\n").slice(0, 4).join("\n"));
