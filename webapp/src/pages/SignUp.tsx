import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { completeOnboarding, setSocialTracking } from "@/state/onboarding";

// Front-end-only sign-up form. There is no auth backend wired up; on submit we
// mark onboarding complete and route the user to the shop.
export default function SignUp() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [socialTracking, setSocialTrackingState] = useState(true);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSocialTracking(socialTracking);
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
        <h1 className="text-2xl font-medium">Create account</h1>
        <form className="space-y-3" onSubmit={onSubmit}>
          <label className="block text-sm font-medium">
            Your name
            <input
              type="text" required value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-gray-400 rounded px-2 py-1.5 text-sm outline-none focus:border-amz-orange"
            />
          </label>
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
              minLength={6}
              className="mt-1 w-full border border-gray-400 rounded px-2 py-1.5 text-sm outline-none focus:border-amz-orange"
            />
            <span className="block text-xs text-gray-500 mt-1">Passwords must be at least 6 characters.</span>
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox" checked={socialTracking}
              onChange={(e) => setSocialTrackingState(e.target.checked)}
            />
            Enable social media tracking
          </label>
          <button type="submit" className="btn-amz-orange w-full">Create your account</button>
        </form>
        <p className="text-xs text-gray-500">
          By creating an account, you agree to Second Life's Conditions of Use and Privacy Notice.
        </p>
      </div>
      <div className="mt-5 text-center text-sm text-gray-600">
        Already have an account?{" "}
        <Link to="/signin" className="link-amz">Sign in</Link>
      </div>
    </div>
  );
}
