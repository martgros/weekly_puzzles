# [InsideOpt Weekly Puzzles](https://www.linkedin.com/newsletters/insideopt-weekly-puzzle-7055208705293733889/)

This repository contains optimization problems and solutions to some of the *InsideOpt Weekly Puzzles* containing topics from *operations research* like optimization, planning & decision making.

Some are used with my preferred tools/solvers, some are investigated and solved by using InsideOpt Solver *Seeker*.

## 🚀 Quick Start

### License Configuration

This repository uses a **centralized license configuration system**. You only need to configure the license file once in a single location.

**Quick setup:**

1. Ensure your Seeker license file (`*.sio`) is in the `lic/` directory
2. Edit `lic/LICENSE_CONFIG.txt` to specify which license file to use
3. Use `get_license_path()` in your notebooks and scripts

**Example for notebooks:**

```python
import sys
sys.path.insert(0, '../..')
from seeker_utils import get_license_path

import seeker as skr
lic_path = get_license_path()

# Use throughout your notebook
env = skr.Env(lic_path, stochastic=True)
```