import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { completeOnboarding } from "@/state/onboarding";

// Front-end-only sign-in form. There is no auth backend wired up; on submit we
// mark onboarding complete and route the user to the shop.
export default function SignIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    completeOnboarding();
    navigate("/");
  };

  return (
    <div className="max-w-sm mx-auto py-6">
      <div className="text-center mb-4">
        <span className="text-2xl font-bold tracking-tight">
          second<span className="text-amz-orange">life</span>
        </span>
      </div>
      <div className="card p-6 space-y-4">
        <h1 className="text-2xl font-medium">Sign in</h1>
        <form className="space-y-3" onSubmit={onSubmit}>
          <label className="block text-sm font-medium">
            Email
            <input
              type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full border border-gray-400 rounded px-2 py-1.5 text-sm outline-none focus:border-amz-orange"
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              type="password" required value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full border border-gray-400 rounded px-2 py-1.5 text-sm outline-none focus:border-amz-orange"
            />
          </label>
          <button type="submit" className="btn-amz w-full">Sign in</button>
        </form>
        <p className="text-xs text-gray-500">
          By continuing, you agree to Second Life's Conditions of Use and Privacy Notice.
        </p>
      </div>
      <div className="mt-5 text-center text-sm text-gray-600">
        New to Second Life?{" "}
        <Link to="/signup" className="link-amz">Create your account</Link>
      </div>
    </div>
  );
}
