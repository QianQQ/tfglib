# Created by Albert Aparicio on 21/10/16
# coding: utf-8

# This import makes Python use 'print' as in Python 3.x
from __future__ import print_function

import h5py
import numpy as np
from keras.utils.np_utils import to_categorical
from tfglib.construct_table import parse_file
from tfglib.utils import kronecker_delta
from tfglib.zero_pad import zero_pad_params


def find_longest_sequence(data_dir, speakers_list, basenames_list):
    """Find the number of speech frames from the longest sequence
    among all speakers

    # Arguments
        data_dir: directory of data to be used in the datatable.
                  This path must end in a '/'
        speakers_list: list of speakers to be used
        basenames_list: list of filenames to be used

    # Returns
        An integer with the number of frames of the longest sequence"""

    # Check that data_dir ends in a '/'
    try:
        assert data_dir[len(data_dir) - 1] == '/'
    except AssertionError:
        print("Please, make sure the data directory string ends with a '/'")

    longest_sequence = 0

    for speaker in speakers_list:
        for basename in basenames_list:
            params = parse_file(
                1,
                data_dir +
                'vocoded_s2s/' +
                speaker + '/' +
                basename +
                '.' + 'lf0' + '.dat'
            )

            if params.shape[0] > longest_sequence:
                longest_sequence = params.shape[0]

    return longest_sequence


def seq2seq_build_file_table(
        source_dir,
        src_index,
        target_dir,
        trg_index,
        basename,
        longest_seq
):
    """Build a datatable from the vocoded parameters of a sequence
    from a source-target pair of speakers

    # Arguments
        source_dir: directory path to the source files
        src_index: index (0-9) of the source speaker in the speakers list
        target_dir: directory path to the target files
        trg_index: index (0-9) of the target speaker in the speakers list
        basename: name without extension of the file's params to be prepared
        longest_seq: number of frames of the longest sequence in the database

        All directory paths must end in '/'

    # Returns
        - Zero-padded (by frames) source and target datatables
        - Source and target mask vectors indicating which frames are padded (0)
          and which of them are original from the data (1)

        The mask vectors are to be used in Keras' fit method"""

    # Check that source_dir and target_dir end in a '/'
    try:
        assert source_dir[-1] == '/'
    except AssertionError:
        print(
            "Please make sure the source data directory string ends with a '/'"
        )

    try:
        assert target_dir[-1] == '/'
    except AssertionError:
        print(
            "Please make sure the target data directory string ends with a '/'"
        )

    # Parse parameter files
    source_mcp = parse_file(40, source_dir + basename + '.' + 'mcp' + '.dat')

    source_f0 = parse_file(1, source_dir + basename + '.' + 'lf0' + '.dat')
    source_f0_i = parse_file(
        1,
        source_dir + basename + '.' + 'lf0' + '.i.dat'
    )  # Interpolated data

    source_vf = parse_file(1, source_dir + basename + '.' + 'vf' + '.dat')
    source_vf_i = parse_file(
        1,
        source_dir + basename + '.' + 'vf' + '.i.dat'
    )  # Use interpolated data

    target_mcp = parse_file(40, target_dir + basename + '.' + 'mcp' + '.dat')

    target_f0 = parse_file(1, target_dir + basename + '.' + 'lf0' + '.dat')
    target_f0_i = parse_file(
        1,
        target_dir + basename + '.' + 'lf0' + '.i.dat'
    )  # Use interpolated data

    target_vf = parse_file(1, target_dir + basename + '.' + 'vf' + '.dat')
    target_vf_i = parse_file(
        1,
        target_dir + basename + '.' + 'vf' + '.i.dat'
    )  # Use interpolated data

    # Build voiced/unvoiced flag arrays
    # The flags are:
    #   1 -> voiced
    #   0 -> unvoiced
    assert source_vf.shape == source_f0.shape
    source_voiced = np.empty(source_vf.shape)
    for index, vf in enumerate(source_vf):
        source_voiced[index] = 1 - kronecker_delta(source_vf[index])

    assert target_vf.shape == target_f0.shape
    target_voiced = np.empty(target_vf.shape)
    for index, vf in enumerate(target_vf):
        target_voiced[index] = 1 - kronecker_delta(target_vf[index])

    # Initialize End-Of-Sequence flag
    src_eos_flag = np.zeros(source_vf.shape)
    src_eos_flag[-1, :] = 1

    trg_eos_flag = np.zeros(target_vf.shape)
    trg_eos_flag[-1, :] = 1

    # Initialize one-hot-encoded speaker indexes
    src_spk_index = to_categorical(
        src_index * np.ones((source_vf.shape[0],), dtype=int),
        nb_classes=10
    )
    trg_spk_index = to_categorical(
        trg_index * np.ones((target_vf.shape[0],), dtype=int),
        nb_classes=10
    )

    # Initialize padding masks, to be passed into keras' fit
    # Source mask
    source_mask = np.concatenate((
        np.zeros((
            longest_seq - source_mcp.shape[0],
            1
        )),
        np.ones((
            source_mcp.shape[0],
            1
        ))
    ))

    # Target mask
    target_mask = np.concatenate((
        np.ones((
            target_mcp.shape[0],
            1
        )),
        np.zeros((
            longest_seq - target_mcp.shape[0],
            1
        ))
    ))

    assert source_mask.shape == target_mask.shape

    # Concatenate zero-padded source and target params
    source_params = np.concatenate((
        zero_pad_params(longest_seq, 'src', source_mcp),
        zero_pad_params(longest_seq, 'src', source_f0_i),
        zero_pad_params(longest_seq, 'src', source_vf_i),
        zero_pad_params(longest_seq, 'src', source_voiced),
        zero_pad_params(longest_seq, 'src', src_eos_flag),
        zero_pad_params(longest_seq, 'src', src_spk_index),
        zero_pad_params(longest_seq, 'src', trg_spk_index)
    ), axis=1)

    target_params = np.concatenate((
        zero_pad_params(longest_seq, 'trg', target_mcp),
        zero_pad_params(longest_seq, 'trg', target_f0_i),
        zero_pad_params(longest_seq, 'trg', target_vf_i),
        zero_pad_params(longest_seq, 'trg', target_voiced),
        zero_pad_params(longest_seq, 'trg', trg_eos_flag)
    ), axis=1)

    return source_params, source_mask, target_params, target_mask


