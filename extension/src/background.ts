// The extension's background worker: the only part that talks to the SignMeUp server, so
// YouTube's page never makes those requests itself (and no CORS setup is needed).

export const DEFAULT_SERVER = 'https://signmeup.fly.dev';

// For trying a local server: chrome.storage.local.set({ server: 'http://localhost:5002' }).
async function server(): Promise<string> {
  const { server } = await chrome.storage.local.get('server');
  return typeof server === 'string' && server ? server : DEFAULT_SERVER;
}

export type Request =
  | { type: 'sign-captions'; lines: unknown[] }
  | { type: 'pose'; path: string };

export interface Reply {
  ok: boolean;
  body: unknown; // the server's JSON, or { error } when it couldn't be reached
}

async function handle(request: Request): Promise<Reply> {
  const base = await server();
  let response: Response;
  if (request.type === 'sign-captions') {
    response = await fetch(`${base}/api/captions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lines: request.lines }),
    });
  } else if (request.type === 'pose' && /^\/poses\/\d+\.json(\?v=\d+)?$/.test(request.path)) {
    response = await fetch(`${base}${request.path}`);
  } else {
    return { ok: false, body: { error: 'Unknown request.' } };
  }
  return { ok: response.ok, body: await response.json() };
}

chrome.runtime.onMessage.addListener((request: Request, _sender, sendResponse: (reply: Reply) => void) => {
  handle(request).then(sendResponse, () => sendResponse({ ok: false, body: { error: 'Could not reach SignMeUp.' } }));
  return true; // the reply comes later
});
