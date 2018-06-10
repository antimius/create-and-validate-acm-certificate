from setuptools import setup

setup(name='acm_factory',
      version='0.1',
      description='Creates and validates an AWS ACM certificate automatically.',
      url='https://github.com/dylburger/create-and-validate-acm-certificate',
      author='dylburger',
      packages=['acm_factory'],
      install_requires=[
                'boto3==1.5.1',
                'botocore==1.8.15',
                'certifi==2017.11.5',
                'chardet==3.0.4',
                'docutils==0.14',
                'idna==2.6',
                'jmespath==0.9.3',
                'python-dateutil==2.6.1',
                'requests==2.18.4',
                'requests-file==1.4.2',
                's3transfer==0.1.12',
                'six==1.11.0',
                'tldextract==2.2.0',
                'urllib3==1.22'
      ],
      zip_safe=False)
