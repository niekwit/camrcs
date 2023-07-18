from setuptools import setup, find_packages
#from pathlib import Path

#this_directory = Path(__file__).parent
#long_description = (this_directory / "README.rst").read_text()

setup(
    name='camrcs',
    version='0.5',
    py_modules=['camrcs'], 
    description='A package for management of Cambridge Research Cold Storage backups',
    #long_description=long_description,
    #long_description_content_type='text/x-rst',
    project_urls={
        'Documentation': 'https://github.com/niekwit/camrcs',
        'Source': 'https://github.com/niekwit/camrcs',
    },
    author='Niek Wit',
    author_email='nw416@cam.ac.uk',
    license='MIT',
    packages=find_packages(),
    install_requires=['pandas','Click','sphinx-click','numpy',
                      ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT', 
        'Operating System :: POSIX :: Linux', 
        'Programming Language :: Python :: 3',
    ],
    entry_points={ ###check
        'console_scripts': [
            'camrcs = camrcs:cli',
        ],
    },
    include_package_data=True,
)