def seq2seq_construct_datatable(data_dir, speakers_file, basenames_file):
    """Concatenate and zero-pad all vocoder parameters
    from all files in basenames_file, for all speakers in speakers_file

    # Arguments
        data_dir: directory of data to be used in the datatable.
        speakers_file: file with the list of speakers to be used
        basenames_file: file with the list of filenames to be used

        The data_dir path must end in a '/'

    # Returns
        - Concatenated and zero-padded (by frames) source and target datatables
        - Source and target mask matrices indicating which frames
          are padded (0) and which of them are original from the data (1)"""

    # Check that data_dir ends in a '/'
    try:
        assert data_dir[-1] == '/'
    except AssertionError:
        print("Please, make sure the data directory string ends with a '/'")

    # Parse speakers file
    speakers = open(data_dir + speakers_file, 'r').readlines()
    # Strip '\n' characters
    speakers = [line.split('\n')[0] for line in speakers]

    # Parse basenames file
    # This file should be equal for all speakers
    basenames = open(data_dir + basenames_file, 'r').readlines()
    # Strip '\n' characters
    basenames = [line.split('\n')[0] for line in basenames]

    # Find number of frames in longest sequence in the dataset
    longest_seq = find_longest_sequence(data_dir, speakers, basenames)

    # Initialize datatables
    src_datatable = []
    trg_datatable = []
    src_masks = []
    trg_masks = []

    # Initialize maximum and minimum values matrices
    spk_max = np.zeros((10, 42))
    spk_min = 1e+50 * np.ones((10, 42))

    # Nest iterate over speakers
    for src_index, src_spk in enumerate(speakers):
        for trg_index, trg_spk in enumerate(speakers):
            for basename in basenames:
                print(src_spk + '->' + trg_spk + ' ' + basename)

                (aux_src_params,
                 aux_src_mask,
                 aux_trg_params,
                 aux_trg_mask
                 ) = seq2seq_build_file_table(
                    data_dir + 'vocoded_s2s/' + src_spk + '/',
                    src_index,
                    data_dir + 'vocoded_s2s/' + trg_spk + '/',
                    trg_index,
                    basename,
                    longest_seq
                )

                # Obtain maximum and minimum values of each speaker's parameter
                # Mask parameters to avoid the zero-padded values
                masked_params = np.ma.array(
                    aux_src_params[:, 0:42],
                    mask=1 - np.repeat(aux_src_mask, 42, axis=1)
                )
                # Compute maximum and minimum values
                spk_max[src_index, :] = np.maximum(
                    spk_max[src_index, :], np.ma.max(masked_params, axis=0)
                )
                spk_min[src_index, :] = np.minimum(
                    spk_min[src_index, :], np.ma.min(masked_params, axis=0)
                )

                # Append sequence params and masks to main datatables and masks
                src_datatable.append(aux_src_params)
                trg_datatable.append(aux_trg_params)
                src_masks.append(aux_src_mask)
                trg_masks.append(aux_trg_mask)

    return (np.array(src_datatable),
            np.array(src_masks).reshape(-1, longest_seq),  # Reshape to 2D mask
            np.array(trg_datatable),
            np.array(trg_masks).reshape(-1, longest_seq),  # Reshape to 2D mask
            longest_seq,
            spk_max,
            spk_min)


