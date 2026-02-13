import Link from "next/link";

const plans = [
  {
    name: "Starter",
    price: "$99/mo",
    ideal: "Small agencies",
    features: ["Up to 3 agents", "1,000 leads/month", "Lead scoring", "Basic reports"]
  },
  {
    name: "Growth",
    price: "$249/mo",
    ideal: "Medium teams",
    features: ["Up to 10 agents", "5,000 leads/month", "Meta integrations", "Automation workflows"]
  },
  {
    name: "Pro",
    price: "$499/mo",
    ideal: "High-volume agencies",
    features: ["Up to 25 agents", "20,000 leads/month", "Advanced analytics", "Priority support"]
  },
  {
    name: "Enterprise",
    price: "$999+/mo",
    ideal: "Multi-branch operations",
    features: ["Unlimited agents", "Custom SLA", "SSO/RBAC hardening", "Dedicated onboarding"]
  }
];

export default function PricingPage() {
  return (
    <main className="container main-shell">
      <section className="card">
        <h1>Pricing</h1>
        <p className="small">Simple subscription pricing for real estate agencies. Usage-based communication costs are billed separately.</p>
      </section>

      <section className="grid cards-3">
        {plans.map((plan) => (
          <article key={plan.name} className="card">
            <h3>{plan.name}</h3>
            <p><strong>{plan.price}</strong></p>
            <p className="small">{plan.ideal}</p>
            <ul className="small">
              {plan.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
            <Link href="/login"><button>Start {plan.name}</button></Link>
          </article>
        ))}
      </section>
    </main>
  );
}