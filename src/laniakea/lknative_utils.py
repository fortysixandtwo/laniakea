# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

from lknative import BaseConfig
from laniakea.db import config_get_project_name, config_get_distro_tag, session_factory, \
    ArchiveSuite
from laniakea import LocalConfig


def create_native_baseconfig():
    session = session_factory()
    bconf = BaseConfig()

    bconf.projectName = config_get_project_name()
    bconf.archive.distroTag = config_get_distro_tag()

    dev_suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.devel_target==True).one()

    bconf.archive.develSuite = dev_suite.name

    lconf = LocalConfig()
    bconf.cacheDir = lconf.cache_dir
    bconf.workspace = lconf.workspace
    bconf.archive.rootPath = lconf.archive_root_dir

    return bconf
