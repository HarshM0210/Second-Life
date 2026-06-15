import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import Layout from "@/components/Layout";
import Shop from "@/pages/Shop";
import ProductDetail from "@/pages/ProductDetail";
import ReturnWizard from "@/pages/ReturnWizard";
import Wallet from "@/pages/Wallet";
import Feed from "@/pages/Feed";
import Classifieds from "@/pages/Classifieds";
import Cart from "@/pages/Cart";
import SignIn from "@/pages/SignIn";
import SignUp from "@/pages/SignUp";
import { hasOnboarded } from "@/state/onboarding";

// Gate the storefront behind sign-up: until the user completes sign-up (or sign-in),
// every storefront route redirects to /signup so it loads first.
function RequireOnboard() {
  return hasOnboarded() ? <Outlet /> : <Navigate to="/signup" replace />;
}

export default function App() {
  return (
    <Routes>
      {/* Standalone auth pages (no storefront chrome) */}
      <Route path="/signup" element={<SignUp />} />
      <Route path="/signin" element={<SignIn />} />

      {/* Storefront — only reachable after onboarding */}
      <Route element={<RequireOnboard />}>
        <Route element={<Layout />}>
          <Route index element={<Shop />} />
          <Route path="/product/:sku" element={<ProductDetail />} />
          <Route path="/returns" element={<ReturnWizard />} />
          <Route path="/returns/:sku" element={<ReturnWizard />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/recommended" element={<Feed />} />
          <Route path="/classifieds" element={<Classifieds />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
