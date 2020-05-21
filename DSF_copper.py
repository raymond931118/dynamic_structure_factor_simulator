import os
import sys
import numpy as np
import pandas as pd
from collections import defaultdict
from phonopy import load
from phonopy.phonon.degeneracy import degenerate_sets
from phonopy.units import THzToEv

def generate_qpoints(n_sample, r_max, r_bin_width, prim_latt):
    rand_array = np.random.rand(3, n_sample)
    sphere_coords = np.zeros((3, n_sample))
    sphere_coords[0] = r_max * np.cbrt(rand_array[0]) # r
    sphere_coords[1] = 2 * np.pi * rand_array[1]  # theta
    sphere_coords[2] = np.arccos(2*rand_array[2]-1) # phi

    cartesian_coords = np.zeros((3, n_sample))
    cartesian_coords[0] = sphere_coords[0] * np.sin(sphere_coords[2]) * np.cos(sphere_coords[1]) # x
    cartesian_coords[1] = sphere_coords[0] * np.sin(sphere_coords[2]) * np.sin(sphere_coords[1]) # y
    cartesian_coords[2] = sphere_coords[0] * np.cos(sphere_coords[2]) # z

    recip_coords = np.zeros((4, n_sample))
    recip_coords[0] = sphere_coords[0] # keep r value
    recip_coords[1:] = np.dot(prim_latt, cartesian_coords) / (2*np.pi) # primitive reciprocal

    shells = defaultdict(list)
    for ipoint in recip_coords.T:
        ishell = int(ipoint[0]/r_bin_width)
        shells[ishell].append(ipoint[1:])
    return shells


# call DSF simulation function from Phonopy
def run(phonon, Q_prim, temperature, scattering_lengths):
    phonon.run_dynamic_structure_factor(
        Q_prim,
        temperature,
        atomic_form_factor_func=None,
        scattering_lengths=scattering_lengths,
        freq_min=1e-3)
    dsf = phonon.dynamic_structure_factor
    return dsf.frequencies, dsf.dynamic_structure_factors


def compute_dsf(phonon, n_sample, r_max, r_bin_width, f_max, f_bin_width, 
                temperature, scattering_lengths, out_file):
    prim_latt = phonon.primitive.get_cell()

    # generate uniform k-point mesh within sphere of r_max radius
    # convert to primitive reciprocal basis and assign to shells
    shells = generate_qpoints(n_sample, r_max, r_bin_width, prim_latt)

    # mesh sampling phonon calculation is needed for Debye-Waller factor
    # this must be done with is_mesh_symmetry=False and with_eigenvectors=True
    mesh = [11, 11, 11]
    phonon.run_mesh(mesh,
                    is_mesh_symmetry=False,
                    with_eigenvectors=True)

    n_freq = int(f_max/f_bin_width) + 1 # number of frequency bins
    # loop over shells
    # doing reversely to early detect potential memory issues for outer shells
    for ishell in reversed(range(int(r_max/r_bin_width))):
        shell_data = [ishell] + [0] * n_freq # initialize data
        # skip empty shells
        if len(shells[ishell]) == 0:
            out = pd.DataFrame([shell_data])
            out.to_csv(out_file, index=None, header=None, mode='a')
            continue
        
        print("Working on shell ID: {}, number of points: {}"
                 .format(ishell, len(shells[ishell])), flush=True)
        
        # for INS, scattering length has to be given.
        # the following values is obtained at (Coh b)
        # https://www.nist.gov/ncnr/neutron-scattering-lengths-list

        results = run(phonon, shells[ishell], temperature, scattering_lengths)
        
        for ipoint in range(len(results[0])):
            frequencies = results[0][ipoint]
            dsfs = results[1][ipoint]
            for j in range(len(frequencies)):
                freq = frequencies[j]
                if freq >= f_max: continue
                jbin = int(freq/f_bin_width)
                shell_data[jbin+1] += dsfs[j]
        
        # append to output
        out = pd.DataFrame([shell_data])
        out.to_csv(out_file, index=None, header=None, mode='a')
    

if __name__ == '__main__':
    # output file
    rand_ID = int(np.random.rand() * 10**8)
    out_file = "ID-"+str(rand_ID)+".csv"

    # read phonon data, requires FORCE_SETS in directory
    phonon = load(supercell_filename="SPOSCAR")

    # set parameters
    n_sample = 1000 # number of uniform sampling k-points in sphere
    r_max = 10 # maximum |Q|
    r_bin_width = 0.02 # |Q| sampling bin width, n_shell = r_max / dr
    f_max = 10 # maximum frequency in THz
    f_bin_width = 0.02 # resolution of frequency
    temperature = 5 # for Debye-Waller factor
    scattering_lengths = {'Ga': 7.288, 'Nb': 7.054, 'Se': 7.97}
    print("number of sampling points:", n_sample, flush=True)
    print("number of shells:", int(r_max/r_bin_width), flush=True)
    print("number of frequency bins:", int(f_max/f_bin_width), flush=True)

    # compute DSF and save to file    
    if True:
    #if False:
        compute_dsf(phonon, n_sample, r_max, r_bin_width, f_max, f_bin_width, \
                      temperature, scattering_lengths, out_file)
    
    print("Program finished normally")