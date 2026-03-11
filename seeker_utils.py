"""Utility functions for Seeker notebooks and scripts.

This module provides convenient functions for working with Seeker,
including automatic license path resolution.
"""

from pathlib import Path
from typing import Optional


def get_license_path(from_notebook: bool = True) -> str:
    """Get the path to the Seeker license file.

    This function automatically finds the .sio license file in the lic directory.
    It first checks for a LICENSE_CONFIG.txt file, and if not found or empty,
    it automatically discovers the first .sio file.

    Args:
        from_notebook: If True (default), returns relative path suitable for
                      notebooks in puzzles/*/ directories (../../lic/filename.sio).
                      If False, returns absolute path.

    Returns:
        Path to the license file as a string.

    Raises:
        FileNotFoundError: If no .sio license file is found.

    Examples:
        # In a notebook (puzzles/*/notebook.ipynb):
        >>> import sys
        >>> sys.path.insert(0, '../..')
        >>> from seeker_utils import get_license_path
        >>> lic_path = get_license_path()
        >>> # Returns: "../../lic/Seeker_Grossbichler_329_lic.sio"

        # In a Python script at root:
        >>> from seeker_utils import get_license_path
        >>> lic_path = get_license_path(from_notebook=False)
        >>> # Returns: "e:/Projects/.../lic/Seeker_Grossbichler_329_lic.sio"
    """
    # Find lic directory
    root_dir = Path(__file__).parent
    lic_dir = root_dir / "lic"

    if not lic_dir.exists():
        raise FileNotFoundError(f"License directory not found: {lic_dir}")

    # Check for config file
    config_file = lic_dir / "LICENSE_CONFIG.txt"
    license_filename = None

    if config_file.exists():
        # Read the config file
        content = config_file.read_text().strip()
        # Find first non-empty, non-comment line
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                license_filename = line
                break

    # If no config or config is empty, auto-discover
    if not license_filename:
        sio_files = list(lic_dir.glob("*.sio"))
        if not sio_files:
            raise FileNotFoundError(
                f"No .sio license file found in {lic_dir}. "
                "Please ensure a Seeker license file (*.sio) is present."
            )
        license_filename = sio_files[0].name

    # Build the full path
    license_path = lic_dir / license_filename

    # Verify the file exists
    if not license_path.exists():
        raise FileNotFoundError(
            f"License file specified in config not found: {license_path}"
        )

    # Return appropriate format
    if from_notebook:
        return f"../../lic/{license_filename}"
    else:
        return str(license_path)


if __name__ == "__main__":
    # Test the function
    print("License path for notebooks:", get_license_path(from_notebook=True))
    print("License path (absolute):", get_license_path(from_notebook=False))
