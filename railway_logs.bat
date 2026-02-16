@echo off
set RAILWAY_TOKEN=cc2b9c31-5d95-4e0c-8a45-dcbec0b9bdb0
call npx @railway/cli whoami
call npx @railway/cli logs --service ldip-worker -n 50
