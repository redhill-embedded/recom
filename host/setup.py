import os
from setuptools import setup, find_packages
import setuptools_scm

def git_describe_version(version):
    """
    Produce a PEP 440 compliant version string mimicking `git describe --tags --dirty`.

    - If the current commit exactly matches a tag, return that tag.
      If the working directory is dirty, append a local version label, e.g., "0.1.1+dirty".
    - Otherwise, return "tag.dev<distance>+g<node>".
      If dirty, append ".dirty" to the local version segment.
    """
    if version.distance == 0:
        base = str(version.tag)
        if version.dirty:
            # Use the plus sign for local version if on a tag but dirty.
            base = f"{base}+dirty"
    else:
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