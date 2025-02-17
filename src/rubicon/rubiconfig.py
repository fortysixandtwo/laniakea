# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import tomlkit

from laniakea import LocalConfig, get_config_file


class RubiConfig:
    '''
    Local configuration for Rubicon.
    '''

    log_storage_dir = None
    incoming_dir = None
    rejected_dir = None

    isotope_root_dir = None

    trusted_gpg_keyrings: list[str] = []

    def __init__(self, local_config=None):
        if not local_config:
            local_config = LocalConfig()
        self._lconf = local_config
        self._loaded = False

        # try to load default configuration
        self.load()

    def load_from_file(self, fname):
        cdata = {}
        if fname and os.path.isfile(fname):
            with open(fname) as json_file:
                cdata = tomlkit.load(json_file)

        self.log_storage_dir = cdata.get('LogStorage', os.path.join(self._lconf.workspace, 'job-logs'))
        if not self.log_storage_dir:
            raise Exception('No "LogStorage" entry in Rubicon configuration: We need to know where to store log files.')

        self.rejected_dir = cdata.get('RejectedDir', os.path.join(self._lconf.workspace, 'archive-rejected'))
        if not self.rejected_dir:
            raise Exception(
                'No "RejectedDir" entry in Rubicon configuration: We need to know where to place rejected files.'
            )
        self.incoming_dir = cdata.get('IncomingDir', os.path.join(self._lconf.workspace, 'archive-incoming'))

        self.trusted_gpg_keyrings = self._lconf.trusted_gpg_keyrings

        self.isotope_root_dir = cdata.get('IsotopeRootDir', None)

        self._loaded = True

    def load(self):
        fname = get_config_file('rubicon.toml')
        self.load_from_file(fname)

    @property
    def common_config(self) -> LocalConfig:
        return self._lconf
