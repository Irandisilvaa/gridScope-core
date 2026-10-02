import { api } from "./api";
import type { AuthResult, LoginCredentials, UserProfile } from "../types/auth";

class AuthService {
  async login(credentials: LoginCredentials): Promise<AuthResult> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15_000);
    try {
      const user = await api.login(credentials.email, credentials.password, controller.signal);
      return { success: true, user };
    } catch (error) {
      return {
        success: false,
        error: error instanceof DOMException && error.name === "AbortError"
          ? "A API não respondeu. Verifique se o servidor está em execução."
          : error instanceof Error
            ? error.message
            : "Credenciais inválidas.",
      };
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async getCurrentUser(): Promise<UserProfile | null> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    try {
      return await api.getCurrentUser(controller.signal);
    } catch {
      return null;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async logout(): Promise<void> {
    try {
      await api.logout();
    } catch {
      // The server session may already be expired.
    }
  }
}

export const authService = new AuthService();
