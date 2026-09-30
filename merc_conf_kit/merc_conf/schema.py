from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Estimate:
    """One Verisk valuation (prefill or final)."""
    merc: float
    low: Optional[float]
    high: Optional[float]
    sqft: float
    iscore: Optional[float] = None
    valuation_id: Optional[str] = None


@dataclass
class Neighborhood:
    center: float   # blended median of log $/sqft
    spread: float   # 1.4826 * blended MAD
    n_r5: int       # comparable homes in the r5 cell


@dataclass
class Result:
    confidence: float
    tier: str
    main_driver: str
    reason: str
    flags: list = field(default_factory=list)
    z: Optional[float] = None
    waterfall: list = field(default_factory=list)
