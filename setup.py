from setuptools import setup, find_packages

core_requirements = [
    # Core AIOps Dependencies
    'aiofiles>=24.1.0',
    'aiohttp>=3.11.10',
    'aiomqtt',
    'anyio',
    'asyncio-mqtt',
    'bcrypt>=4.2.1',
    'blinker',
    'boto3>=1.35.87',
    'celery>=5.4.0',
    'coverage>=7.6.9',
    'elasticsearch',
    'fastapi>=0.115.6',
    'flake8>=7.1.1',
    'flask',
    'flask-cors',
    'flask-socketio>=5.4.1',
    'gunicorn>=23.0.0',
    'jinja2>=3.1.4',
    'mypy>=1.13.0',
    'numpy',
    'openai',
    'tqdm',
    'networkx',
    'paho-mqtt',
    'pandas',
    'prophet',
    'prometheus-client',
    'psutil',
    'pyjwt',
    'pydantic',
    'python-dotenv',
    'python-jose>=3.3.0',
    'python-multipart>=0.0.20',
    'pyyaml>=6.0.2',
    'requests',
    'rich',
    'schedule',
    'scikit-learn>=1.6.1',
    'seaborn>=0.13.2',
    'sqlalchemy>=2.0.36',
    'uvicorn>=0.32.1',
    'watchdog>=6.0.0',
    's3transfer',
    'python-engineio',
    'httpx',
    'cmdstanpy',
    'python-socketio',
    'matplotlib'
]

dev_requirements = [
    # Development & Testing
    'black>=24.10.0',
    'pytest>=8.4.0',
    'pytest-asyncio>=0.25.0',
    'pre-commit>=4.0.1',
    'bump2version'
]

setup(
    name='aiops-dashboard',
    version="0.4.7",
    author='Muhammad Awais Turk',
    author_email='muhammmadawaisturk1@gmail.com',
    description='AIOps Dashboard for Real-Time Monitoring, Incident Management, and Self-Healing Automation',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/aiops-dashboard',  # Replace with your actual GitHub URL
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Topic :: System :: Monitoring',
        'Topic :: Software Development :: Artificial Intelligence',
        'Framework :: FastAPI',
        'Framework :: Flask'
    ],
    python_requires='>=3.8',
    install_requires=core_requirements,
    extras_require={
        'dev': dev_requirements
    },
    include_package_data=True,
    zip_safe=False,
)
