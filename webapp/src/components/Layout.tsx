import { Outlet, Link, useNavigate, NavLink } from "react-router-dom";
import { useState } from "react";
import { useSession } from "@/state/session";
import { useCart } from "@/state/cart";
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
  const { count } = useCart();
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
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search Second Life — new & Renewed"
              className="flex-1 px-3 py-2 text-sm text-black outline-none rounded-l-md"
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

          {/* Account: sign in / sign up */}
          <div className="text-xs leading-tight px-2">
            <Link to="/signin" className="block text-gray-300 hover:text-white">Sign In</Link>
            <Link to="/signup" className="block font-bold hover:underline">Sign Up</Link>
          </div>

          <Link to="/cart" className="relative flex items-end px-2 hover:outline hover:outline-1 hover:outline-white/40 rounded" aria-label="Cart">
            <CartIcon />
            {count > 0 && (
              <span className="absolute -top-0.5 left-4 bg-amz-orange text-[#0f1111] text-[11px] font-bold rounded-full px-1.5 leading-tight">
                {count}
              </span>
            )}
            <span className="text-sm font-bold mb-1">Cart</span>
          </Link>
        </div>

        {/* Secondary slate nav */}
        <nav className="bg-amz-slate text-white text-sm">
          <div className="flex items-center gap-1 px-3 py-1.5 overflow-x-auto whitespace-nowrap">
            <NavLink to="/" end className={navLink}>Shop</NavLink>
            <NavLink to="/recommended" className={navLink}>For You</NavLink>
            <NavLink to="/classifieds" className={navLink}>Classifieds</NavLink>
            <NavLink to="/returns" className={navLink}>My Orders</NavLink>
            <NavLink to="/wallet" className={navLink}>Green Coin</NavLink>
          </div>
        </nav>
      </header>

      <ImpactTicker />

      <main className="flex-1 w-full max-w-[1500px] mx-auto px-3 py-4">
        <Outlet />
      </main>

      <footer className="bg-amz-slate text-gray-300 text-xs">
        <div className="max-w-[1000px] mx-auto px-4 py-6 grid grid-cols-1 sm:grid-cols-3 gap-8 items-start text-left">
          <div>
            <div className="font-bold text-white mb-2">The Intelligent Bridge</div>
            <p>AI grading, smart routing, P2P resale, and Green Coin — every returned item gets a second life.</p>
          </div>
          <div>
            <div className="font-bold text-white mb-2">Sustainability</div>
            <ul className="space-y-1"><li>CO₂e Impact</li><li>Green Credits</li><li>Renewed Store</li></ul>
          </div>
          <div>
            <div className="font-bold text-white mb-2">Created by</div>
            <ul className="space-y-1">
              <li>Harsh Mishra</li>
              <li>Chinmay Bhardwaj</li>
              <li>Kaushal Sharma</li>
            </ul>
          </div>
        </div>
        <div className="text-center py-4 border-t border-white/10">
          Second Life Commerce · Built by Team Second Life · Hackathon prototype
        </div>
      </footer>
    </div>
  );
}
