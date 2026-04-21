"""S9: rule action message template rendering must be single-pass.

Previously `_render_template` chained `str.replace` calls, so a
user-supplied title like "Pay {priority} bill" would see its
`{priority}` placeholder substituted in the next pass — recursive
substitution that leaks context fields into title-as-input strings.
"""
from taskstore.rules.actions import _render_template
from taskstore.rules.context import RuleContext


def test_single_pass_does_not_recurse_through_user_content():
    # User put the literal string "{priority}" in their title. After
    # rendering "Title: {title}", the result must keep the priority
    # placeholder verbatim — it came from user input, not the template.
    ctx = RuleContext(issue={"title": "Pay the {priority} bill", "priority": 9})
    out = _render_template("Title: {title}", ctx)
    assert out == "Title: Pay the {priority} bill", out


def test_expected_placeholders_still_substitute():
    ctx = RuleContext(issue={"title": "foo", "priority": 2})
    assert _render_template("{title} @ p{priority}", ctx) == "foo @ p2"


def test_unknown_placeholders_pass_through_unchanged():
    ctx = RuleContext(issue={"title": "x"})
    assert _render_template("hello {unknown}", ctx) == "hello {unknown}"
