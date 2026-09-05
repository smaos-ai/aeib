import * as crypto from 'crypto';

interface Session {
  id: string;
  userId: string;
  createdAt: number;
  lastActivity: number;
  mfaRequired?: boolean;
  mfaComplete?: boolean;
  mfaMethod?: string;
  attributes: Map<string, any>;
  maxAge?: number;
}

interface SessionOptions {
  mfaRequired?: boolean;
  maxAge?: number;
}

interface RateLimitEntry {
  count: number;
  resetTime: number;
  failedLogins: number;
}

export class SessionManager {
  private sessions: Map<string, Session> = new Map();
  private rateLimits: Map<string, RateLimitEntry> = new Map();
  private passwordResetTokens: Map<string, { userId: string; expiresAt: number }> = new Map();
  private readonly RATE_LIMIT_WINDOW = 60000; // 1 minute
  private readonly RATE_LIMIT_MAX = 10; // 10 attempts per window
  private readonly PASSWORD_RESET_EXPIRY = 15 * 60 * 1000; // 15 minutes

  createSession(userId: string, options?: SessionOptions): Session {
    const now = Date.now();
    const session: Session = {
      id: `sess_${crypto.randomBytes(16).toString('hex')}`,
      userId,
      createdAt: now,
      lastActivity: now,
      mfaRequired: options?.mfaRequired,
      attributes: new Map(),
      maxAge: options?.maxAge
    };
    this.sessions.set(session.id, session);
    return session;
  }

  getSession(sessionId: string): Session | undefined {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.lastActivity = Date.now();
      return session;
    }
    return undefined;
  }

  logout(sessionId: string): void {
    this.sessions.delete(sessionId);
  }

  invalidateAllUserSessions(userId: string): void {
    const sessionsToDelete: string[] = [];
    for (const [id, session] of this.sessions) {
      if (session.userId === userId) {
        sessionsToDelete.push(id);
      }
    }
    sessionsToDelete.forEach(id => this.sessions.delete(id));
  }

  isSessionValid(sessionId: string): boolean {
    const session = this.sessions.get(sessionId);
    if (!session) return false;

    if (session.maxAge) {
      const age = (Date.now() - session.createdAt) / 1000;
      if (age > session.maxAge) {
        this.sessions.delete(sessionId);
        return false;
      }
    }
    return true;
  }

  isMFAComplete(sessionId: string): boolean {
    const session = this.sessions.get(sessionId);
    if (!session) return false;
    return session.mfaComplete ?? false;
  }

  markMFAComplete(sessionId: string, method: string): void {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.mfaComplete = true;
      session.mfaMethod = method;
    }
  }

  getMFAMethod(sessionId: string): string | undefined {
    const session = this.sessions.get(sessionId);
    return session?.mfaMethod;
  }

  canAttemptLogin(userId: string): boolean {
    const now = Date.now();
    const key = `login:${userId}`;

    if (this.rateLimits.has(key)) {
      const entry = this.rateLimits.get(key)!;
      if (now < entry.resetTime) {
        if (entry.count >= this.RATE_LIMIT_MAX) {
          return false;
        }
        entry.count++;
        return true;
      } else {
        this.rateLimits.set(key, {
          count: 1,
          resetTime: now + this.RATE_LIMIT_WINDOW,
          failedLogins: 0
        });
        return true;
      }
    } else {
      this.rateLimits.set(key, {
        count: 1,
        resetTime: now + this.RATE_LIMIT_WINDOW,
        failedLogins: 0
      });
      return true;
    }
  }

  recordFailedLogin(userId: string): void {
    const now = Date.now();
    const key = `login:${userId}`;

    if (this.rateLimits.has(key)) {
      const entry = this.rateLimits.get(key)!;
      if (now < entry.resetTime) {
        entry.failedLogins++;
      } else {
        this.rateLimits.set(key, {
          count: 1,
          resetTime: now + this.RATE_LIMIT_WINDOW,
          failedLogins: 1
        });
      }
    } else {
      this.rateLimits.set(key, {
        count: 1,
        resetTime: now + this.RATE_LIMIT_WINDOW,
        failedLogins: 1
      });
    }
  }

  recordSuccessfulLogin(userId: string): void {
    const key = `login:${userId}`;
    this.rateLimits.delete(key);
  }

  getFailedLoginCount(userId: string): number {
    const key = `login:${userId}`;
    const entry = this.rateLimits.get(key);
    return entry?.failedLogins ?? 0;
  }

  setAttribute(sessionId: string, key: string, value: any): void {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.attributes.set(key, value);
    }
  }

  getAttribute(sessionId: string, key: string): any | undefined {
    const session = this.sessions.get(sessionId);
    return session?.attributes.get(key);
  }

  createPasswordResetToken(userId: string, expiryMs?: number): string {
    const token = crypto.randomBytes(32).toString('hex');
    const expiresAt = Date.now() + (expiryMs ?? this.PASSWORD_RESET_EXPIRY);
    this.passwordResetTokens.set(token, { userId, expiresAt });
    return token;
  }

  validatePasswordResetToken(token: string, userId: string): boolean {
    const entry = this.passwordResetTokens.get(token);
    if (!entry) return false;
    if (entry.userId !== userId) return false;
    if (Date.now() > entry.expiresAt) {
      this.passwordResetTokens.delete(token);
      return false;
    }
    return true;
  }

  consumePasswordResetToken(token: string): void {
    this.passwordResetTokens.delete(token);
  }
}
