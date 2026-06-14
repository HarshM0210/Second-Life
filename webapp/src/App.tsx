import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import Shop from "@/pages/Shop";
import ProductDetail from "@/pages/ProductDetail";
import ReturnWizard from "@/pages/ReturnWizard";
import Wallet from "@/pages/Wallet";
import Feed from "@/pages/Feed";
import Seller from "@/pages/Seller";
import Ops from "@/pages/Ops";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Shop />} />
        <Route path="/product/:sku" element={<ProductDetail />} />
        <Route path="/returns" element={<ReturnWizard />} />
        <Route path="/returns/:sku" element={<ReturnWizard />} />
        <Route path="/wallet" element={<Wallet />} />
        <Route path="/recommended" element={<Feed />} />
        <Route path="/seller" element={<Seller />} />
        <Route path="/ops" element={<Ops />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
