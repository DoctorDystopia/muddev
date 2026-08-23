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

## Where the config lives

**One live file: `C:\ProgramData\cloudflared\config.yml`.** Both the Windows
service and manual runs read it, so there is nothing to keep in sync.

`config.yml` in this directory is the canonical source. It is a template --
substitute the tunnel id in two places when you copy it out. The credentials
JSON sits beside the live config in `C:\ProgramData\cloudflared\` and is
readable by both `LocalSystem` (the service) and your own account (manual runs),
which is what lets one file serve both.

> **Never put the live config in `C:\Program Files (x86)\cloudflared\`.**
> cloudflared **overwrites that file with a stub on every service start**. An
> earlier version of this README told you to copy it there; that advice could
> not work, and cost an afternoon on 08/22/2026. See the post-mortem below.

## One-time setup

```bash
winget install --id Cloudflare.cloudflared
cloudflared tunnel login
cloudflared tunnel create playblackout
cloudflared tunnel route dns playblackout game.playblackout.io
```

`create` prints a tunnel id and writes a credentials JSON into
`%USERPROFILE%\.cloudflared\`. Then, in an **elevated** shell, place the config
and credentials in the shared location and register the service:

```powershell
New-Item -ItemType Directory -Force "C:\ProgramData\cloudflared" | Out-Null
Copy-Item "$env:USERPROFILE\.cloudflared\<TUNNEL-ID>.json" "C:\ProgramData\cloudflared\"
# copy deploy/cloudflared/config.yml here, substituting the tunnel id
cloudflared service install
sc.exe config Cloudflared binPath= "C:\PROGRA~2\CLOUDF~1\cloudflared.exe --config C:\ProgramData\cloudflared\config.yml --no-autoupdate tunnel run"
sc.exe start Cloudflared
```

That `sc.exe config` line is **not optional** -- see the post-mortem.

## Everyday operations

Most of these need an **elevated** shell (the service cannot be touched without
one). Manual runs and read-only checks do not.

### Is it actually up?

Only a real tunnel holds QUIC connections to the edge (4 UDP endpoints). A PID
with `UDP=0` is inert -- running, serving nothing.

```powershell
Get-Process cloudflared | ForEach-Object { $u = (Get-NetUDPEndpoint -OwningProcess $_.Id -EA SilentlyContinue | Measure-Object).Count; "PID $($_.Id): UDP=$u" }
```

Git Bash equivalent:

```bash
for pid in $(tasklist //FI "IMAGENAME eq cloudflared.exe" //FO CSV //NH | cut -d, -f2 | tr -d '"'); do echo "PID $pid: UDP=$(netstat -ano -p UDP | grep -cE "[[:space:]]${pid}\$")"; done
```

End-to-end check, which is the one that actually matters:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://game.playblackout.io/
```

`200` is good. **`530` with body `error code: 1033`** means DNS is routing to
the tunnel correctly but no `cloudflared` is connected -- the tunnel is down,
not the DNS. `502` means the tunnel is up but Evennia is not (`evennia start`).

### Restart the service

```powershell
Restart-Service Cloudflared
```

If that hangs on `Waiting for service ... to stop`, the process is wedged.
A misconfigured cloudflared does not respond to the stop control and the
service sticks in `STOP_PENDING`. Force it:

```powershell
$svcPid = (Get-CimInstance Win32_Service -Filter "Name='Cloudflared'").ProcessId; Stop-Process -Id $svcPid -Force; Start-Sleep 3; sc.exe start Cloudflared
```

### Run it manually instead

Useful for watching live output, or when you do not want to elevate. **Stop the
service first** -- two instances on one tunnel both connect, and Cloudflare
splits traffic between them.

```powershell
Stop-Service Cloudflared
```

```bash
"/c/Program Files (x86)/cloudflared/cloudflared.exe" --config "C:\ProgramData\cloudflared\config.yml" tunnel run
```

Both paths must stay quoted in Git Bash -- unquoted, bash eats the backslashes
and turns `C:\ProgramData\...` into `C:ProgramData...`. The tunnel name is
omitted because the config already names it; passing both can conflict.

This dies when the terminal closes or you log out. Hand back to the service
with `Start-Service Cloudflared` (elevated) once you are done.

### Read the logs

```powershell
Get-ChildItem "C:\ProgramData\cloudflared\*.log" | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content -Tail 40
```

If **no log file exists at all**, the config is not being read. That is a
finding, not an inconvenience -- go check `binPath` and the `--config` path.

### Change the ingress rules

Edit `deploy/cloudflared/config.yml` (canonical), copy it to
`C:\ProgramData\cloudflared\config.yml` with the tunnel id substituted, then
`Restart-Service Cloudflared`. Confirm `UDP=4` and a `200` afterwards.

## Post-mortem: why the service was inert (fixed 08/22/2026)

For about a day the `Cloudflared` service reported "Running" while serving
nothing, and the live tunnel was a manually launched process -- so the site went
down whenever that terminal closed. **Two independent bugs**, and fixing either
one alone did nothing:

**1. The service had no arguments.** `cloudflared service install` was run
without a token, registering `binPath` as the bare executable:

```
Cloudflared service arguments: [C:\Program Files (x86)\cloudflared\cloudflared.exe]
```

No `--config`, no `tunnel run`. cloudflared then looks for a config in
`$HOME\.cloudflared\`, but the service runs as **LocalSystem**, whose home is
`C:\Windows\System32\config\systemprofile\` -- not `C:\Users\NickR\`. No config
was ever found there.

**2. cloudflared rewrites its own install-directory config.** The obvious fix --
copying the real config into `C:\Program Files (x86)\cloudflared\` -- is
defeated because cloudflared replaces that file with a `logDirectory:`-only stub
on every service start. Which is also why the previous investigator found only
that one line there and misread it as "the config was never filled in".

The fix is both halves: keep the config somewhere cloudflared does not manage
(`C:\ProgramData\cloudflared\`) **and** point the service at it explicitly.

```
BINARY_PATH_NAME : C:\PROGRA~2\CLOUDF~1\cloudflared.exe --config C:\ProgramData\cloudflared\config.yml --no-autoupdate tunnel run
START_TYPE       : 2  AUTO_START
```

Short (8.3) paths avoid quoting problems with `sc.exe`; `C:\ProgramData\...`
has no spaces and needs none.

Two traps worth naming, both of which cost time:

- **`logDirectory:` is not a real key.** The correct one is `log-directory`
  (kebab-case, matching the CLI flag). cloudflared ignores unknown keys
  silently, so the service produced no logs whatsoever -- which is precisely
  why it stayed undiagnosable. cloudflared's own stub uses `logDirectory:`;
  that does not make it valid.
- **`Set-Content -Encoding utf8` writes a BOM** in Windows PowerShell 5.1, and
  cloudflared's YAML parser rejects it (service exits `1067`). Use
  `[IO.File]::WriteAllLines($path, $lines)`, which writes UTF-8 without a BOM.

## Is any of this fighting the Cloudflare dashboard?

No, and it is worth knowing why, because the two configs look adjacent.

| Hostname | Backend |
|---|---|
| `playblackout.io` (apex) | Worker `playblackout-site` (Astro static site) |
| `game.playblackout.io` | CNAME to `<tunnel-id>.cfargotunnel.com` -- this tunnel |

They do not overlap. A Worker **Custom Domain** is an exact-hostname binding, so
`playblackout.io` does not capture subdomains, and the Worker has no Routes.

> **Do not add a Worker route like `*.playblackout.io/*`.** A wildcard route
> *would* capture `game.` and swallow the tunnel. Custom Domains on the apex are
> safe; wildcard Routes are not.

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
