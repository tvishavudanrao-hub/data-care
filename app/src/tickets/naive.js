// Start a Naive session for the Recovery Manager, using the official SDK exactly as the Naive docs
// show it (createClient({ baseUrl, apiKey }); sessions.create({ agent_id, message })).
// The SDK is loaded only when autostart is on, so the form and tests need no extra dependency.
// Install it in the app that serves the form:  npm i @usenaive-sdk/managed-agents
// Use a NARROW key (sessions:write only), never an admin key, stored as an app secret.
export function naiveSessionStarter(env) {
  return async (message) => {
    const { createClient } = await import("@usenaive-sdk/managed-agents");
    const naive = createClient({ baseUrl: env.NAIVE_BASE_URL || "https://api.vetta.sh", apiKey: env.NAIVE_API_KEY });
    const session = await naive.sessions.create({ agent_id: env.RECOVERY_MANAGER_AGENT_ID, message });
    return session.id;
  };
}
