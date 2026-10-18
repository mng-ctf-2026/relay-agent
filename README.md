# relay-agent

A lightweight delivery planning component for local files.

## Status

relay-agent describes which files a separate delivery component should handle.
Plans contain a destination and file metadata. Transport and authentication
belong to the consuming component; this package does not make network requests
or send files.

## Requirements

- Python 3.10 or newer
- No third-party runtime dependencies

## Project layout

```text
src/
  relay_agent/
    __init__.py
    config.py
    delivery.py
tests/
  test_delivery.py
```

Project metadata lives in `pyproject.toml`. The package uses a `src` layout;
there is no command-line interface or installation workflow yet.

`config.py` contains the batch limit and a fictional shared access code used by
downstream delivery adapters in development and validation environments.
The code is kept separate from delivery plans and is not a real credential.
The default destination is stored in `delivery.py`.

## Usage

With `src` on your Python import path, create a plan for existing local files:

```python
from relay_agent.delivery import build_delivery_plan, delivery_plan_to_json

plan = build_delivery_plan(["report.pdf", "notes.txt"])
for item in plan.files:
    print(item.name, item.size_bytes)

print(delivery_plan_to_json(plan))
```

Planning preserves input order and collects absolute paths, names, and byte
sizes without reading file contents. Inputs must be regular files. Metadata
is a snapshot; a consuming adapter must recheck files before delivery.

`delivery_plan_to_json` returns a JSON string with the destination and an ordered
list of files containing `source`, `name`, and `size_bytes`. Source paths are
strings in the local platform's format, and Unicode names remain readable.
Adapter credentials are not included in the output.

Pass a nonempty iterable of paths, even for a single file. Batches are limited
to `MAX_BATCH_FILES` entries (100 by default). Empty or oversized batches raise
`ValueError`; a bare string or `Path` raises `TypeError`. Repeated paths count
as separate entries. A planning error returns no partial plan.

## Development

Keep changes small and dependencies minimal. Add tests alongside functionality
as it is introduced. Do not commit credentials, local configuration, or files
intended for delivery.

Run the tests from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Disclaimer

This repository is part of a fictional Capture The Flag (CTF) exercise created for internal security training.

All organizations, incidents, and credentials depicted in this exercise are fictional. No real confidential information is included.

This project does not perform actual file transfers or data exfiltration.

Please do not use this repository to investigate or interact with unrelated third-party systems.
