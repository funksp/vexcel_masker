"""Method parameters (illustrative starting values). Humans tune these after shadow mode."""

TOL_UNDER, TOL_OVER = 0.10, 0.15      # MERC may be ~10% too low or ~15% too high
RANGE_Z = 1.645                       # Verisk ranges treated as 90% ranges
PCS_POINTS = [1, 2, 3, 4, 5]          # Property Confidence Score (5 = most reliable)
PCS_SIGMA = [0.12, 0.08, 0.05, 0.035, 0.02]   # leftover data risk; decimals interpolate
P_MEMBER_WRONG = 0.10                 # chance the member's changes are wrong
HIGH_CUT, LOW_CUT = 0.90, 0.70        # tier cutoffs on confidence
MIN_NEARBY, EXTREME_Z = 30, 3.0       # guardrails: homes in r5 cell; |z| of $/sqft
K_CRED = 25                           # H3 credibility constant
MAD_FLOOR = 0.02
MIN_SQFT = 400
SIZE_BANDS = [1800, 2500, 3500]       # band 0 <1800, 1 1800-2499, 2 2500-3499, 3 3500+
LEVELS = ["state", "h3_r4", "h3_r5", "h3_r6", "h3_r7"]   # coarse to fine
