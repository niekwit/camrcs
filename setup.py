from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='camrcs',
    version='0.7.1',
    py_modules=['camrcs'], 
    description='A package for management of Cambridge Research Cold Storage backups',
    long_description=long_description,
    long_description_content_type='text/markdown',
    project_urls={
        'Documentation': 'https://camrcs.readthedocs.io',
        'Source': 'https://github.com/niekwit/camrcs',
    },
    author='Niek Wit',
    author_email='nw416@cam.ac.uk',
    license='MIT',
    packages=find_packages(),
    install_requires=['pandas','Click','numpy',
                      ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License', 
        'Operating System :: POSIX :: Linux', 
        'Programming Language :: Python :: 3',
        'Topic :: System :: Archiving :: Backup',
    ],
    entry_points={ ###check
        'console_scripts': [
            'camrcs = camrcs:cli',
        ],
    },
    include_package_data=True,
)
