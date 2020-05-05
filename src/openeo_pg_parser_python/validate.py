import re
import os
import requests
import warnings
from json import load
from openeo_pg_parser_python.translate import translate_process_graph


def map_ids(dict_list):
    """
    Converts a list of dictionaries to a dictionary of dictionaries (i.e., a map), where the key is the ID ('id')
    given as a key in the dictionaries.

    Parameters
    ----------
    dict_list : list of dicts
        List of dictionaries containing the key 'id'.

    Returns
    -------
    dict
    """

    id_map = dict()
    for dict_i in dict_list:
        id_map[dict_i['id']] = dict_i

    return id_map

def load_json_files(dirpath):
    """
    Collects process definitions (JSON files) from a local process directory.

    Parameters
    ----------
    dirpath : str
        Directory path of the process files (.json) folder.

    Returns
    -------
    list
        List of processes decoded as dictionaries.
    """

    pattern = re.compile(".*.json$")
    filenames = [filename for filename in os.listdir(dirpath) if re.match(pattern, filename)]
    filepaths = [os.path.join(dirpath, filename) for filename in filenames]
    processes_list = []
    for filepath in filepaths:
        processes_list.append(load(open(filepath)))

    return processes_list

def load_processes(processes_src):
    """
    Collects process definitions (JSON files) from a local or remote directory.

    Parameters
    ----------
    processes_src : str or list
        It can be:
            - directory path to processes (.json)
            - URL of the remote process endpoint (e.g., "http://openeo.vgt.vito.be/openeo/0.4.0/processes")
            - list of loaded process definitions

    Returns
    -------
    list
        List of loaded process definitions.
    """

    if isinstance(processes_src, str) and os.path.isdir(processes_src):
        processes = load_json_files(processes_src)
    elif isinstance(processes_src, str):
        r = requests.get(url=processes_src)
        if r.status_code == 200:
            data = r.json()
            processes = data['processes']
        else:
            err_msg = "The specified URL is wrong."
            raise ValueError(err_msg)
    elif isinstance(processes_src, list):
        processes = processes_src
    else:
        err_msg = "Either a processes URL or a local directory path must be specified."
        raise ValueError(err_msg)

    return processes

def load_collections(collections_src):
    """
    Collects collection definitions (JSON files) from a local or remote directory.

    Parameters
    ----------
    collections_src : str or list
        It can be:
            - directory path to collections (.json)
            - URL of the remote process endpoint (e.g., "http://openeo.vgt.vito.be/openeo/0.4.0/collections")
            - list of loaded collection definitions

    Returns
    -------
    list
        List of loaded collection definitions.
    """

    if isinstance(collections_src, str) and os.path.isdir(collections_src):
        collections = load_json_files(collections_src)
    elif isinstance(collections_src, str):
        r = requests.get(url=collections_src)
        if r.status_code == 200:
            data = r.json()
            collections = data['collections']
        else:
            err_msg = "The specified URL is wrong."
            raise ValueError(err_msg)
    elif isinstance(collections_src, list):
        collections = collections_src
    else:
        err_msg = "Either a collection URL or a local directory path must be specified."
        raise ValueError(err_msg)

    return collections


def validate_processes(process_graph, processes_src):
    """
    Validate the input process graph according to the given list of processes.

    Parameters
    ----------
    process_graph : graph.Graph
        Traversable Python process graph.
    processes_src : str or list
        It can be:
            - directory path to processes (.json)
            - URL of the remote process endpoint (e.g., "http://openeo.vgt.vito.be/openeo/0.4.0/processes")
            - list of loaded process definitions

    Returns
    -------
    valid : bool
        If True, the given process graph is valid with respect to the given process definitions.
    """

    processes = load_processes(processes_src=processes_src)
    process_defs = map_ids(processes)

    valid = True
    for node in process_graph.nodes:
        if node.content['process_id'] not in process_defs.keys():
            valid = False
            wrn_msg = "'{}' is not in the current set of process definitions.".format(node.content['process_id'])
            warnings.warn(wrn_msg)
        else:
            process_def = process_defs[node.content['process_id']]
            # check all parameters
            # NB key 'parameters' is used in the processes' definition
            # NB key 'arguments' is used in the process graph
            for parameter_def in process_def['parameters']:
                if 'required' in parameter_def:
                    if parameter_def['name'] not in node.content['arguments'].keys():
                        valid = False
                        wrn_msg = "Parameter '{}' is required for process '{}'".format(parameter_def['name'],
                                                                                       node.content['process_id'])
                        warnings.warn(wrn_msg)

    return valid

def validate_collections(process_graph, collections_src):
    """
    Validate the input process graph according to the given list of processes.

    Parameters
    ----------
    process_graph : graph.Graph
        Traversable Python process graph.
    collections_src : str or list
        It can be:
            - directory path to collections (.json)
            - URL of the remote process endpoint (e.g., "http://openeo.vgt.vito.be/openeo/0.4.0/collections")
            - list of loaded collection definitions

    Returns
    -------
    valid : bool
        If True, the given process graph is valid with respect to the given process definitions.
    """

    collections  = load_collections(collections_src=collections_src)
    collections_map = map_ids(collections)

    valid = True
    for node in process_graph.nodes:
        if node.content['process_id'] == 'load_collection':
            if node.content['arguments']['id'] not in collections_map.keys():
                valid = False
                wrn_msg = "'{}' is not in the current set of collections.".format(node.content['arguments']['id'])
                warnings.warn(wrn_msg)
            else:
                collection = collections_map[node.content['arguments']['id']]
                # check bands
                if 'bands' in node.content['arguments'] and 'bands' in collection:
                    node_bands = [band.lower() for band in node.content['arguments']['bands']]
                    available_bands = [band_properties['name'].lower() for band_properties in collection['bands']
                                       if 'name' in band_properties]
                    for node_band in node_bands:
                        if node_band not in available_bands:
                            valid = False
                            available_bands_str = ', '.join(["'{}'".format(available_band)
                                                             for available_band in available_bands])
                            wrn_msg = "'{}' is not a valid band name for collection '{}' " \
                                      "with the following bands: {}.".format(node_band,
                                                                             collection['id'],
                                                                             available_bands_str)
                            warnings.warn(wrn_msg)

    return valid

def validate_process_graph(pg_filepath, processes_src, collections_src):
    """
    Validate the input process graph according to the given list of processes.

    Parameters
    ----------
    pg_filepath : str or dict
        Filepath to process graph (json file) or parsed file as a dictionary.
    processes_src : str or list
        It can be:
            - directory path to processes (.json)
            - URL of the remote process endpoint (e.g., "http://openeo.vgt.vito.be/openeo/0.4.0/processes")
            - list of loaded process definitions
    collections_src : str or list
        It can be:
            - directory path to collections (.json)
            - URL of the remote process endpoint (e.g., "http://openeo.vgt.vito.be/openeo/0.4.0/collections")
            - list of loaded collection definitions

    Returns
    -------
    valid : bool
        If True, the given process graph is valid with respect to the given process definitions.
    """

    process_graph = translate_process_graph(pg_filepath)

    processes_valid = validate_processes(process_graph, processes_src)
    collections_valid = validate_collections(process_graph, collections_src)

    process_graph_valid = processes_valid & collections_valid

    return process_graph_valid

if __name__ == '__main__':
    pass