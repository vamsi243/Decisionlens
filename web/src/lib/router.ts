import { useEffect, useState } from "react";

/** Hash routing (#/, #/how, #/live, #/recap): works on any static host without rewrite rules. */
export type Route = "home" | "how" | "live" | "recap";

function parse(hash: string): Route {
  const r = hash.replace(/^#\/?/, "").split(/[?/]/)[0];
  return r === "how" || r === "live" || r === "recap" ? r : "home";
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => {
      setRoute(parse(window.location.hash));
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export const href = (r: Route) => (r === "home" ? "#/" : `#/${r}`);
