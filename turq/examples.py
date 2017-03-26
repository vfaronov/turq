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


def _load_rst():
    return pkgutil.get_data('turq', 'examples.rst')
