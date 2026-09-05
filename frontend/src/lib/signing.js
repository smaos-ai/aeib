/**
 * Real cryptographic signing via Web Crypto API.
 * Ed25519 preferred; ECDSA P-256/SHA-256 fallback for browsers without Ed25519 support.
 * Every signature is immediately self-verified (verified boolean is computed, not claimed).
 */

let cachedKeypair = null
let algorithm = null

/**
 * Get or create a session keypair.
 * Stores JWK data in sessionStorage; reconstructs CryptoKey objects in memory.
 * CryptoKey objects cannot be serialized, so we only store + restore JWK data.
 */
export async function getOrCreateKeypair() {
  if (cachedKeypair) return cachedKeypair

  // Check sessionStorage for JWK data
  const stored = sessionStorage.getItem('smaos-session-keypair')
  if (stored) {
    try {
      const jwkData = JSON.parse(stored)
      algorithm = jwkData.alg

      // Reconstruct CryptoKey objects from JWK
      if (jwkData.alg === 'Ed25519') {
        const privateKey = await crypto.subtle.importKey('jwk', jwkData.privateKeyJwk, 'Ed25519', true, ['sign'])
        const publicKey = await crypto.subtle.importKey('jwk', jwkData.publicKeyJwk, 'Ed25519', false, ['verify'])
        cachedKeypair = {
          alg: 'Ed25519',
          privateKey,
          publicKey,
          publicKeyBase64: jwkData.publicKeyBase64,
          privateKeyJwk: jwkData.privateKeyJwk,
          publicKeyJwk: jwkData.publicKeyJwk,
        }
        return cachedKeypair
      } else if (jwkData.alg === 'ECDSA-P256') {
        const privateKey = await crypto.subtle.importKey('jwk', jwkData.privateKeyJwk, { name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign'])
        const publicKey = await crypto.subtle.importKey('jwk', jwkData.publicKeyJwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify'])
        cachedKeypair = {
          alg: 'ECDSA-P256',
          privateKey,
          publicKey,
          publicKeyBase64: jwkData.publicKeyBase64,
          privateKeyJwk: jwkData.privateKeyJwk,
          publicKeyJwk: jwkData.publicKeyJwk,
          hashAlgorithm: 'SHA-256',
        }
        return cachedKeypair
      }
    } catch (e) {
      console.warn('Failed to restore keypair from sessionStorage:', e)
    }
  }

  // Generate new keypair
  try {
    // Try Ed25519 first (most modern, post-quantum resistant)
    const key = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify'])
    algorithm = 'Ed25519'
    const privateKeyJwk = await crypto.subtle.exportKey('jwk', key.privateKey)
    const publicKeyJwk = await crypto.subtle.exportKey('jwk', key.publicKey)
    const publicKeyRaw = await crypto.subtle.exportKey('raw', key.publicKey)

    const publicKeyBase64 = btoa(String.fromCharCode(...new Uint8Array(publicKeyRaw)))
    cachedKeypair = {
      alg: 'Ed25519',
      privateKey: key.privateKey,
      publicKey: key.publicKey,
      publicKeyBase64,
      privateKeyJwk,
      publicKeyJwk,
    }

    // Store only JWK data in sessionStorage (CryptoKey cannot be serialized)
    sessionStorage.setItem('smaos-session-keypair', JSON.stringify({
      alg: 'Ed25519',
      publicKeyBase64,
      publicKeyJwk,
      privateKeyJwk,
    }))
  } catch (e) {
    // Fallback to ECDSA P-256 with SHA-256
    console.warn('Ed25519 not supported, falling back to ECDSA P-256:', e.message)
    const key = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify']
    )
    algorithm = 'ECDSA-P256'
    const publicKeyRaw = await crypto.subtle.exportKey('raw', key.publicKey)
    const privateKeyJwk = await crypto.subtle.exportKey('jwk', key.privateKey)
    const publicKeyJwk = await crypto.subtle.exportKey('jwk', key.publicKey)
    const publicKeyBase64 = btoa(String.fromCharCode(...new Uint8Array(publicKeyRaw)))

    cachedKeypair = {
      alg: 'ECDSA-P256',
      privateKey: key.privateKey,
      publicKey: key.publicKey,
      publicKeyBase64,
      privateKeyJwk,
      publicKeyJwk,
      hashAlgorithm: 'SHA-256',
    }

    // Store only JWK data in sessionStorage
    sessionStorage.setItem('smaos-session-keypair', JSON.stringify({
      alg: 'ECDSA-P256',
      publicKeyBase64,
      publicKeyJwk,
      privateKeyJwk,
    }))
  }

  return cachedKeypair
}

/**
 * Canonical JSON stringify: sorted keys, no whitespace.
 * Used as the input to signing so the same object always produces the same signature.
 */
export function canonicalStringify(obj) {
  if (obj === null) return 'null'
  if (typeof obj !== 'object') return JSON.stringify(obj)
  if (Array.isArray(obj)) {
    const items = obj.map(canonicalStringify)
    return `[${items.join(',')}]`
  }
  const keys = Object.keys(obj).sort()
  const pairs = keys.map(k => `"${k}":${canonicalStringify(obj[k])}`)
  return `{${pairs.join(',')}}`
}

/**
 * Sign a payload (object).
 * Returns a Receipt object with all signing metadata.
 */
export async function signPayload(payload) {
  const kp = await getOrCreateKeypair()
  const canonical = canonicalStringify(payload)
  const bytes = new TextEncoder().encode(canonical)

  let signatureBytes
  if (kp.alg === 'Ed25519') {
    signatureBytes = await crypto.subtle.sign('Ed25519', kp.privateKey, bytes)
  } else if (kp.alg === 'ECDSA-P256') {
    signatureBytes = await crypto.subtle.sign(
      { name: 'ECDSA', hash: kp.hashAlgorithm },
      kp.privateKey,
      bytes
    )
  }

  const signatureBase64 = btoa(String.fromCharCode(...new Uint8Array(signatureBytes)))

  // Immediately self-verify
  let verified = false
  try {
    if (kp.alg === 'Ed25519') {
      verified = await crypto.subtle.verify('Ed25519', kp.publicKey, signatureBytes, bytes)
    } else if (kp.alg === 'ECDSA-P256') {
      verified = await crypto.subtle.verify(
        { name: 'ECDSA', hash: kp.hashAlgorithm },
        kp.publicKey,
        signatureBytes,
        bytes
      )
    }
  } catch (e) {
    console.error('Self-verification failed:', e)
    verified = false
  }

  return {
    id: `receipt-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    timestamp: new Date().toISOString(),
    alg: kp.alg,
    payload,
    payloadCanonicalJSON: canonical,
    signatureBase64,
    publicKeyBase64: kp.publicKeyBase64,
    verified,
  }
}

/**
 * Verify a receipt's signature against its stored public key.
 * Can be called multiple times (used in the UI's "Verify" button per row).
 */
export async function verifyReceipt(receipt) {
  if (!receipt.publicKeyBase64 || !receipt.signatureBase64 || !receipt.payloadCanonicalJSON) {
    return false
  }

  const publicKeyBytes = Uint8Array.from(atob(receipt.publicKeyBase64), c => c.charCodeAt(0))
  const signatureBytes = Uint8Array.from(atob(receipt.signatureBase64), c => c.charCodeAt(0))
  const messageBytes = new TextEncoder().encode(receipt.payloadCanonicalJSON)

  try {
    // Reconstruct the public key from its raw bytes
    let publicKey
    if (receipt.alg === 'Ed25519') {
      publicKey = await crypto.subtle.importKey('raw', publicKeyBytes, 'Ed25519', false, ['verify'])
      return await crypto.subtle.verify('Ed25519', publicKey, signatureBytes, messageBytes)
    } else if (receipt.alg === 'ECDSA-P256') {
      publicKey = await crypto.subtle.importKey(
        'raw',
        publicKeyBytes,
        { name: 'ECDSA', namedCurve: 'P-256' },
        false,
        ['verify']
      )
      return await crypto.subtle.verify(
        { name: 'ECDSA', hash: 'SHA-256' },
        publicKey,
        signatureBytes,
        messageBytes
      )
    }
  } catch (e) {
    console.error('Verification error:', e)
    return false
  }

  return false
}

/**
 * Reset keypair (useful for testing, or to start a new session).
 */
export function resetKeypair() {
  cachedKeypair = null
  algorithm = null
  sessionStorage.removeItem('smaos-session-keypair')
}
