"""Browser-render-grain assertions for the Telegram twin's explainer page.

The cheap-grain check (`assert_no_html_entity_in_css_content`) catches
HTML entities written into CSS content: declarations in the source. This
suite asserts the *rendered output* a user actually sees, which is the
correct grain for "the bullet glyph is a real arrow, not literal text".

Job 020 introduced the `&rarr;`-in-CSS bug. Job 021 fixed it for
telegram and added the cheap-grain check. Job 022 extracted shared
render assertions to `twins_local.testing.render` and propagated both
grains sibling-wide.
"""

import pytest

from twins_local.testing import (
    assert_explainer_renders_correct_bullet,
    assert_no_entity_artifacts_in_visible_text,
)

pytestmark = pytest.mark.render


def test_explainer_bullet_renders_as_arrow(page, live_server_url):
    assert_explainer_renders_correct_bullet(page, live_server_url)


def test_explainer_visible_text_has_no_entity_artifacts(page, live_server_url):
    assert_no_entity_artifacts_in_visible_text(page, live_server_url)
