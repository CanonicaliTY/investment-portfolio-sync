# Security

## Threat model

The sensitive assets are the Trading 212 API key and secret, plus the financial data written to `portfolio/latest.json`. The main risks are committing credentials, leaking them through logs or exceptions, forwarding Basic Auth to another host, accidentally adding write operations, and exposing a real snapshot in a public repository.

## Built-in controls

- Credentials are read only from `T212_API_KEY` and `T212_API_SECRET`.
- `.env`, common credential files, private keys, and editor files are ignored by Git.
- The client is fixed to `https://live.trading212.com/api/v0` and five explicit read-only paths.
- Every HTTP request uses `GET`; there are no order placement, cancellation, or Pie modification methods.
- Redirects are rejected so Basic Auth is never forwarded to a redirect target.
- Pagination URLs must remain on the official HTTPS host and match an allowed history endpoint.
- API response bodies, request headers, and underlying exception messages are never included in user-facing errors.
- Rate-limit responses are retried using the server-provided timing headers.
- Snapshots are written to a temporary file and atomically replaced.
- GitHub Actions stages only `portfolio/latest.json`.

## Repository visibility

This source repository can be public because it contains only an empty placeholder snapshot. A repository that runs the sync against a real account should be private because the generated snapshot contains financial information.

Use **Use this template** to create a separate private repository. Do not rely on a public fork becoming private.

## Operator responsibilities

- Create a dedicated Trading 212 key with read-only permissions. Never grant trading permissions.
- Keep the repository containing real snapshots private and restrict collaborator access.
- Store credentials only in local environment variables and GitHub Actions Secrets.
- Never paste credentials into chat, issues, pull requests, source code, or command arguments.
- Rotate credentials regularly. Revoke them immediately if exposure is suspected.
- Review staged changes and run a secret scanner before publishing.

Deleting a leaked secret from a file is not enough. Revoke the credential first, then clean Git history and any copied logs or artifacts.

## Reporting a vulnerability

Do not report suspected credentials in a public issue. Revoke affected credentials and contact the repository owner through a private channel.
