# Tunnelling the game server

`game.playblackout.io` is served from this machine through an outbound
Cloudflare Tunnel -- `cloudflared` dials out and Cloudflare routes inbound
requests back down that connection.

> **Correction, 08/21/2026:** this file used to claim "nothing is port-forwarded
> and nothing listens on a public address". That is not true today. The game
> ports bind to `0.0.0.0`, Windows Firewall has inbound *Allow* rules for
> `python3.13.exe` on the **Public** profile, and `portal.log` records raw TCP
> peers with public addresses (`208.185.77.187`, `73.203.80.203`, and
> `158.69.55.82`, an OVH host that looks like a scanner). Tunnelled traffic
> arrives as `127.0.0.1` -- verified against a probe -- so those are genuinely
> direct connections reaching the origin and bypassing Cloudflare.
>
> Two consequences worth weighing. `SECURE_PROXY_SSL_HEADER` trusts
> `X-Forwarded-Proto` from *any* client, and a direct connection can set that
> header itself. And none of Cloudflare's protection applies on that path.
>
> Not changed here, because it is a product decision rather than a pure
> hardening one: telnet on 4000 cannot traverse the tunnel at all (see below),
> so binding the ports to `127.0.0.1` would cut off any player using a
> traditional MUD client.

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

## The service does not currently work -- read this before trusting it

As of 08/21/2026 the `Cloudflared` service is installed and reports "Running",
but it is serving nothing. The live tunnel is a **manually launched process**,
which means the site goes down when that terminal closes or the user logs out.

How to tell them apart -- only the real tunnel holds QUIC connections to the
edge (4 UDP endpoints):

```powershell
foreach ($p in (Get-Process cloudflared)) {
  $u = (Get-NetUDPEndpoint -OwningProcess $p.Id -EA SilentlyContinue | Measure-Object).Count
  "PID $($p.Id): UDP=$u"
}
```

A PID with `UDP=0` is inert. On 08/21 the service PID had 0 and the
bash-launched PID had 4.

**Why it is inert.** `cloudflared service install` was run without a token, so
per its own help text the service "look[s] for credentials in a configuration
file upon startup". Its config directory is the install directory, and the
file there contains only `logDirectory:` -- no `tunnel:`, no
`credentials-file:`, no `ingress:`. The Windows Event Log confirms the service
starts with no arguments at all:

```
Cloudflared service arguments: [C:\Program Files (x86)\cloudflared\cloudflared.exe]
```

**The fix** (requires an elevated shell; the service cannot be touched without
one). Copy the credentials and the real config into the service config
directory, then restart:

```powershell
$svc = "C:\Program Files (x86)\cloudflared"
Copy-Item "$env:USERPROFILE\.cloudflared\*.json" $svc   # the tunnel credentials
Copy-Item "$env:USERPROFILE\.cloudflared\config.yml" "$svc\config.yml" -Force
Add-Content "$svc\config.yml" "logDirectory: C:\Program Files (x86)\cloudflared"
Restart-Service Cloudflared
```

Then confirm the service PID has `UDP=4` using the snippet above, and only
after that stop the manual process -- never before, or the site drops.

> **`config.yml` in this directory is canonical.** It has to be copied to BOTH
> `%USERPROFILE%\.cloudflared\config.yml` (manual runs) and the service config
> directory above. Editing one and not the other is how the ingress rules
> silently drift apart.

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
