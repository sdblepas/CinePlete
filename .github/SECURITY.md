# Security Policy

## Supported Versions

Only the latest release is actively maintained and receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest (`latest` Docker tag) | ✅ |
| Older pinned versions | ❌ |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use GitHub's private reporting feature instead:

1. Go to the [Security tab](https://github.com/sdblepas/CinePlete/security) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details — what you found, steps to reproduce, and potential impact

You can also contact the maintainer directly via GitHub.

**Response commitment:**
- Acknowledgement within **48 hours**
- Assessment and triage within **5 days**
- Patch released within **14 days** for confirmed vulnerabilities

## Out of Scope

The following are not considered security vulnerabilities:

- Self-hosted misconfiguration (e.g. exposing the app to the internet without auth)
- TMDB or third-party API key exposure in user-managed config files
- Issues in Docker base images not yet patched upstream
- `localhost` connectivity issues (this is a Docker networking UX issue, not a CVE)

## Disclosure Policy

Once a fix is released, the vulnerability will be disclosed in the release notes with appropriate credit to the reporter (unless anonymity is requested).
