import setuptools
import sys

for arg in sys.argv:
    if arg in ('upload', 'register', 'testarg'):
        print('This setup is not designed to be uploaded or registered.')
        sys.exit(-1)

setuptools.setup(
    name="av1clip",
    version="1.0.0",
    packages=setuptools.find_packages(),
    install_requires=[],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "av1clip = av1clip.av1clip",
        ]
    },
)
