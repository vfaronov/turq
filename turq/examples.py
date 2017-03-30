import pkgutil
import xml.etree.ElementTree

import docutils.core


def load_pairs():
    # Load pairs of "example ID, rules code" for the test suite.
    rst_code = _load_rst()
    xml_code = docutils.core.publish_string(rst_code, writer_name='xml')
    tree = xml.etree.ElementTree.fromstring(xml_code)
    parsed = []
    for section in tree.findall('./section'):
        slug = section.get('ids').replace('-', '_')
        for i, block in enumerate(section.findall('./literal_block'), start=1):
            parsed.append(('%s_%d' % (slug, i), block.text))
    return parsed


def load_html(initial_header_level):
    # Render an HTML fragment ready for inclusion into a page.
    rst_code = _load_rst()
    parts = docutils.core.publish_parts(
        rst_code, writer_name='html',
        settings_overrides={'initial_header_level': initial_header_level})
    return parts['fragment']


def _load_rst():
    return pkgutil.get_data('turq', 'examples.rst')
