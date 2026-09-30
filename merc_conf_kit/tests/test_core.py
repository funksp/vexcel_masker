import math

from merc_conf import core
from merc_conf.schema import Estimate as E, Neighborhood

NB = Neighborhood(math.log(184.10663734351203), 0.09872285246497434, 310)
H1 = (E(335_000, 306_000, 367_000, 1_950), E(372_000, 341_000, 405_000, 2_150), 3)
H2 = (E(380_000, 352_000, 410_000, 2_050), E(380_000, 352_000, 410_000, 2_050), 5)
H3 = (E(400_000, 364_000, 440_000, 2_200), E(300_000, 272_000, 331_000, 1_950), 2)


def test_home1_medium():
    r = core.score(*H1, NB)
    assert (r.tier, r.main_driver) == ("Medium", "Property Confidence Score")
    assert abs(r.confidence - 0.8485) < 1e-3
    assert [round(v, 3) for _, v in r.waterfall] == [0.970, 0.898, 0.852, 0.848]


def test_home2_high():
    r = core.score(*H2, NB)
    assert (r.tier, r.main_driver) == ("High", "Final MERC range") and abs(r.confidence - 0.9761) < 1e-3


def test_home3_low():
    r = core.score(*H3, NB)
    assert (r.tier, r.main_driver) == ("Low", "Neighborhood estimate") and abs(r.confidence - 0.4785) < 1e-3
    assert "-16%" in r.reason


def test_guardrails_cap_high():
    assert core.score(*H2, Neighborhood(NB.center, NB.spread, 12)).tier == "Medium"
    far = E(518_000, 480_000, 559_000, 2_050)
    assert core.score(far, far, 5, NB).tier == "Medium"


def test_missing_inputs():
    fin = H2[1]
    r = core.score(None, fin, 5, NB)
    assert r.tier == "Medium" and "no prefill MERC to compare" in r.flags
    assert core.score(None, E(380_000, None, None, 2_050), 5, NB).tier == "Low"
    assert "PCS missing; treated as 1" in core.score(*H2[:2], None, NB).flags
    assert core.score(H2[0], fin, 5, None).tier == "Medium"


def test_decimal_pcs_between_neighbors():
    assert core.sigma_pcs(4) < core.sigma_pcs(3.5) < core.sigma_pcs(3)
