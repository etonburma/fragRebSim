# Standard python modules
import random as rnd
from math import cos, sin, sqrt
# import sys

# These modules need to be pip installed.
import numpy as np
import rebound
from astropy import units as u
# For Jupyter/IPython notebook
from tqdm import tnrange, tqdm

# From fragRebSim
from .dMdEdist import dMdEdist
from .forces import sim_constants as sc
from .forces import bulge_force, cluster_force, disk_force, halo_force
from .funcs import beta_dist, mstar_dist, r_tidal, rstar_func


class RebSimIntegrator:

    def __init__(self, Nstars, Nfrag):
        self.Nstars = Nstars
        self.Nfrag = Nfrag
        self.Nout = 10000
        self.max_time = 1.0e6 * 2.0 * np.pi
        self.posx = [[[] for y in range(Nfrag)] for x in range(Nstars)]
        self.posy = [[[] for y in range(Nfrag)] for x in range(Nstars)]
        self.posz = [[[] for y in range(Nfrag)] for x in range(Nstars)]
        self.dmde = dMdEdist()
        self.forces = []
        self.star_masses = []
        self.star_radii = []
        self.tidal_radii = []
        self.orbital_vels = []

        # Star-fragment indices list, necessary to keep track of which
        # particles in the simulation belong to which star.
        self.sfindices = [0]

    def set_Nstars(self, new_Nstars):
        self.Nstars = new_Nstars

    def set_Nfrag(self, new_Nfrag):
        self.Nfrag = new_Nfrag

    def set_Nout(self, new_Nout):
        self.Nout = new_Nout

    # Galaxy potential,
    # from http://adsabs.harvard.edu/abs/2014ApJ...793..122K
    # Note: There is a typo in that paper where "a_d" is said to be
    # 2750 kpc, it should be 2.75 kpc.
    def migrationAccel(self, reb_sim):
        ps = reb_sim.contents.particles

        # Apply forces to every fragment
        for p in ps[1:]:
            x2 = p.x**2
            y2 = p.y**2
            z2 = p.z**2
            r = sqrt(x2 + y2 + z2)
            rho2 = x2 + y2
            zbd = sqrt(z2 + sc.bd**2)

            p.ax += cluster_force(r, p.x) + bulge_force(r, p.x) +\
                disk_force(r, p.x, rho2, zbd) + halo_force(r, p.x)
            p.ay += cluster_force(r, p.y) + bulge_force(r, p.y) +\
                disk_force(r, p.y, rho2, zbd) + halo_force(r, p.y)
            p.az += cluster_force(r, p.z) + bulge_force(r, p.z) +\
                disk_force(r, p.z, rho2, zbd) + halo_force(r, p.z)

    # Star disruption function
    def star_disrupt(self, reb_sim, time):
        m_hole = sc.m_hole

        # Randomly drawn mass of star
        xstar = rnd.random()
        m_star = mstar_dist(xstar)
        self.star_masses.append(m_star)

        # Determined radius of star from stellar mass
        r_star = rstar_func(m_star) * sc.RsuntoAU
        self.star_radii.append(r_star)

        # Distance spread for fragments
        rads = [r_star * float(f) / float(self.Nfrag + 1)
                for f in range(self.Nfrag + 1)]
        rads.pop(0)

        # Determined tidal radius of star
        r_t = r_tidal(m_star, r_star)
        self.tidal_radii.append(r_t)

        self.orbital_vels.append(2.0 * m_hole / r_t)

        # Set position of star; random sphere point picking
        u1 = rnd.uniform(-1.0, 1.0)
        th1 = rnd.uniform(0., 2. * np.pi)
        star_direc = np.array([sqrt(1.0 - (u1)**2) * cos(th1),
                               sqrt(1.0 - (u1)**2) * sin(th1),
                               u1])
        star_vec = [r_t * d for d in star_direc]

        # Binding energy spread, with beta value randomly drawn from
        # beta distribution
        xbeta = rnd.random()
        beta = beta_dist(xbeta)
        NRGs = self.dmde.energy_spread(beta, self.Nfrag)

        # Converted NRGs list from cgs to proper units
        natural_u = (u.AU / (u.yr / (2.0 * np.pi)))**2
        nrg_scale = ((r_star * sc.AUtoRsun)**(-1.0) * (m_star)**(2.0 / 3.0)
                     * (m_hole / 1.0e6)**(1.0 / 3.0))
        energies = [(nrg_scale * nrg *
                     (u.cm / u.second)**2).to(natural_u).value
                    for nrg in NRGs]

        # Calculating velocities
        vels = [sqrt((2.0 * g) + (2.0 * m_hole / r_t)) for g in energies]

        # Randomly draw velocity vector direction
        phi2 = rnd.uniform(0., 2. * np.pi)

        x = star_vec[0]
        y = star_vec[1]
        z = star_vec[2]
        r = np.linalg.norm(star_vec)

        randomvelvec = [
            (x * (r - z + z * cos(phi2)) - r * y * sin(phi2)) /
            (r**2 * sqrt(2.0 - 2.0 * z / r)),
            (y * (r - z + z * cos(phi2)) + r * x * sin(phi2)) /
            (r**2 * sqrt(2.0 - 2.0 * z / r)),
            ((r - z) * z - (x**2 + y**2) * cos(phi2)) /
            (r**2 * sqrt(2.0 - 2.0 * z / r))
        ]

        velocity_vec = np.cross(star_vec, randomvelvec)
        n = np.linalg.norm(velocity_vec)
        vel_direc = [v / n for v in velocity_vec]

        for frag in tnrange(self.Nfrag, desc='Fragment', leave=False):

            # Velocity vector of fragment
            vel = vels[frag]
            frag_velvec = [vel * v for v in vel_direc]

            # Position vector of Fragment
            rad = rads[frag]
            frag_posvec = [(r_t + rad) * p for p in star_direc]

            # Add particle to rebound simulation
            reb_sim.add(m=0.0, x=frag_posvec[0], y=frag_posvec[1],
                        z=frag_posvec[2], vx=frag_velvec[0],
                        vy=frag_velvec[1], vz=frag_velvec[2])

        self.sfindices.append(reb_sim.N - 1)
        print('Star disrupted, t= {0}'.format(time))
        print('Number of particles: {0}'.format(reb_sim.N))
        print(self.sfindices)
        # sys.exit()

    # Removing fragment from posx, posy, and posz arrays given its index
    # in the array of reb_sim particles
    def remove_fragment_record(self, particle_index):
        pi = particle_index
        i = next(ind for ind, v in enumerate(self.sfindices)
                 if v > pi or v == pi)
        start = self.sfindices[i-1] + 1
        new_pi = pi - start
        star = i-1
        self.posx[star].pop(new_pi)
        self.posy[star].pop(new_pi)
        self.posz[star].pop(new_pi)
        for j, index in enumerate(self.sfindices[i:]):
            self.sfindices[j+i] -= 1

    # Record the position of each fragment
    def record_fragment_positions(self, reb_sim):
        for pi, p in enumerate(reb_sim.particles):
            if pi == 0:
                continue
            i = next(ind for ind, v in enumerate(self.sfindices)
                     if v > pi or v == pi)
            frag = pi - self.sfindices[i-1] - 1
            star = i - 1
            self.posx[star][frag].append(p.x / sc.scale)
            self.posy[star][frag].append(p.y / sc.scale)
            self.posz[star][frag].append(p.z / sc.scale)

    # Integrating simulation
    def sim_integrate(self):
        # Set up rebound simulation
        reb_sim = rebound.Simulation()
        reb_sim.integrator = "ias15"
        reb_sim.add(m=sc.m_hole)
        reb_sim.dt = 1.0e-15

        reb_sim.N_active = 1
        reb_sim.additional_forces = self.migrationAccel
        reb_sim.force_is_velocity_dependent = 1
        reb_sim.exit_max_distance = 15.0 * sc.scale  # 15 pc in AU

        stop = np.log10(self.max_time)
        times = np.logspace(-17.0, stop, self.Nout - 1)
        times = np.insert(times, 0.0, 0)
        epsilon = 0.1 * (1.0e4 * 2 * np.pi)
        bound_vel = ((500 * u.km / u.second).
                     to(u.AU/(u.yr / (2.0 * np.pi))).value)

        # Disrupt first star
        self.star_disrupt(reb_sim, reb_sim.t)
        star_count = 1

        # Begin integration
        for ti, time in enumerate(tqdm(times)):
            try:
                reb_sim.integrate(time, exact_finish_time=1)

                # Add new disruption every 10,000 years
                if (time % (1.0e4 * 2 * np.pi) < epsilon and
                        time > (1.0e4 * 2 * np.pi) and
                        star_count != self.Nstars):
                    self.star_disrupt(reb_sim, reb_sim.t)
                    star_count += 1

                # Bound velocity criterion:
                # Cuts particles closely bound to black hole
                for index in range(reb_sim.N):
                    if index == 0:
                        continue
                    try:
                        p = reb_sim.particles[index]
                        star = next(ind for ind, v in enumerate(self.sfindices)
                                    if v > index or v == index) - 1
                        velinf2 = np.absolute(p.vx**2 + p.vy**2 + p.vz**2 -
                                              self.orbital_vels[star])
                        velinf = sqrt(velinf2)
                        if velinf < bound_vel:
                            reb_sim.remove(index)
                            self.remove_fragment_record(index)
                            print('Bound particle removed.')
                            raise StopIteration
                    except StopIteration:
                        # print('Particle index: {0}'.format(index))
                        # print('Number of particles: {0}'.format(reb_sim.N))
                        # print(self.sfindices)
                        # reb_sim.status()
                        # sys.exit()
                        break

            except rebound.Escape:  # Removes escaped particles
                print('A particle has escaped.')
                for j in range(reb_sim.N):
                    try:
                        p = reb_sim.particles[j]
                        d2 = p.x * p.x + p.y * p.y + p.z * p.z
                        if d2 > reb_sim.exit_max_distance**2:
                            reb_sim.remove(j)
                            self.remove_fragment_record(j)
                            raise StopIteration
                    except StopIteration:
                        break

            # Recording positions of fragments
            self.record_fragment_positions(reb_sim)
