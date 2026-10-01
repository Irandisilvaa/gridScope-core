import type {
  AuthResult,
  LoginCredentials,
  OperatorRole,
  PasswordStrength,
  RegisterCredentials,
  UserProfile,
} from "../types/auth";

const STORAGE_KEY_USER = "gridscope_auth_user";
const STORAGE_KEY_TOKEN = "gridscope_auth_token";

const DEMO_USERS: UserProfile[] = [
  {
    id: "usr-001",
    name: "Dr. Carlos Eduardo Mendonça",
    email: "operador@gridscope.com",
    role: "engineer",
    technicalId: "OP-4821",
    department: "Operação de Tempo Real & Proteção",
    lastLoginAt: new Date().toISOString(),
  },
  {
    id: "usr-002",
    name: "Engª. Beatriz Albuquerque",
    email: "analista@gridscope.com",
    role: "analyst",
    technicalId: "AN-9104",
    department: "Planejamento Energético & GD",
    lastLoginAt: new Date().toISOString(),
  },
  {
    id: "usr-003",
    name: "Superintendência ONS / GridScope",
    email: "admin@gridscope.com",
    role: "admin",
    technicalId: "ADM-001",
    department: "Centro Nacional de Supervisão Elétrica",
    lastLoginAt: new Date().toISOString(),
  },
];

export interface IAuthService {
  login(credentials: LoginCredentials): Promise<AuthResult>;
  register(credentials: RegisterCredentials): Promise<AuthResult>;
  logout(): void;
  getCurrentUser(): UserProfile | null;
  checkPasswordStrength(password: string): PasswordStrength;
}

class AuthService implements IAuthService {
  private activeUser: UserProfile | null = null;

  constructor() {
    this.restoreSession();
  }

