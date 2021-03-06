from astropy import units as u
from math import atan
import numpy as np


class sim_constants():
    m_hole = 4.0e6
    m_bulge = 3.76e9
    m_disk = 6.0e10
    m_halo = 1.0e12

    # All distances initialized in AU:
    r_halo = 4.125e9

    # Bulge and disk parameters
    ab = 2.0e7
    ad = 5.7e8
    bd = 6.2e7

    # Nuclear cluster parameters
    rc = (1.0 * u.pc).to('AU').value

    # Additional constants
    scale = (1.0e3 * u.pc).to('AU').value  # 1 kpc converted to AU
    AUtokm = (1.0 * u.AU).to('km').value  # 1 AU converted to km
    AUtoRsun = (1.0 * u.AU).to('Rsun').value  # 1 AU converted to Rsun
    RsuntoAU = (1.0 * u.Rsun).to('AU').value  # 1 Rsun converted to AU

    # Constants for smoothing functions
    sf1 = 1.0e8
    sf2 = 1.0e4


def smoothing_func(r):
    return ((1.0 / np.pi) * atan((r - sim_constants.sf1) /
            sim_constants.sf2) + 0.5)
    # smoothing function is necessary
    # for integrator to handle logterm


def logterm(r):
    return np.log(1.0 + (r / sim_constants.r_halo))


def rterm(r):
    return (r + sim_constants.r_halo) * (r**2)


# For now, cluster_force is unnecessary
def cluster_force(r, coord):
    return 0
#     return (-2 * sim_constants.m_hole * coord /
#             (sim_constants.rc * r**2))
    # return (-2 * sim_constants.m_hole * coord /
    #         (max(sim_constants.rc, r) * r**2))


def bulge_force(r, coord):
    # return 0
    return -sim_constants.m_bulge * coord / ((r**2) * (sim_constants.ab + r))
    # return -sim_constants.m_bulge * coord / (r * (sim_constants.ab + r)**2)


def disk_force(r, coord, rho2, zbd):
    # return 0
    return (-sim_constants.m_disk * coord /
            (rho2 + (sim_constants.ad + zbd)**2)**1.5)


def halo_force(r, coord):
    # return 0
    if r < 10*sim_constants.rc:
        halo_scale = 0
    else:
        halo_scale = 1
    return (-halo_scale * sim_constants.m_halo * coord *
            ((logterm(r) / r**3) - (1.0 / rterm(r))))
