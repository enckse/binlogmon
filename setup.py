#!/usb/bin/python


from setuptools import setup, find_packages
import binlogmon

setup(
    name='binlogmon',
    version=binlogmon.__version__,
    description='Binary log monitoring and alerting',
    url='https://github.com/epiphyte/binlogmon',
    license='MIT',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=['twilio'],
    entry_points={
        'console_scripts': [
            'binlogmon=binlogmon:main',
        ],
    },
)