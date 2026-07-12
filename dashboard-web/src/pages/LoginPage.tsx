import type { Dispatch, FormEvent, SetStateAction } from "react";

type LoginPageProps = {
  email: string;
  setEmail: Dispatch<SetStateAction<string>>;
  password: string;
  setPassword: Dispatch<SetStateAction<string>>;
  showLoginPassword: boolean;
  setShowLoginPassword: Dispatch<SetStateAction<boolean>>;
  error?: string | null;
  loginLoading: boolean;
  login: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
};

export function LoginPage({
  email,
  setEmail,
  password,
  setPassword,
  showLoginPassword,
  setShowLoginPassword,
  error,
  loginLoading,
  login,
}: LoginPageProps) {
  return (
    <main className="login-page premium-login-page">
      <section className="login-hero-card">
        <div className="login-brand-panel">
          <div className="login-brand-badge">MS</div>

          <p className="login-eyebrow">Merchant Control Center</p>
          <h1>Run your storefront like a real business.</h1>
          <p>
            Manage products, orders, payments, subscription limits, and store branding from one clean dashboard.
          </p>

          <div className="login-feature-list">
            <span>Fast order tracking</span>
            <span>Plan-based selling limits</span>
            <span>Premium storefront tools</span>
          </div>
        </div>

        <form className="login-card premium-login-card" onSubmit={login}>
          <div className="login-card-head">
            <h2>Sign in to StorePlug</h2>
            <p>Manage your storefront, orders, products, and payments from one workspace.</p>
          </div>

          <label>
            Email address
            <input
              type="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="merchant@example.com"
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <div className="password-input-wrap">
              <input
                type={showLoginPassword ? "text" : "password"}
                name="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />

              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowLoginPassword((prev) => !prev)}
                aria-label={showLoginPassword ? "Hide password" : "Show password"}
              >
                {showLoginPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          {error && (
            <div className="login-error-card" role="alert">
              <strong>Sign in failed</strong>
              <span>{error}</span>
            </div>
          )}

          <button className="premium-login-btn" type="submit" disabled={loginLoading}>
            {loginLoading ? "Signing in..." : "Login to dashboard"}
          </button>

          <p className="login-security-note">
            Protected merchant access for your StorePlug dashboard.
          </p>
        </form>
      </section>
    </main>
  );
}
