# relay-agent

A lightweight delivery planning component for local files.

## What it does

relay-agent describes which files a separate delivery component should handle.
Plans contain a destination and file metadata. Transport and authentication
belong to the consuming component; this package does not make network requests
or send files. Planning inspects filesystem metadata without reading file
contents. It does not upload, copy, rename, or modify the input files.

## Requirements

- Python 3.10 or newer
- No third-party runtime dependencies

## Install for local use

Start with a local checkout of this repository and open a terminal in its root.
The source checkout can be used directly in an isolated Python environment;
no package downloads or third-party dependencies are needed.

On Windows with PowerShell:

```powershell
python -m venv --without-pip .venv
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -c "import relay_agent; print('relay-agent is ready')"
```

On Linux or macOS:

```sh
python3 -m venv --without-pip .venv
export PYTHONPATH="$PWD/src"
.venv/bin/python -c "import relay_agent; print('relay-agent is ready')"
```

Keep using the same terminal for the examples below. Set `PYTHONPATH` again
when opening a new terminal. This is a source-based setup, not a system-wide
package installation. The package provides a Python API, not a command-line
interface.

## Create a delivery plan

Choose existing local files and save the following as `plan_local.py`, replacing
the example paths with your own. Relative paths are interpreted from the
process's current working directory, not the script's location.

```python
from pathlib import Path

from relay_agent.delivery import build_delivery_plan, delivery_plan_to_json

plan = build_delivery_plan([Path("report.pdf"), "notes.txt", "report.pdf"])
print("Destination:", plan.destination)
for item in plan.files:
    print(item.source, item.name, item.size_bytes)
```

Run the script from that directory using the configured environment:

```powershell
.\.venv\Scripts\python.exe .\plan_local.py
```

On Linux or macOS, use `.venv/bin/python plan_local.py`.

`build_delivery_plan(paths)` accepts an iterable of strings or `Path` objects
and returns a `DeliveryPlan`. Its `files` tuple contains immutable `PlannedFile`
records with these fields:

| Field | Meaning |
| --- | --- |
| `source` | Resolved absolute `Path` for the local file |
| `name` | Source filename normalized to Unicode NFC |
| `size_bytes` | File size in bytes; empty files have size zero |

The example includes `report.pdf` twice, so it appears once in the plan, followed
by `notes.txt`. Normalizing `name` does not rename the local file. Metadata is
a snapshot; a consuming adapter must recheck files before delivery.

## JSON output

Append this to the example script to print the plan as JSON:

```python
output = delivery_plan_to_json(plan)
print(output)
```

`delivery_plan_to_json(plan)` returns a string with a top-level `destination`
and a `files` array. Each file contains `source`, `name`, and `size_bytes`.
File order is preserved, sizes are JSON numbers, and Unicode names remain
readable. Paths are strings using the local platform's format, with characters
escaped as required by JSON. Adapter credentials are not included.

Returning or printing this JSON does not contact the destination. Pass the plan
to a separate delivery component if you need actual file transfer.

## Input validation and duplicate files

Pass a nonempty iterable, even for one file: `build_delivery_plan(["report.pdf"])`.
Every input must resolve to an existing regular file. Symbolic links to regular
files are followed. Directories and special files are rejected. File extensions
are not restricted and file contents are not inspected.

Batches are limited to `MAX_BATCH_FILES` distinct files (100 by default), after
duplicate removal. The first occurrence and its order are retained. Relative
paths, absolute paths, and symbolic links are resolved before comparison. File
identity also recognizes hard links when the filesystem provides inode numbers;
otherwise comparison uses resolved paths. Distinct files with identical names
or contents remain separate, including names that become equal after NFC
normalization.

| Input problem | Exception |
| --- | --- |
| Empty iterable, including an exhausted iterator | `ValueError` |
| More than the configured number of distinct files | `ValueError` |
| A bare string or `Path` instead of an iterable of paths | `TypeError` |
| Missing file or missing parent | `FileNotFoundError` |
| Permission denied while inspecting a path | `PermissionError` |
| A parent component is not a directory, when reported by the OS | `NotADirectoryError` |
| Directory or special file supplied as an input | `ValueError` |

Path errors identify the affected input and cause. The filesystem exceptions
above retain the original exception as their cause and preserve its error number.
Other filesystem errors can propagate from the operating system. A planning
error raises an exception rather than returning a partial plan.

## Configuration

`config.py` contains the batch limit and a fictional shared access code used by
downstream delivery adapters in development and validation environments.
The code is kept separate from delivery plans and is not a real credential.
The default destination is stored in `delivery.py`. An adapter can consume a plan with an explicit destination:

```python
from relay_agent.delivery import DeliveryPlan

adapter_plan = DeliveryPlan(
    files=plan.files,
    destination="https://archive.example.invalid/v1/files",
)
```

This only changes the metadata in the new plan; it does not initiate a transfer.
Directly constructing `DeliveryPlan` does not validate paths or apply batch
rules. Use `build_delivery_plan` to collect and validate local files first.

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

Project metadata lives in `pyproject.toml`. Runtime code uses only the Python
standard library.

## Development

Keep changes small and dependencies minimal. Add tests alongside functionality
as it is introduced. Do not commit credentials, local configuration, or files
intended for delivery.

After the local setup above, run all tests from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux or macOS, use `.venv/bin/python -m unittest discover -s tests -v`.
Tests create their own temporary files and do not require a delivery service.

## Disclaimer

This repository is part of a fictional Capture The Flag (CTF) exercise created for internal security training.

All organizations, incidents, and credentials depicted in this exercise are fictional. No real confidential information is included.

This project does not perform actual file transfers or data exfiltration.

Please do not use this repository to investigate or interact with unrelated third-party systems.
