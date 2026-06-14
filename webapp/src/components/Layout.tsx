import { Outlet, Link, useNavigate, NavLink } from "react-router-dom";
import { useState } from "react";
import { useSession } from "@/state/session";
import ImpactTicker from "@/components/ImpactTicker";

function CartIcon() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" className="text-white">
      <circle cx="9" cy="20" r="1" /><circle cx="18" cy="20" r="1" />
      <path d="M2 3h3l2.4 12.2a1 1 0 0 0 1 .8h8.7a1 1 0 0 0 1-.8L21 7H6" />
    </svg>
  );
}

export default function Layout() {
  const { persona, personas, setPersonaById } = useSession();
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  const navLink = ({ isActive }: { isActive: boolean }) =>
    `px-2 py-1 rounded hover:outline hover:outline-1 hover:outline-white/40 ${
      isActive ? "outline outline-1 outline-white/60" : ""
    }`;

  return (
    <div className="min-h-full flex flex-col">
      {/* Primary navy header */}
      <header className="bg-amz-navy text-white">
        <div className="flex items-center gap-2 px-3 py-2">
          <Link to="/" className="flex items-end gap-0.5 px-2 py-1 rounded hover:outline hover:outline-1 hover:outline-white/40">
            <span className="text-xl font-bold tracking-tight">second<span className="text-amz-orange">life</span></span>
            <span className="text-[10px] mb-1 text-gray-300">.in</span>
          </Link>

          {/* Deliver to */}
          <div className="hidden md:flex items-center text-xs px-2 leading-tight">
            <span className="self-end">📍</span>
            <div className="ml-1">
              <div className="text-gray-300">Deliver to {persona.name}</div>
              <div className="font-bold">Bengaluru 560001</div>
            </div>
          </div>

          {/* Search */}
          <form
            className="flex flex-1 max-w-3xl rounded-md overflow-hidden"
            onSubmit={(e) => { e.preventDefault(); navigate(`/?q=${encodeURIComponent(q)}`); }}
          >
            <span className="bg-gray-100 text-gray-700 text-xs px-3 flex items-center rounded-l-md border-r border-gray-300">
              All
            </span>
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search Second Life — new & Renewed"
              className="flex-1 px-3 py-2 text-sm text-black outline-none"
            />
            <button className="bg-amz-orange hover:bg-amz-yellowDark px-4 flex items-center" aria-label="Search">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0f1111" strokeWidth="2">
                <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
              </svg>
            </button>
          </form>

          {/* Role / persona switcher */}
          <label className="text-xs leading-tight px-2 cursor-pointer">
            <div className="text-gray-300">Hello, {persona.name}</div>
            <select
              value={persona.customer_id}
              onChange={(e) => setPersonaById(e.target.value)}
              className="bg-amz-navy font-bold text-white outline-none cursor-pointer"
            >
              {personas.map((p) => (
                <option key={p.customer_id} value={p.customer_id} className="text-black">
                  {p.name} — {p.role}
                </option>
              ))}
            </select>
          </label>

          <Link to="/wallet" className="text-xs leading-tight px-2 hover:outline hover:outline-1 hover:outline-white/40 rounded">
            <div className="text-gray-300">Green Coin</div>
            <div className="font-bold text-amz-orange">Wallet</div>
          </Link>

          <Link to="/recommended" className="flex items-end px-2 hover:outline hover:outline-1 hover:outline-white/40 rounded" aria-label="Cart">
            <CartIcon />
            <span className="text-sm font-bold mb-1">Cart</span>
          </Link>
        </div>

        {/* Secondary slate nav */}
        <nav className="bg-amz-slate text-white text-sm">
          <div className="flex items-center gap-1 px-3 py-1.5 overflow-x-auto whitespace-nowrap">
            <span className="px-2 py-1 font-medium flex items-center gap-1">☰ All</span>
            <NavLink to="/" end className={navLink}>Shop</NavLink>
            <NavLink to="/recommended" className={navLink}>For You</NavLink>
            <NavLink to="/returns" className={navLink}>Returns &amp; Resell</NavLink>
            <NavLink to="/wallet" className={navLink}>Green Coin</NavLink>
            <NavLink to="/seller" className={navLink}>Seller Hub</NavLink>
            <NavLink to="/ops" className={navLink}>
              <span className="text-amz-orange">● </span>Ops Console
            </NavLink>
            <span className="ml-auto text-amz-yellow font-medium hidden md:block">
              The Intelligent Bridge for Returns
            </span>
          </div>
        </nav>
      </header>

      <ImpactTicker />

      <main className="flex-1 w-full max-w-[1500px] mx-auto px-3 py-4">
        <Outlet />
      </main>

      <footer className="bg-amz-slate text-gray-300 text-xs">
        <div className="bg-amz-navy text-center py-3 text-sm text-white hover:underline cursor-pointer"
             onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          Back to top
        </div>
        <div className="max-w-[1000px] mx-auto px-4 py-6 grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="font-bold text-white mb-2">The Intelligent Bridge</div>
            <p>AI grading, smart routing, P2P resale, and Green Coin — every returned item gets a second life.</p>
          </div>
          <div>
            <div className="font-bold text-white mb-2">Modules</div>
            <ul className="space-y-1">
              <li>Grading &amp; Fraud</li><li>Recommend</li><li>Return Prevention</li>
              <li>Green Coin</li><li>P2P Exchange</li>
            </ul>
          </div>
          <div>
            <div className="font-bold text-white mb-2">Sustainability</div>
            <ul className="space-y-1"><li>CO₂e Impact</li><li>Green Credits</li><li>Renewed Store</li></ul>
          </div>
          <div>
            <div className="font-bold text-white mb-2">Demo</div>
            <ul className="space-y-1">
              <li><Link className="hover:underline" to="/ops">Ops Console</Link></li>
              <li><Link className="hover:underline" to="/returns">Start a return</Link></li>
            </ul>
          </div>
        </div>
        <div className="text-center py-4 border-t border-white/10">
          Second Life Commerce · Hackathon prototype · single-origin via gateway :8080
        </div>
      </footer>
    </div>
  );
}
