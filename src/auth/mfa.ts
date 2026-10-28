export class CtapTimeoutError extends Error {
  constructor(message = "CTAP user presence check timed out (ERR_CTAP_TIMEOUT)") {
    super(message);
    this.name = "CtapTimeoutError";
  }
}

export async function verifyUserPresence(challenge: Uint8Array): Promise<boolean> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s attention window

  try {
    const credential = await navigator.credentials.get({
      publicKey: {
        challenge,
        userVerification: "required",
        timeout: 30000,
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!credential) {
      throw new CtapTimeoutError();
    }
    return true;
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError" || err instanceof CtapTimeoutError) {
      throw new CtapTimeoutError();
    }
    throw new Error(`WebAuthn assertion failed: ${err.message}`);
  }
}
