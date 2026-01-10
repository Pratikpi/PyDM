# PyDM: Python Asynchronous Download Manager

PyDM is a high-performance, segmented download manager built with Python's `asyncio`. It maximizes bandwidth utilization by downloading file segments concurrently and features robust resume capabilities.

## Features

- **Concurrent Downloading**: Splits files into segments and downloads them in parallel to maximize throughput.
- **Resume Capability**: Automatically resumes interrupted downloads from the exact byte where they stopped, using a robust state management system.
- **Efficiency**: Uses `asyncio` for efficient I/O handling on a single thread.
- **CLI Interface**: Clean command-line interface with real-time progress visualization using `tqdm`.

## Installation

### Prerequisites

- Python 3.9 or higher

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/Pratikpi/PyDM.git
   cd PyDM
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```
   This will install `pydm` and its dependencies.

## Usage

Once installed, you can use the `pydm` command directly:

```bash
pydm <URL> [OPTIONS]
```

### Options

- `URL`: The URL of the file to download (Required).
- `-o`, `--output <FILENAME>`: Specify the output filename. Autosuggested from URL if omitted.
- `-s`, `--segments <N>`: Number of segments to split the file into (Default: 8).
- `-c`, `--concurrency <N>`: Maximum number of concurrent connections (Default: 4).
- `-v`, `--verbose`: Enable verbose logging for debugging.

### Examples

**Basic download:**
```bash
pydm https://example.com/largefile.zip
```

**Download with 16 segments and saved as `my_archive.zip`:**
```bash
pydm https://example.com/largefile.zip -o my_archive.zip -s 16
```

## Development

### Project Structure

```
PyDM/
├── src/pydm/           # Source code
│   ├── core/           # Core downloader logic and models
│   ├── utils/          # File operations and helpers
│   └── cli/            # Command line interface
├── tests/              # Unit tests
├── info.md             # Project requirements and design doc
└── pyproject.toml      # Project metadata and dependencies
```

### Running Tests

To run the test suite:

```bash
pytest tests/
```