def seq2seq_save_datatable(data_dir, datatable_out_file):
    """Generate datatables and masks and save them to .h5 file

    # Arguments
        data_dir: directory of data to be used for the datatable.
        datatable_out_file: path to the output .h5 file (no extension)

    # Returns
        An h5py file with source and target datatables and matrices.

        It also returns the data returned by seq2seq_construct_datatable:
        - Concatenated and zero-padded (by frames) source and target datatables
        - Source and target mask matrices indicating which frames
          are padded (0) and which of them are original from the data (1)"""

    # Check that the data_dir ends in a '/'
    try:
        assert data_dir[-1] == '/'
    except AssertionError:
        print("Please, make sure the data directory string ends with a '/'")

    try:
        assert type(datatable_out_file) == str
    except AssertionError:
        print("Please, make sure the data output filename is a string")

    # Construct datatables and masks
    (source_datatable,
     source_masks,
     target_datatable,
     target_masks,
     max_seq_length,
     speakers_max,
     speakers_min
     ) = seq2seq_construct_datatable(
        data_dir,
        'speakers.list',
        'seq2seq_basenames.list'
    )

    # Save dataset names and dataset arrays for elegant iteration when saving
    data_dict = {
        'src_datatable': source_datatable,
        'trg_datatable': target_datatable,
        'src_mask': source_masks,
        'trg_mask': target_masks
    }

    # Save data to .h5 file
    with h5py.File(datatable_out_file + '.h5', 'w') as f:
        # Save max_seq_length as an attribute
        f.attrs.create('max_seq_length', max_seq_length, dtype=int)
        f.attrs.create('speakers_max', speakers_max)
        f.attrs.create('speakers_min', speakers_min)

        # Save the rest of datasets
        for dataset_name, dataset in data_dict.items():
            f.create_dataset(
                dataset_name,
                data=dataset,
                compression="gzip",
                compression_opts=9
            )

        f.close()

    return (source_datatable,
            source_masks,
            target_datatable,
            target_masks,
            max_seq_length,
            speakers_max,
            speakers_min)


def seq2seq2_load_datatable(datatable_file):
    """Load datasets and masks from an h5py file

    # Arguments
        datatable_file: path to the .h5 file that contains the data

    # Returns
        The same data returned by seq2seq_construct_datatable:

        - Concatenated and zero-padded (by frames) source and target datatables
        - Source and target mask matrices indicating which frames
          are padded (0) and which of them are original from the data (1)"""

    # Load data from .h5 file
    with h5py.File(datatable_file, 'r') as file:
        # Load datasets
        source_datatable = file['src_datatable'][:, :]
        target_datatable = file['trg_datatable'][:, :]

        source_masks = file['src_mask'][:, :]
        target_masks = file['trg_mask'][:, :]

        # Load max_seq_length attribute
        max_seq_length = file.attrs.get('max_seq_length')
        speakers_max = file.attrs.get('speakers_max')
        speakers_min = file.attrs.get('speakers_min')

        file.close()

    return (source_datatable,
            source_masks,
            target_datatable,
            target_masks,
            max_seq_length,
            speakers_max,
            speakers_min)
