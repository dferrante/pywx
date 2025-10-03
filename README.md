# PyWX

PyWX is a multi-component system providing weather information, emergency scanner alerts, and IRC bot functionality.

## Features

- **IRC Bot**: Interactive command-based bot responding to user queries
- **Weather Information**: Detailed weather data with custom formatting
- **Scanner Alert Monitoring**: Transcribes emergency scanner audio and sends notifications
- **Web Interface**: View and search emergency alerts and events

## Getting Started

### Prerequisites

- Python 3.9+
- SQLite
- FFmpeg (for audio processing)
- API keys for:
  - Google Maps (geocoding)
  - OpenWeatherMap and/or ForecastIO (weather data)
  - OpenAI (optional, for enhanced transcription)

### Installation

#### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/dferrante/pywx.git
   cd pywx
   ```

2. Create a configuration file:
   ```bash
   # Create data directory if it doesn't exist
   mkdir -p data
   # Copy the example config and edit as needed
   cp example_config.py data/local_config.json
   # Edit the config file with your API keys and settings
   ```

3. Install dependencies:
   ```bash
   # Using pip
   pip install -r requirements.txt
   # OR using the provided uv lock file
   uv sync --locked
   ```

### Running the Application

#### Run the IRC Bot

```bash
python pywx.py
```

#### Run the Web Interface

```bash
flask --app webscanner run --debug
```

#### Run Alert Transcription Service

```bash
python transcribe_alerts.py
```

### Docker Deployment

Build and run the application with Docker:

```bash
docker build -t pywx .
docker run -it --mount type=bind,source=./data,target=/data -p 8080:443 pywx
```

## Project Structure

- `pythabot.py`: Core IRC bot implementation
- `pywx.py`: Main application entry point
- `transcribe_alerts.py`: Scanner alert monitoring and transcription
- `webscanner.py`: Flask web interface
- `modules/`: Command modules and extensions
  - `registry.py`: Command registration system
  - `base.py`: Base classes for commands
  - `weather.py`: Weather data services
  - `alerts.py`: Alert notification functionality
  - *Various other service modules*
- `data/`: Configuration and database storage
  - `local_config.json`: Local configuration
  - `alerts.db`: SQLite database for scanner alerts
  - `pywx.db`: SQLite database for weather data

## Development

### Adding New Commands

Create a new module or extend an existing one using the registry pattern:

```python
from . import base
from .registry import register

@register(['mynewcommand'])
class MyNewCommand(base.Command):
    template = "Response: {{ result }}"

    def context(self, msg):
        # Process the command
        return {'result': 'Processed result'}
```

### Adding Periodic Tasks

Register tasks that run at specified intervals:

```python
from .registry import register_periodic

@register_periodic('periodic_task', run_every=300)  # Run every 5 minutes
class PeriodicTask(base.Command):
    template = "Periodic update: {{ result }}"

    def context(self, msg):
        # Periodic task logic
        return {'result': 'Updated data'}
```

### Working with Templates

Templates use Jinja2 with custom IRC color filters:

```python
template = "Weather: {{ temp|c('red') }} | Wind: {{ wind|c('aqua') }}"
```

## Database Operations

- Copy production database:
  ```bash
  # Run the predefined task
  # This requires SSH access to the production server
  rm data/alerts.db* && scp mach5@colin.home:/etc/pywx/mefi/alerts* data/
  ```

## License

[License Information]

## Acknowledgments

- OpenAI Whisper for audio transcription
- Google Maps API for geocoding
- Weather data providers (OpenWeatherMap, ForecastIO)
