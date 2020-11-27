from pathlib import Path
from subprocess import check_call

from poetry_publish.publish import poetry_publish
from semver import parse_version_info

import mause_rpc

version = parse_version_info(mause_rpc.__version__).bump_patch()

with open('mause_rpc/__init__.py', 'w') as fh:
    fh.write(f'__version__ = \'{version}\'\n')


check_call(['git', 'changelog', '--tag', str(version)])
check_call(['poetry', 'version', str(version)])
check_call(['git', 'add', 'pyproject.toml', 'mause_rpc/__init__.py', 'History.md'])
check_call(['git', 'commit', '-m', f'Bump to {version}'])

poetry_publish(
    package_root=Path(mause_rpc.__file__).parent.parent,
    version=str(version),
)
