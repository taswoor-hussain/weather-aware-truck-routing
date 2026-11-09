class UpstreamError(Exception):
    """A third-party API failed; the message is safe to show to the user."""


class NoRouteError(Exception):
    """No drivable truck route exists between the requested points."""
