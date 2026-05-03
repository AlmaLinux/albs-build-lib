"""
Build System build thread implementation.
"""


import logging
import os
import threading

from albs_common_lib.utils.file_utils import clean_dir

from albs_build_lib.builder.numa import apply_cpu_affinity


class BaseSlaveBuilder(threading.Thread):
    """Build thread."""

    def __init__(
        self,
        thread_num,
        numa_cpus=None,
    ):
        """
        Build thread initialization.

        Parameters
        ----------
        config : build_node.build_node_config.BuildNodeConfig
            Build node configuration object.
        thread_num : int
            Number of a build thread to construct a "unique" name.
        terminated_event : threading.Event
            Shows, if process got "kill -15" signal.
        graceful_terminated_event : threading.Event
            Shows, if process got "kill -10" signal.
        numa_cpus : list of int, optional
            CPU identifiers the thread should be pinned to. When provided,
            ``apply_numa_affinity`` confines the thread (and the processes it
            spawns) to these CPUs so that a build stays on a single NUMA node.
        """
        super().__init__(name='Builder-{0}'.format(thread_num))
        self._numa_cpus = numa_cpus

    def apply_numa_affinity(self):
        """
        Pins the running thread to the configured NUMA CPU set.

        Must be called from inside ``run()`` so that the affinity is applied
        to the build thread itself rather than the thread that constructed
        the builder. Subprocesses spawned afterwards inherit the mask.
        """
        if not self._numa_cpus:
            return
        applied = apply_cpu_affinity(self._numa_cpus)
        if applied:
            logging.info(
                '%s pinned to CPUs %s',
                self.name,
                sorted(applied),
            )

    @staticmethod
    def init_working_dir(working_dir):
        """
        Creates a non-existent working directory or cleans it up from previous
        builds.
        """
        if os.path.exists(working_dir):
            logging.debug('cleaning the %s working directory', working_dir)
            clean_dir(working_dir)
        else:
            logging.debug('creating the %s working directory', working_dir)
            os.makedirs(working_dir, 0o750)

    @staticmethod
    def init_thread_logger(log_file):
        """
        Build thread logger initialization.

        Parameters
        ----------
        log_file : str
            Log file path.

        Returns
        -------
        logging.Logger
            Build thread logger.
        """
        logger = logging.getLogger(
            'bt-{0}-logger'.format(threading.current_thread().name)
        )
        logger.handlers = []
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s: " "%(message)s", "%H:%M:%S %d.%m.%y"
        )
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
