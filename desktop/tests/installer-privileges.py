"""Check built PE privilege manifests without running or installing either EXE."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pefile


def execution_level(executable: Path) -> str:
    levels = []
    with pefile.PE(str(executable)) as pe:
        for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if resource.id != pefile.RESOURCE_TYPE['RT_MANIFEST']:
                continue
            for name in resource.directory.entries:
                for language in name.directory.entries:
                    data = language.data.struct
                    xml = pe.get_data(data.OffsetToData, data.Size).rstrip(b'\0')
                    tree = ET.fromstring(xml)
                    levels.extend(element.attrib['level'] for element in tree.iter()
                                  if element.tag.endswith('}requestedExecutionLevel'))
    assert len(levels) == 1, (executable.name, levels)
    return levels[0]


if __name__ == '__main__':
    desktop = Path(__file__).resolve().parents[1]
    version = json.loads((desktop / 'package.json').read_text())['version']
    setup = desktop / 'dist' / f'NYXOR-Windows-{version}-preview-Setup.exe'
    app = desktop / 'dist' / 'win-unpacked' / 'NYXOR.exe'
    result = {'installer': execution_level(setup), 'application': execution_level(app)}
    assert result == {'installer': 'requireAdministrator', 'application': 'asInvoker'}, result
    print(json.dumps({'ok': True, **result}))
