# PyWX Copilot Instructions

## Project Overview
PyWX is a multi-component system that provides:
1. IRC bot functionality through `pythabot.py`
2. Weather information service and various command modules
3. Scanner alert monitoring, transcription, and notification system
4. Web interface for viewing alerts and events through Flask

## Architecture and Components

### Core Components
- **IRC Bot (`pythabot.py`)**: Connects to IRC servers, processes commands, and sends messages to channels
- **Module System (`modules/`)**: Extensible command and parser system with a registry pattern
- **Weather Services (`modules/weather.py`)**: Weather data fetching and formatting
- **Alert System (`modules/alerts.py`, `transcribe_alerts.py`)**: Monitors emergency alerts, transcribes audio, and sends notifications
- **Web Interface (`webscanner.py`)**: Flask application for viewing alert data

### Data Flow
1. The system processes incoming IRC messages through registered command handlers
2. Scanner alerts are pulled from external sources, transcribed using Whisper, and stored in SQLite
3. Alert data is processed, geocoded, and analyzed before being displayed in the web UI or sent to IRC

## Key Patterns and Conventions

### Module Registration System
Commands are registered using decorators:
```python
# Register a command that responds to !command in IRC
@register(['commandname'])
class MyCommand(base.Command):
    template = "Response template with {{ variables }}"

    def context(self, msg):
        # Process command and return template context
        return {'variables': 'values'}

# Register a periodic task
@register_periodic('task_name', run_every=60)
class PeriodicTask(base.Command):
    # Will run every 60 seconds

# Register a parser for passive message processing
@register_parser
class MyParser(base.ParserCommand):
    def parse(self, msg):
        # Process and return responses
```

### Template System
Responses use Jinja2 templates with IRC color filters:
```python
template = "Temperature: {{ temp|c('red') }} | Wind: {{ wind|c('aqua') }}"
```

## Development Workflow

### Local Development
1. Create `data/local_config.json` based on `example_config.py`
2. Run the bot directly: `python pywx.py`
3. Run the web interface: `flask --app webscanner run --debug`

### Docker Deployment
```bash
# Build and run in docker
docker build -t pywx .
docker run -it --mount type=bind,source=./data,target=/data -p 8080:443 pywx
```

### Database Operations
- Scanner alerts are stored in SQLite at `data/alerts.db`
- Weather data is stored in `data/pywx.db`
- Use the `copy-db-from-prod` task to fetch production database

## Important Files
- `pythabot.py`: IRC bot implementation
- `modules/registry.py`: Command registration system
- `modules/base.py`: Base classes for commands and parsers
- `transcribe_alerts.py`: Alert processing system
- `webscanner.py`: Web interface
- `supervisord.conf`: Service configuration for production

## Testing and Debugging
- Run the Flask server in debug mode: `flask --app webscanner run --debug`
- Most components log to standard output with proper logging setup

## Integrations
- OpenAI Whisper for audio transcription
- Google Maps API for geocoding
- Various weather APIs (OWM, ForecastIO)
- IRC servers for bot communication