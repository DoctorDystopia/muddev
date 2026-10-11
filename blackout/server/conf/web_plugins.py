"""
Web plugin hooks.
"""

from systems.interface.serverstatus import status


def at_webserver_root_creation(web_root):
    """
    This is called as the web server has finished building its default
    path tree. At this point, the media/ and static/ URIs have already
    been added to the web root.

    Blackout adds /status.json here, outside Django, for the status light
    on the website. See systems/interface/serverstatus/status.py.

    Args:
        web_root (twisted.web.resource.Resource): The root
            resource of the URI tree. Use .putChild() to
            add new subdomains to the tree.

    Returns:
        web_root (twisted.web.resource.Resource): The potentially
            modified root structure.

    Example:
        from twisted.web import static
        my_page = static.File("web/mypage/")
        my_page.indexNames = ["index.html"]
        web_root.putChild("mypage", my_page)

    """
    return status.mount(web_root)


def at_webproxy_root_creation(web_root):
    """
    This function can modify the portal proxy service.
    Args:
        web_root (evennia.server.webserver.Website): The Evennia
            Website application. Use .putChild() to add new
            subdomains that are Portal-accessible over TCP;
            primarily for new protocol development, but suitable
            for other shenanigans.
    """
    return web_root
