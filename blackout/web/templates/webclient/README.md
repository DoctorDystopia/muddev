# RETIRED — the three.js webclient's page

**Status: retired 08/27/2026. Superseded by the Godot client in `godot/`.**
Still served, still working, and deliberately not removed — the reasons are in
[../../static/webclient/js/README.md](../../static/webclient/js/README.md).

`base.html` is the override that loads it. Removing the override would hand
`/webclient/` back to Evennia's stock client, which draws no Blackout panes, so
it is left in place.

---

## Original Evennia note

Replace Evennia's webclient django template with your own here.

You can find the original files in `evennia/web/templates/webclient/`. Just copy
the original here and modify - after a reload the new template will be used.
