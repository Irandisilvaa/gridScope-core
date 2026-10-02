export type OperatorRole = "admin" | "user";

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: OperatorRole;
  is_active: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthResult {
  success: boolean;
  user?: UserProfile;
  error?: string;
}

export type AuthMode = "login";
