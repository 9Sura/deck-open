// The home route (plan 09 §4.4, D1). Delegates to the client <HomeGate/>, which
// renders the study dashboard for a signed-in member and the marketing landing
// for a guest. All the actual home content lives in components/home/*.

import { HomeGate } from "@/components/home/home-gate";

export default function Home() {
  return <HomeGate />;
}
