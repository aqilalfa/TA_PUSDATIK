# Plan: Cloudflare Tunnel Local Server Deployment

## Goal
Expose the local SPBE RAG Docker production stack to users on different networks through Cloudflare Tunnel, without exposing backend or Qdrant directly.

## Constraints
- Local PC remains the server.
- Public access must enter through Cloudflare Tunnel.
- Frontend nginx is the only public-facing application service.
- Backend FastAPI and Qdrant stay private inside Docker network.
- Do not commit tunnel token or secrets.

## Implementation Summary
1. Use `docker-compose.prod.yml` for production stack.
2. Add `docker-compose.cloudflare.yml` for `cloudflared` sidecar.
3. Use `.env.cloudflare` for `CLOUDFLARED_TUNNEL_TOKEN`.
4. Make frontend API base URL same-origin by default when `VITE_API_URL` is empty.
5. Document manual Cloudflare UI steps in `docs/CLOUDFLARE_TUNNEL_DEPLOYMENT.md`.

## Acceptance Criteria
- `docker compose config` succeeds with prod + cloudflare files.
- Frontend production build does not hardcode `localhost` as API URL when `VITE_API_URL` is empty.
- `cloudflared` service depends on frontend and joins `spbe-network`.
- `.env.cloudflare` is ignored by git.
- Documentation gives exact run, stop, log, and verification commands.

## User Manual Steps
1. Copy `.env.docker.example` to `.env.docker`.
2. Copy `.env.cloudflare.example` to `.env.cloudflare`.
3. Create Cloudflare Tunnel in Zero Trust.
4. Paste token into `.env.cloudflare`.
5. Add public hostname pointing to `http://frontend:80`.
6. Run the combined docker compose command from the docs.
7. Test from a different network.
