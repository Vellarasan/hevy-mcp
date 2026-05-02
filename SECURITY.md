# Security policy

## Supported versions

Only the latest minor release of `hevy-mcp` receives security fixes.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security problems.**

Email the maintainers privately or use GitHub's "Report a vulnerability" feature on the repository's *Security* tab. We aim to acknowledge reports within 72 hours and ship a fix or mitigation within 14 days for high-severity issues.

## What's in scope

- The MCP server itself (`src/hevy_mcp/`)
- The Docker image and deployment instructions in this repo

## What's out of scope

- Vulnerabilities in the Hevy API itself — report those to Hevy.
- Issues that require an attacker to already have your `HEVY_API_KEY`.

## Handling your API key

`hevy-mcp` never logs your API key. It is read from the `HEVY_API_KEY` environment variable (stdio mode) or accepted as a request header in HTTP mode. If you suspect a key has been exposed, rotate it immediately at <https://hevy.com/settings?developer>.
