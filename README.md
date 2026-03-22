# Eero AdGuard Sync

Sync hostnames and identifiers from your Eero client list into AdGuard Home.

This fork is aimed at self-hosted use with Docker Compose and Synology-style pull deployments. The repo now supports:

- publishing a container image to GitHub Container Registry
- pulling a prebuilt image by default in Compose
- optional local image builds for development
- persisting the Eero session in a mounted data directory
- unattended scheduled syncs with Docker Compose
- explicit Eero network selection for multi-network accounts

## How It Works

`eag-sync` reads the devices known to your Eero account, converts them into AdGuard Home client entries, then:

- updates matching AdGuard clients by MAC address
- creates missing clients
- optionally deletes AdGuard clients that are no longer present in Eero

The sync is one-way: Eero is the source of truth.

## Important Caveat

Eero login still uses a verification-code flow. For unattended operation, you should do one interactive login first so the session cookie is cached in the mounted `/data` directory. After that, scheduled runs reuse the cached session until Eero invalidates it.

If Eero expires the session later, you can re-run one interactive login to refresh it.

## Environment Variables

These options are supported by the CLI and the included Compose setup:

| Variable | Required | Description |
| --- | --- | --- |
| `EAG_ADGUARD_HOST` | Yes | AdGuard Home base URL, for example `http://adguard-home:3000` |
| `EAG_ADGUARD_USER` | Yes | AdGuard Home admin username |
| `EAG_ADGUARD_PASSWORD` | Yes | AdGuard Home admin password |
| `EAG_EERO_USER` | First login | Eero email address or phone number |
| `EAG_EERO_NETWORK_ID` | No | Specific Eero network URL/ID to sync |
| `EAG_EERO_NETWORK_NAME` | No | Specific Eero network name to sync |
| `EAG_EERO_COOKIE` | No | Optional pre-captured Eero session cookie |
| `EAG_DATA_DIR` | No | Directory where the cached Eero session is stored |
| `EAG_CRON_SCHEDULE` | No | Cron schedule used by the container, default `0 * * * *` |
| `EAG_IMAGE` | No | Container image to run, default `ghcr.io/jimjudd/eero-adguard-sync:latest` |
| `EAG_DATA_VOLUME` | No | Host path to mount at `/data`, default `./data` |
| `EAG_DELETE` | No | Set to `true` to delete AdGuard clients missing from Eero |
| `EAG_OVERWRITE` | No | Set to `true` to clear AdGuard clients before sync |
| `TZ` | No | Container timezone |

If your Eero account has more than one network, set exactly one of `EAG_EERO_NETWORK_ID` or `EAG_EERO_NETWORK_NAME` for non-interactive runs.

## Docker Compose

The default [`docker-compose.yml`](/Users/jimjudd/Documents/python/eero-adguard-sync/docker-compose.yml) pulls a prebuilt image from GitHub Container Registry. This is the recommended path for Synology and Dockhand.

1. Copy the example env file:

```sh
cp .env.example .env
```

2. Edit `.env` with your AdGuard Home settings and Eero username.

3. If you have multiple Eero networks, set either `EAG_EERO_NETWORK_ID` or `EAG_EERO_NETWORK_NAME`.

4. Pull the image:

```sh
docker compose pull
```

5. Run an interactive first sync to complete Eero verification and cache the session in `./data`:

```sh
docker compose run --rm eag-sync eag-sync sync
```

6. Once that succeeds, start the scheduled container:

```sh
docker compose up -d
```

7. Watch logs:

```sh
docker compose logs -f eag-sync
```

The included [`docker-compose.yml`](/Users/jimjudd/Documents/python/eero-adguard-sync/docker-compose.yml) mounts `./data` into the container so the cached Eero session survives container restarts and image updates.

Container startup behavior:

- the container runs one sync immediately on startup
- if that first sync succeeds, cron is started for the regular schedule
- if that first sync fails, the container exits so the failure is visible in logs
- each sync run logs clear start and finish messages in addition to the CLI output from Eero and AdGuard authentication

If you want to build locally on a machine with a working Docker engine, use the override file:

```sh
docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker compose -f docker-compose.yml -f docker-compose.build.yml run --rm eag-sync eag-sync sync
```

## Synology Notes

For Synology or Dockhand, the usual flow is:

1. Put this repo in a folder on the NAS.
2. Create and edit `.env`.
3. Make sure the image exists in GHCR for your fork.
4. Pull and start the service from the repo without building locally.
5. Run the one-time interactive login from a shell on the NAS with `docker compose run --rm eag-sync eag-sync sync` if you are not copying an existing `session.cookie`.

If you prefer the Synology Container Manager UI, the same settings apply:

- mount a persistent folder to `/data`
- set the environment variables from `.env`
- use the default container command so cron stays running

If your NAS or Dockhand cannot build images because of an older Docker API, this pull-based deployment model avoids that problem entirely.

## GitHub Container Registry

This repo now includes a workflow at [.github/workflows/container-publish.yml](/Users/jimjudd/Documents/python/eero-adguard-sync/.github/workflows/container-publish.yml) that builds `docker/Dockerfile` and publishes tags to:

```text
ghcr.io/jimjudd/eero-adguard-sync
```

The workflow runs on:

- pushes to `master`
- tags that start with `v`
- published GitHub releases
- manual dispatch

For the first publish, make sure:

1. GitHub Actions is enabled for the repo.
2. The repo allows workflows to write packages.
3. The resulting GHCR package is visible to whatever will pull it.

After a successful workflow run on `master`, the Compose default tag will be:

```text
ghcr.io/jimjudd/eero-adguard-sync:latest
```

## CLI Usage

Run a one-off sync locally:

```sh
python3 -m eero_adguard_sync sync
```

Useful options:

```text
--adguard-host
--adguard-user
--adguard-password
--eero-user
--eero-cookie
--eero-network-id
--eero-network-name
-d, --delete
-o, --overwrite
-y, --confirm
--debug
```

You can also clear the cached Eero session:

```sh
python3 -m eero_adguard_sync clear
```

## What Changed In This Fork

- fixed Eero multi-network selection so the chosen network is actually used
- added explicit non-interactive network selection
- added environment-variable support for unattended runs
- made the auth cache location configurable with `EAG_DATA_DIR`
- switched Docker to install this fork inside the image
- added a GHCR publish workflow for registry-based deployments
- changed Compose to pull a prebuilt image by default, with an optional local build override
