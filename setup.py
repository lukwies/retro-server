from setuptools import setup,find_packages

setup(
	name='retro-server',
	version='0.1.0',
	description='end2end encrypted terminal messenger (server)',
	url='https://github.com/lukwies/retro-server',
	author='Lukas Wiese',
	author_email='luken@gmx.net',
	license='GPLv3+',

	packages=['retro_server'],

	install_requires=[
		'libretro',
	],

	# Create a globally accessable console script
	# named 'retro-server'
	entry_points={
		'console_scripts': [
			'retro-server=retro_server.main:main',
		],
	},
	classifiers=[
		"Development Status :: 3 - Alpha",
		"Environment :: Console",
		"Intended Audience :: Developers",
		"Intended Audience :: Education",
		"Intended Audience :: End Users/Desktop",
		"License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
		"Operating System :: POSIX",
		"Operating System :: POSIX :: Linux",
		"Programming Language :: Python :: 3.11",
		"Topic :: Communications",
		"Topic :: Communications :: Chat",
	]
)


