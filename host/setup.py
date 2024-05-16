
from setuptools import setup, find_packages

setup(
    name='recom',
    version="0.0.3",
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