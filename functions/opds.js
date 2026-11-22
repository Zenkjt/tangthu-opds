const WORKER_ORIGIN = "https://tangthu-storage-api.mienluonngon.workers.dev";

export async function onRequest({ request }) {
  const incoming = new URL(request.url);
  const target = new URL(WORKER_ORIGIN);
  target.pathname = "/opds/index.xml";
  target.search = incoming.search;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("authorization");

  return fetch(new Request(target.toString(), {
    method: request.method,
    headers,
    redirect: "manual"
  }));
}
