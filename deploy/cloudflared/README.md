# Tunnelling the game server

`game.playblackout.io` is served from this machine through an outbound
Cloudflare Tunnel. Nothing is port-forwarded and nothing listens on a public
address -- `cloudflared` dials out and Cloudflare routes inbound requests back
down that connection.

## One-time setup

```bash
winget install --id Cloudflare.cloudflared
cloudflared tunnel login
cloudflared tunnel create playblackout
cloudflared tunnel route dns playblackout game.playblackout.io
```

`create` prints a tunnel id and writes a credentials JSON into
`%USERPROFILE%\.cloudflared\`. Put both into `config.yml`, then copy it to
`%USERPROFILE%\.cloudflared\config.yml`.

## Run it

```bash
cloudflared tunnel run playblackout
```

Once that works, install it as a Windows service so it survives reboots:

```bash
cloudflared service install
```

## Ports it expects

| Port | Serves | Set by |
|---|---|---|
| 4001 | Evennia webserver (site + webclient page) | `WEBSERVER_PORTS` |
| 4002 | Webclient websocket | `WEBSOCKET_CLIENT_PORT` |
| 4008 | Godot 3D client websocket | `GODOT_CLIENT_WEBSOCKET_PORT` |
| 4000 | Telnet | `TELNET_PORTS` |

## Two ports that are not routed, on purpose

**Telnet (4000)** cannot be exposed this way. Cloudflare Tunnel carries
arbitrary TCP only if the *client* also runs `cloudflared access tcp`, which no
ordinary MUD player will do. Reaching traditional clients (Mudlet, TinTin++)
needs a cheap VPS running a TCP proxy back over the tunnel. Until that exists,
the browser client is the only way in.

**Godot websocket (4008)** is bound to `127.0.0.1` in `settings.py` and has no
ingress rule yet. Adding one means picking a path prefix that the Godot client
also sends; verify against the contrib before routing it.
