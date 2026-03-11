# Seeker License Configuration System

This directory contains the Seeker license files and a centralized configuration system to manage license file references across all notebooks and scripts.

centralized configuration system that allows you to:

1. Change the license file in ONE place
2. Automatically discover available license files
3. Keep all notebooks generic and portable

## Configuration Options

### Option 1: Manual Configuration (Recommended)

Edit the [LICENSE_CONFIG.txt](LICENSE_CONFIG.txt) file in this directory:

```text
# Simply put the filename of the .sio file you want to use
Seeker_Mustermann_123_lic.sio
```

### Option 2: Automatic Discovery

If `LICENSE_CONFIG.txt` is empty or doesn't specify a file, the system will automatically use the first `*.sio` file found in this directory.

## Usage in Notebooks

### For Jupyter Notebooks in `puzzles/*/` directories:

Add these lines at the start of your notebook:

```python
import sys
sys.path.insert(0, '../..')
from seeker_utils import get_license_path

import seeker as skr
lic_path = get_license_path()

# Now use lic_path with Seeker
env = skr.Env(lic_path, stochastic=True)
```

### For Python Scripts in the root directory:

```python
from seeker_utils import get_license_path

import seeker as skr

# Get absolute path for scripts
lic_path = get_license_path(from_notebook=False)
env = skr.Env(lic_path, stochastic=True)
```

### For Python Scripts in subdirectories:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from seeker_utils import get_license_path

import seeker as skr
lic_path = get_license_path()
```

## How It Works

1. The `seeker_utils.py` module (at repo root) provides the `get_license_path()` function
2. This function checks `lic/LICENSE_CONFIG.txt` for a configured license file
3. If not configured, it automatically discovers the first `*.sio` file in `lic/`

## Testing

To verify your setup:

```bash
# From repo root
python seeker_utils.py
```

This will print:

```text
License path for notebooks: ../../lic/Seeker_Grossbichler_329_lic.sio
License path (absolute): e:/Projects/.../lic/Seeker_Grossbichler_329_lic.sio
```
