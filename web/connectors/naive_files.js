// Copy one file into the Naive file library (organization storage the agents read with fetch_file).
// Uses the official SDK's files.upload(FormData) as shown in the Naive Files docs. The docs show the
// "file" field; "folder" and "description" mirror the CLI's --folder / --description flags.
// UNVERIFIED until one real upload: check the file lands in <ticket_id>-incoming with `naive file list`.
export function naiveFiles(env) {
  return {
    async upload({ bytes, name, contentType, folder, description }) {
      const { createClient } = await import("@usenaive-sdk/managed-agents");
      const naive = createClient({ baseUrl: env.NAIVE_BASE_URL || "https://api.vetta.sh", apiKey: env.NAIVE_FILES_API_KEY });
      const form = new FormData();
      form.append("file", new Blob([bytes], { type: contentType || "application/octet-stream" }), name);
      form.append("folder", folder);
      if (description) form.append("description", description);
      const f = await naive.files.upload(form);
      return f.id;
    },
  };
}
