import os
from setuptools import setup, find_packages
import setuptools_scm

def git_describe_version(version):
    """
    Mimics Git's semantic versioning in a PEP 440 compliant way.

    - If the current commit exactly matches a tag, return that tag (e.g., "0.1.0").
    - Otherwise, return "tag.dev<distance>+g<node>" (e.g., "0.1.0.dev33+g66d759e").
    - Append ".dirty" if the working directory has uncommitted changes.
    """
    if version.distance == 0:
        base = version.tag
    else:
        # Create a development release segment.
        base = f"{version.tag}.dev{version.distance}+g{version.node}"
    if version.dirty:
        base += ".dirty"
    return base

# Determine the repo root
this_directory = os.path.abspath(os.path.dirname(__file__))
repo_root = os.path.abspath(os.path.join(this_directory, ".."))

# Determine the version of this package
version = setuptools_scm.get_version(
    root=repo_root,
    relative_to=os.path.join(repo_root, "python_package", "pyproject.toml"),
    version_scheme=git_describe_version,  # our custom function handles everything
    local_scheme=lambda version: ""       # disable any extra local scheme processing
)

setup(
    name='recom',
    version=version,
    packages=find_packages(),
    setup_requires=['setuptools_scm'],
    license='MIT',
    author='Adrian Rothenbuhler',
    author_email='adrian@redhill-embedded.com',
    description='Embedded communication backend',
    keywords='embedded communication backedn usb serial',
    url='https://github.com/redhill-embedded/recom.git',
    #download_url='https://github.com/redhill-embedded/sertool/archive/v_010.tar.gz',
    package_data={
        "recom": [
            "package_version"
        ]
    },
    python_requires=">=3.8",
    install_requires=["libusb1", "pyserial", "pyudev", "psutil"],
    entry_points={
        "console_scripts": [
            "recom=recom.__main__:main",
        ]
    },
)