"""
Global constants for the CiviCodeAPI.

This module contains constant values used across the application, such as
deadline options for violations.
"""

# Constants for deadline options and their corresponding values in days
DEADLINE_OPTIONS = [
    "Immediate",
    "1 day",
    "3 days",
    "7 days",
    "14 days",
    "30 days"
]
"""list[str]: Human-readable strings for violation deadline options."""

DEADLINE_VALUES = [0, 1, 3, 7, 14, 30]
"""list[int]: Corresponding day values for the deadline options."""
