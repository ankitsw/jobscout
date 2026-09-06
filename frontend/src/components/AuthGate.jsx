import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';

export default function AuthGate({ children }) {
  const [status, setStatus] = useState('checking'); // checking | locked | open
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .authStatus()
      .then((res) => setStatus(res.gate_enabled && !res.authenticated ? 'locked' : 'open'))
      .catch(() => setStatus('open'));
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await api.login(password);
      setStatus('open');
    } catch (err) {
      setError(err.message || 'Incorrect password');
    } finally {
      setSubmitting(false);
    }
  }

  if (status === 'checking') return null;
  if (status === 'open') return children;

  return (
    <div className="auth-gate">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="brand-mark">J</div>
        <h1>JobScout</h1>
        <p className="muted">This is a private instance. Enter the access password to continue.</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
        />
        {error && <p className="auth-error">{error}</p>}
        <button className="action-button" type="submit" disabled={submitting || !password}>
          {submitting ? 'Checking…' : 'Enter'}
        </button>
      </form>
    </div>
  );
}
