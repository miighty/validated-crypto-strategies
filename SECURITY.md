# Security and Public-Repository Policy

This repository is intentionally safe for public release:

- It fetches unauthenticated public market-data endpoints only.
- It does not read `.env`, keychain, wallet, exchange, cloud, or messaging credentials.
- It contains no order-placement client, private endpoint, scheduler, webhook secret, deployment manifest, account identifier, or live/paper execution path.
- `.env*`, local virtual environments, caches, and logs are ignored.
- Public exchange observations and derived research outputs are not user account data.

Before each publication, scan tracked content for high-entropy secrets and common key/token formats, inspect the staged diff, and reject files above GitHub's 100 MiB object limit.

If a credential is ever committed, revoke it first, then remove it from Git history before republishing. Opening a cleanup pull request alone is not sufficient because the secret remains in history.
