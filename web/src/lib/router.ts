import { useEffect, useState } from "react";

/** Hash routing (#/, #/recap, #/how): works on any static host without rewrite rules. */
export type Route = "live" | "recap" | "how";

function parse(hash: string): Route {
  const r = hash.replace(/^#\/?/, "").split(/[?/]/)[0];
  return r === "recap" || r === "how" ? r : "live";
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

export const href = (r: Route) => (r === "live" ? "#/" : `#/${r}`);
