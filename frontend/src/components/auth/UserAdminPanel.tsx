import React, { useEffect, useState } from "react";
import { CircleNotch, FloppyDisk, UserPlus, UsersThree, X } from "@phosphor-icons/react";
import { api, type AuthUser } from "../../lib/api";
import { Select } from "../Select";

function formatDate(value?: string | null) {
  if (!value) return "Nunca";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

export const UserAdminPanel: React.FC = () => {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "user" as AuthUser["role"] });
  const [resetUserId, setResetUserId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const loadUsers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setUsers(await api.listUsers());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Não foi possível carregar os usuários.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const runAction = async (action: () => Promise<void>, successMessage: string) => {
    setIsSaving(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(successMessage);
      await loadUsers();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Não foi possível concluir a operação.");
    } finally {
      setIsSaving(false);
    }
  };

  const createUser = async (event: React.FormEvent) => {
    event.preventDefault();
    await runAction(
      async () => {
        await api.createUser(form);
        setForm({ email: "", name: "", password: "", role: "user" });
      },
      "Usuário criado com sucesso.",
    );
  };

  const handleResetPassword = async (userId: string) => {
    await runAction(async () => {
      await api.resetUserPassword(userId, newPassword);
      setResetUserId(null);
      setNewPassword("");
    }, "Senha redefinida e sessões anteriores revogadas.");
  };

  return (
    <div className="space-y-6 pt-2">
      <section className="rounded-2xl border border-grid-border-card bg-grid-surface p-5 double-bezel md:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">CONTROLE DE ACESSO</span>
            <h2 className="mt-1 font-display text-2xl font-bold text-white">Usuários provisionados</h2>
            <p className="mt-1 max-w-2xl text-sm text-grid-gray">Crie, suspenda e redefina credenciais. Não existe cadastro público.</p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-grid-border bg-grid-surface-elevated px-3 py-2 font-mono text-xs text-grid-gray-light">
            <UsersThree size={16} className="text-grid-yellow" />
            {users.length} contas
          </div>
        </div>
      </section>

      {error && <div className="rounded-xl border border-status-danger/40 bg-status-danger/10 p-3 text-xs text-status-danger">{error}</div>}
      {notice && <div className="rounded-xl border border-status-success/40 bg-status-success/10 p-3 text-xs text-status-success">{notice}</div>}

      <section className="rounded-2xl border border-grid-border-card bg-grid-surface p-5 md:p-6">
        <div className="mb-4 flex items-center gap-2">
          <UserPlus size={18} className="text-grid-yellow" />
          <h3 className="font-display text-base font-bold text-white">Provisionar usuário</h3>
        </div>
        <form onSubmit={createUser} className="grid gap-3 md:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_150px_auto]">
          <input
            required
            type="text"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            placeholder="Nome completo"
            className="rounded-xl border border-grid-border-card bg-grid-surface-raised px-3 py-2.5 font-mono text-xs text-white placeholder:text-grid-gray-dim focus:border-grid-yellow focus:outline-none"
          />
          <input
            required
            type="email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            placeholder="email@distribuidora.com.br"
            className="rounded-xl border border-grid-border-card bg-grid-surface-raised px-3 py-2.5 font-mono text-xs text-white placeholder:text-grid-gray-dim focus:border-grid-yellow focus:outline-none"
          />
          <input
            required
            minLength={12}
            type="password"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            placeholder="Senha (mín. 12)"
            className="rounded-xl border border-grid-border-card bg-grid-surface-raised px-3 py-2.5 font-mono text-xs text-white placeholder:text-grid-gray-dim focus:border-grid-yellow focus:outline-none"
          />
          <Select<AuthUser["role"]>
            value={form.role}
            onChange={(role) => setForm({ ...form, role })}
            options={[
              { value: "user", label: "Usuário" },
              { value: "admin", label: "Administrador" },
            ]}
          />
          <button disabled={isSaving} type="submit" className="flex items-center justify-center gap-2 rounded-xl bg-grid-yellow px-4 py-2.5 font-mono text-xs font-bold text-black disabled:opacity-50">
            {isSaving ? <CircleNotch size={15} className="animate-spin" /> : <UserPlus size={15} />}
            Criar
          </button>
        </form>
      </section>

      <section className="overflow-hidden rounded-2xl border border-grid-border-card bg-grid-surface">
        {isLoading ? (
          <div className="flex h-40 items-center justify-center gap-2 font-mono text-xs text-grid-gray"><CircleNotch size={18} className="animate-spin text-grid-yellow" /> Carregando usuários...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead className="border-b border-grid-graphite-light bg-grid-surface-raised font-mono text-[0.65rem] uppercase tracking-wider text-grid-gray-muted">
                <tr><th className="px-4 py-3">Usuário</th><th className="px-4 py-3">Perfil</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3">Último acesso</th><th className="px-4 py-3 text-right">Ações</th></tr>
              </thead>
              <tbody className="divide-y divide-grid-border-subtle">
                {users.map((user) => (
                  <tr key={user.id} className="text-xs text-grid-gray-subtle">
                    <td className="px-4 py-4"><strong className="block text-white">{user.name}</strong><span className="font-mono text-[0.68rem] text-grid-gray-muted">{user.email}</span></td>
                    <td className="px-4 py-4">
                      <Select<AuthUser["role"]>
                        value={user.role}
                        disabled={isSaving}
                        size="sm"
                        onChange={(role) =>
                          void runAction(
                            () => api.updateUser(user.id, { role }).then(() => undefined),
                            "Perfil atualizado."
                          )
                        }
                        options={[
                          { value: "user", label: "Usuário" },
                          { value: "admin", label: "Administrador" },
                        ]}
                        className="w-36"
                      />
                    </td>
                    <td className="px-4 py-4"><span className={`inline-flex items-center gap-1.5 font-mono text-[0.68rem] ${user.is_active ? "text-status-success" : "text-status-danger"}`}><span className={`h-1.5 w-1.5 rounded-full ${user.is_active ? "bg-status-success" : "bg-status-danger"}`} />{user.is_active ? "Ativo" : "Suspenso"}</span></td>
                    <td className="px-4 py-4 font-mono text-[0.68rem] text-grid-gray-muted">{formatDate(user.last_login_at)}</td>
                    <td className="px-4 py-4"><div className="flex justify-end gap-2">
                      <button type="button" disabled={isSaving} onClick={() => void runAction(() => api.updateUser(user.id, { is_active: !user.is_active }).then(() => undefined), user.is_active ? "Usuário suspenso." : "Usuário reativado.")} className="rounded-lg border border-grid-border-card px-2.5 py-1.5 font-mono text-[0.68rem] text-grid-gray-subtle hover:border-grid-yellow hover:text-grid-yellow disabled:opacity-50">{user.is_active ? "Suspender" : "Reativar"}</button>
                      <button type="button" disabled={isSaving} onClick={() => { setResetUserId(user.id); setNewPassword(""); }} className="rounded-lg border border-grid-border-card px-2.5 py-1.5 font-mono text-[0.68rem] text-grid-gray-subtle hover:border-grid-yellow hover:text-grid-yellow disabled:opacity-50">Redefinir senha</button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {resetUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="dialog" aria-modal="true">
          <form onSubmit={(event) => { event.preventDefault(); void handleResetPassword(resetUserId); }} className="w-full max-w-sm rounded-2xl border border-grid-border-card bg-grid-surface p-5 shadow-2xl">
            <div className="flex items-center justify-between"><h3 className="font-display font-bold text-white">Redefinir senha</h3><button type="button" onClick={() => setResetUserId(null)} className="text-grid-gray-muted hover:text-white"><X size={18} /></button></div>
            <p className="mt-2 text-xs text-grid-gray">As sessões existentes do usuário serão revogadas.</p>
            <input required minLength={12} type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="Nova senha (mín. 12)" className="mt-4 w-full rounded-xl border border-grid-border-card bg-grid-surface-raised px-3 py-2.5 font-mono text-xs text-white placeholder:text-grid-gray-dim focus:border-grid-yellow focus:outline-none" />
            <button disabled={isSaving} type="submit" className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-grid-yellow px-4 py-2.5 font-mono text-xs font-bold text-black disabled:opacity-50"><FloppyDisk size={15} /> Salvar nova senha</button>
          </form>
        </div>
      )}
    </div>
  );
};