  private restoreSession(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_USER) || sessionStorage.getItem(STORAGE_KEY_USER);
      if (stored) {
        this.activeUser = JSON.parse(stored) as UserProfile;
      }
    } catch {
      this.activeUser = null;
    }
  }

  public getCurrentUser(): UserProfile | null {
    if (!this.activeUser) {
      this.restoreSession();
    }
    return this.activeUser;
  }

  public async login(credentials: LoginCredentials): Promise<AuthResult> {
    // Artificial operational latency for realism and UX tactile feel
    await new Promise((resolve) => setTimeout(resolve, 600));

    const emailClean = credentials.email.trim().toLowerCase();
    const pass = credentials.password;

    if (!emailClean) {
      return { success: false, error: "Informe o e-mail ou ID técnico operacional." };
    }

    if (!pass) {
      return { success: false, error: "Informe a senha de acesso." };
    }

    // Try matching demo operator or previously registered user
    const matched = DEMO_USERS.find(
      (u) => u.email.toLowerCase() === emailClean || u.technicalId.toLowerCase() === emailClean
    );

    let userToAuth: UserProfile;

    if (matched) {
      userToAuth = {
        ...matched,
        lastLoginAt: new Date().toISOString(),
      };
    } else {
      // Allow valid corporate emails for frictionless operational testing
      const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailClean);
      if (!isEmail && !emailClean.startsWith("OP-") && !emailClean.startsWith("GS-")) {
        return {
          success: false,
          error: "Credenciais inválidas. Use um e-mail corporativo ou ID técnico (ex: OP-4821).",
        };
      }

      if (pass.length < 6) {
        return {
          success: false,
          error: "A senha operacional deve conter no mínimo 6 caracteres.",
        };
      }

      // Generate operator profile for custom user
      const nameParts = emailClean.split("@")[0].split(".");
      const formattedName = nameParts
        .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
        .join(" ");

      userToAuth = {
        id: `usr-${Date.now().toString(36)}`,
        name: formattedName || "Operador de Rede",
        email: emailClean,
        role: "operator",
        technicalId: `OP-${Math.floor(1000 + Math.random() * 9000)}`,
        department: "Supervisão da Distribuição",
        lastLoginAt: new Date().toISOString(),
      };
    }

    this.persistUser(userToAuth, credentials.rememberMe);
    return { success: true, user: userToAuth };
  }

  public async register(credentials: RegisterCredentials): Promise<AuthResult> {
    await new Promise((resolve) => setTimeout(resolve, 800));

    const name = credentials.name.trim();
    const email = credentials.email.trim().toLowerCase();
    const pass = credentials.password;
    const confirm = credentials.confirmPassword;

    if (!name || name.length < 3) {
      return { success: false, error: "Nome completo deve ter pelo menos 3 caracteres." };
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return { success: false, error: "Informe um endereço de e-mail corporativo válido." };
    }

    if (!credentials.department.trim()) {
      return { success: false, error: "Informe o setor ou departamento de atuação." };
    }

    if (pass.length < 8) {
      return { success: false, error: "A senha deve conter no mínimo 8 caracteres." };
    }

    if (pass !== confirm) {
      return { success: false, error: "A confirmação de senha não confere." };
    }

    if (!credentials.acceptTerms) {
      return {
        success: false,
        error: "É obrigatório aceitar o termo de conformidade de segurança e sigilo de rede.",
      };
    }

    // Role prefix for technical operator ID
    const rolePrefixes: Record<OperatorRole, string> = {
      admin: "ADM",
      engineer: "ENG",
      analyst: "ANL",
      operator: "OPR",
    };

    const newOperator: UserProfile = {
      id: `usr-${Date.now().toString(36)}`,
      name,
      email,
      role: credentials.role,
      technicalId: `${rolePrefixes[credentials.role]}-${Math.floor(1000 + Math.random() * 9000)}`,
      department: credentials.department.trim(),
      lastLoginAt: new Date().toISOString(),
    };

    this.persistUser(newOperator, true);
    return { success: true, user: newOperator };
  }

  public logout(): void {
    this.activeUser = null;
    try {
      localStorage.removeItem(STORAGE_KEY_USER);
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      sessionStorage.removeItem(STORAGE_KEY_USER);
      sessionStorage.removeItem(STORAGE_KEY_TOKEN);
    } catch {
      // storage unavailable
    }
  }

  private persistUser(user: UserProfile, rememberMe: boolean): void {
    this.activeUser = user;
    const json = JSON.stringify(user);
    try {
      if (rememberMe) {
        localStorage.setItem(STORAGE_KEY_USER, json);
      } else {
        sessionStorage.setItem(STORAGE_KEY_USER, json);
      }
    } catch {
      // fallback
    }
  }

  public checkPasswordStrength(password: string): PasswordStrength {
    const rules = [
      {
        id: "len",
        label: "Mínimo de 8 caracteres",
        passed: password.length >= 8,
      },
      {
        id: "upper",
        label: "Pelo menos uma letra maiúscula",
        passed: /[A-Z]/.test(password),
      },
      {
        id: "num",
        label: "Pelo menos um número",
        passed: /[0-9]/.test(password),
      },
      {
        id: "spec",
        label: "Caractere especial (@, #, $, !)",
        passed: /[^A-Za-z0-9]/.test(password),
      },
    ];

    const passedCount = rules.filter((r) => r.passed).length;

    let score = passedCount;
    if (password.length >= 12 && passedCount === 4) {
      score = 4;
    }

    const configs: Array<{
      label: PasswordStrength["label"];
      color: string;
    }> = [
      { label: "Muito Fraca", color: "#EF4444" },
      { label: "Fraca", color: "#F97316" },
      { label: "Moderada", color: "#F59E0B" },
      { label: "Forte", color: "#EAB308" },
      { label: "Excelente (Padrão ONS)", color: "#22C55E" },
    ];

    const currentConfig = configs[Math.min(score, 4)];

    return {
      score,
      label: currentConfig.label,
      color: currentConfig.color,
      rules,
    };
  }
}

export const authService = new AuthService();
