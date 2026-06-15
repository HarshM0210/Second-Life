import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { SessionProvider } from "@/state/session";
import { CartProvider } from "@/state/cart";
import { ClassifiedsProvider } from "@/state/classifieds";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <CartProvider>
          <ClassifiedsProvider>
            <App />
          </ClassifiedsProvider>
        </CartProvider>
      </SessionProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
