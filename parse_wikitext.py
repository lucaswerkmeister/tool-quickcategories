import flask
import mwapi # type: ignore


def parse_summary(session: mwapi.Session, summary: str) -> flask.Markup:
    """Parses a summary text or fragment into HTML."""

    response = session.get(action='parse',
                           summary=summary,
                           prop=[],
                           formatversion=2)
    summary_html = response['parse']['parsedsummary']
    return flask.Markup(summary_html)
