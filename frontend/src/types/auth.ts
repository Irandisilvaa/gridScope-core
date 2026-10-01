export type OperatorRole = "admin" | "engineer" | "analyst" | "operator";

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: OperatorRole;
  technicalId: string;
  department: string;
  token?: string;
  lastLoginAt?: string;
  avatarUrl?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface RegisterCredentials {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  role: OperatorRole;
  department: string;
  acceptTerms: boolean;
}

export interface AuthResult {
  success: boolean;
  user?: UserProfile;
  error?: string;
}

export interface PasswordValidationRule {
  id: string;
  label: string;
  passed: boolean;
}

export interface PasswordStrength {
  score: number; // 0 to 4
  label: "Muito Fraca" | "Fraca" | "Moderada" | "Forte" | "Excelente (Padrão ONS)";
  color: string;
  rules: PasswordValidationRule[];
}

export type AuthMode = "login" | "register";
