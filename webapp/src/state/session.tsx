import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { PERSONAS, type Persona } from "@/lib/catalog";

interface SessionCtx {
  persona: Persona;
  setPersonaById: (customerId: string) => void;
  personas: Persona[];
}

const Ctx = createContext<SessionCtx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [persona, setPersona] = useState<Persona>(PERSONAS[0]);
  const value = useMemo<SessionCtx>(
    () => ({
      persona,
      personas: PERSONAS,
      setPersonaById: (id) => {
        const p = PERSONAS.find((x) => x.customer_id === id);
        if (p) setPersona(p);
      },
    }),
    [persona],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession must be used within SessionProvider");
  return v;
}
