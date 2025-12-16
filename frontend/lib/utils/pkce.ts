'use client';

/**
 * PKCE の code_verifier と code_challenge を生成するユーティリティ。
 * SHA-256 + base64url でチャレンジを返す。
 */
export async function createPkcePair(): Promise<{ codeVerifier: string; codeChallenge: string }> {
  const cryptoApi: Crypto | undefined =
    typeof crypto !== 'undefined' ? crypto : (globalThis as any).crypto;

  if (!cryptoApi?.getRandomValues || !cryptoApi.subtle?.digest) {
    throw new Error('安全な乱数生成またはハッシュ機能が利用できません');
  }

  const random = new Uint8Array(96);
  cryptoApi.getRandomValues(random);
  const codeVerifier = base64UrlEncode(random).slice(0, 96);

  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const digest = await cryptoApi.subtle.digest('SHA-256', data);
  const codeChallenge = base64UrlEncode(new Uint8Array(digest));

  return { codeVerifier, codeChallenge };
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = btoa(binary);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
