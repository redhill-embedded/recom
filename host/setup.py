
from setuptools import setup

from recom import __version__

setup(
    name='recom',
    packages=['recom'],
    setup_requires=['setuptools_scm'],
    version=__version__,
    license='MIT',
    author='Adrian Rothenbuhler',
    author_email='adrian@redhill-embedded.com',
    description='Embedded communication backend',
    keywords='embedded communication backedn usb serial',
    url='https://github.com/redhill-embedded/retool.git',
    #download_url='https://github.com/redhill-embedded/sertool/archive/v_010.tar.gz',
    package_data={
        "recom": [
            "package_version"
        ]
    },
    python_requires=">=3.8",
    install_requires=["pyusb", "pyserial"],
    entry_points={
        "console_scripts": [
            "recom=recom.__main__:main",
        ]
    },
)