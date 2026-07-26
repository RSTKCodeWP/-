#!/usr/bin/env node
// Generate the RS256 keypair Convex Auth (the Password provider) needs.
//
// Mission Control's optional cloud backend signs and verifies session JWTs
// with RS256. A self-hosted Convex deployment needs three environment
// variables set ON THE BACKEND for password sign-in to work:
//
//   JWT_PRIVATE_KEY  PKCS#8 PEM private key (newlines collapsed to spaces)
//   JWKS             public key as a JSON Web Key Set, { "keys": [ ... ] }
//   SITE_URL         the public origin the GCS is served from
//
// Run it:
//   node scripts/generate-auth-keys.mjs
//
// The output format is byte-for-byte what `npx @convex-dev/auth` would set,
// so the keys interoperate with the auth runtime exactly.
//
// IMPORTANT for self-hosted Convex: set these on YOUR backend, not the
// managed cloud. Target your own URL + admin key, or the keys land on the
// wrong deployment and password sign-in fails with no obvious error:
//
//   npx convex env set JWT_PRIVATE_KEY "$JWT_PRIVATE_KEY" \
//     --url http://localhost:3210 --admin-key <your-admin-key>
//   npx convex env set JWKS "$JWKS" \
//     --url http://localhost:3210 --admin-key <your-admin-key>
//   npx convex env set SITE_URL "http://localhost:4000" \
//     --url http://localhost:3210 --admin-key <your-admin-key>

import { exportJWK, exportPKCS8, generateKeyPair } from "jose";

const keys = await generateKeyPair("RS256", { extractable: true });
const privateKey = await exportPKCS8(keys.privateKey);
const publicKey = await exportJWK(keys.publicKey);

// Match the upstream encoding exactly: PKCS#8 PEM with newlines replaced by
// spaces so the value survives a single-line environment variable.
const JWT_PRIVATE_KEY = privateKey.trimEnd().replace(/\n/g, " ");
const JWKS = JSON.stringify({ keys: [{ use: "sig", ...publicKey }] });

console.log("# Convex Auth keys. Set these on your Convex backend.");
console.log("#");
console.log("# Self-hosted Convex: target your own backend URL + admin key,");
console.log("# e.g. --url http://localhost:3210 --admin-key <your-admin-key>");
console.log("# (the backend cloud-API origin, port 3210), or sign-in fails silently.");
console.log("");
console.log(`JWT_PRIVATE_KEY="${JWT_PRIVATE_KEY}"`);
console.log("");
console.log(`JWKS='${JWKS}'`);
console.log("");
console.log("# SITE_URL is the public origin the GCS is served from, e.g.:");
console.log('SITE_URL="http://localhost:4000"');
