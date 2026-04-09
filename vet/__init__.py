"""
V.E.T. — Vendor Entity Threat Detection
An AI-Powered Data Fusion Framework for U.S. Supply Chain Security

Author: Arthunya Kanoklertwongse
DOI: 10.13140/RG.2.2.33961.76641
License: MIT
"""

from .models.risk_scorer import RiskScorer as VETScorer
from .config import VETConfig

__version__ = "0.1.0-alpha"
__author__ = "Arthunya Kanoklertwongse"
__doi__ = "10.13140/RG.2.2.33961.76641"

__all__ = ["VETScorer", "VETConfig"]
