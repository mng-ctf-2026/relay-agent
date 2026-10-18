# relay-agent

A lightweight file delivery tool for simple, explicit workflows.

## Status

This repository contains the initial Python project scaffold. File delivery,
network communication, and authentication are not implemented yet.

## Requirements

- Python 3.10 or newer
- No third-party runtime dependencies

## Project layout

```text
src/
  relay_agent/
    __init__.py
```

Project metadata lives in `pyproject.toml`. The package uses a `src` layout;
there is no command-line interface or installation workflow yet.

## Development

Keep changes small and dependencies minimal. Add tests alongside functionality
as it is introduced. Do not commit credentials, local configuration, or files
intended for delivery.

## Disclaimer

This repository is part of a fictional Capture The Flag (CTF) exercise created for internal security training.

All organizations, incidents, and credentials depicted in this exercise are fictional. No real confidential information is included.

This project does not perform actual file transfers or data exfiltration.

Please do not use this repository to investigate or interact with unrelated third-party systems.
