from setuptools import setup, find_packages

setup(
    name="conference-transcription-bot",
    version="1.0.0",
    description="Automatically joins, transcribes, and summarizes online conference lectures",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "playwright>=1.40.0",
        "openai>=1.12.0",
        "anthropic>=0.18.0",
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
        "scipy>=1.11.0",
        "python-dotenv>=1.0.0",
        "click>=8.1.7",
        "pydub>=0.25.1",
        "httpx>=0.25.0",
    ],
    entry_points={
        "console_scripts": [
            "conference-bot=conference_bot.bot:main",
        ]
    },
)
