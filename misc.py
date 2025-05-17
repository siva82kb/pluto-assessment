"""
Module containing miscellaneous useful functions for the PLUTO full assessment protocol.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

def rangea_within_rangeb(rangea: tuple[float], rangeb: tuple[float]) -> bool:
    """
    Check if rangea is within rangeb.

    Args:
        rangea (tuple[float]): The first range (start, end).
        rangeb (tuple[float]): The second range (start, end).

    Returns:
        bool: True if rangea is within rangeb, False otherwise.
    """
    return rangea[0] >= rangeb[0] and rangea[1] <= rangeb[1]