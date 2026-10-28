"""
NUMA topology discovery and CPU affinity helpers.
"""


import logging
import os
import typing
from pathlib import Path


NODE_ROOT = Path('/sys/devices/system/node')


def parse_cpulist(cpulist):
    """
    Parses a Linux cpulist string (e.g. "0-3,8,10-11") into a list of CPU ids.

    Parameters
    ----------
    cpulist : str
        Contents of a sysfs ``cpulist`` file.

    Returns
    -------
    list of int
        CPU identifiers contained in the list.
    """
    cpus = []
    for part in cpulist.strip().split(','):
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-')
            cpus.extend(range(int(start), int(end) + 1))
        else:
            cpus.append(int(part))
    return cpus


def numa_nodes():
    """
    Discovers NUMA nodes that have CPUs assigned to them.

    Reads ``/sys/devices/system/node/node*/cpulist`` and returns a mapping of
    NUMA node id to the list of CPU ids belonging to that node. Nodes without
    CPUs (memory-only nodes) are skipped. Returns an empty dictionary on hosts
    where the sysfs NUMA hierarchy is not exposed (non-NUMA kernels,
    restricted containers).

    Note that NUMA node ids are not necessarily contiguous: ppc64le hosts
    commonly expose ids such as 0 and 8.

    Returns
    -------
    dict of int to list of int
        Mapping of NUMA node id to its CPU ids, ordered by numeric node id.
    """
    if not NODE_ROOT.exists():
        return {}
    nodes = {}
    paths = sorted(
        NODE_ROOT.glob('node[0-9]*'),
        key=lambda p: int(p.name[4:]),
    )
    for path in paths:
        try:
            cpulist = (path / 'cpulist').read_text()
        except OSError:
            continue
        cpus = parse_cpulist(cpulist)
        if cpus:
            nodes[int(path.name[4:])] = cpus
    return nodes


def apply_cpu_affinity(cpus):
    """
    Pins the calling thread to the given set of CPUs.

    The affinity mask is inherited by child processes, so subprocesses spawned
    by the calling thread (e.g. ``mock``) are confined to the same CPUs. The
    requested set is intersected with the thread's current affinity mask in
    order to respect cgroup or taskset restrictions imposed by the operating
    environment.

    Parameters
    ----------
    cpus : list of int
        CPU identifiers to pin the calling thread to. A falsy value is
        treated as a no-op.

    Returns
    -------
    set of int or None
        The CPU set that was actually applied, or ``None`` if no affinity was
        set (input was empty or no CPUs remained after intersecting with the
        current mask).
    """
    if not cpus:
        return None
    allowed = os.sched_getaffinity(0)
    effective = set(cpus) & allowed
    if not effective:
        logging.warning(
            'NUMA CPU set %s has no overlap with current affinity %s, '
            'skipping pinning',
            sorted(cpus),
            sorted(allowed),
        )
        return None
    os.sched_setaffinity(0, effective)
    return effective
