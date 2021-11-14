# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
import enum
import uuid
from sqlalchemy import Column, Table, Index, Text, String, Integer, SmallInteger, DateTime, Enum, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import ARRAY, CHAR, JSON, JSONB, TEXT
from sqlalchemy.sql import func, cast
from sqlalchemy.ext.mutable import MutableDict
from datetime import datetime
from .base import Base, UUID, DebVersion, create_tsvector


UUID_NS_SRCPACKAGE = uuid.UUID('bdc4cc28-43ed-58f7-8cf8-7bd1b4e80560')
UUID_NS_BINPACKAGE = uuid.UUID('b897829c-2eb4-503c-afd1-0fd74da8cc2b')
UUID_NS_SWCOMPONENT = uuid.UUID('94c8e196-e236-48fe-81c8-38dd47de4650')


repo_suite_assoc_table = Table('archive_repo_suite_association', Base.metadata,
                               Column('repo_id', Integer, ForeignKey('archive_repositories.id', ondelete='cascade')),
                               Column('suite_id', Integer, ForeignKey('archive_suites.id', ondelete='cascade'))
                               )


class ArchiveConfig(Base):
    '''
    General archive configuration that applies to all repositories and suites.
    '''
    __tablename__ = 'archive_config'

    id = Column(Integer, primary_key=True)

    primary_repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    primary_repo = relationship('ArchiveRepository')
    auto_debug_management = Column(Boolean(), default=True)  # If True, Laniakea will automatically create, delete and assign debug suites

    primary_repo_root = Column(Text(), nullable=False, default='/')  # Location (directory) of the primary/master repository
    extra_repo_root = Column(Text(), nullable=False, default='/multiverse')  # Location of the additional repositories

    archive_url = Column(Text(), nullable=False)  # Web URL of the primary archive mirror

    def __init__(self, name):
        self.name = name


class ArchiveRepository(Base):
    '''
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    '''
    __tablename__ = 'archive_repositories'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository
    origin_name = Column(String(200))  # Name of the origin of this repository (e.g. "Purism")

    suites = relationship('ArchiveSuite',
                          secondary=repo_suite_assoc_table,
                          back_populates='repos')
    suite_settings = relationship('ArchiveRepoSuiteSettings',
                                  back_populates='repo')

    def __init__(self, name):
        self.name = name


suite_component_assoc_table = Table('archive_suite_component_association', Base.metadata,
                                    Column('suite_id', Integer,
                                           ForeignKey('archive_suites.id', ondelete='cascade'),
                                           primary_key=True),
                                    Column('component_id', Integer,
                                           ForeignKey('archive_components.id', ondelete='cascade'),
                                           primary_key=True)
                                    )

suite_arch_assoc_table = Table('archive_suite_architecture_association', Base.metadata,
                               Column('suite_id', Integer,
                                      ForeignKey('archive_suites.id', ondelete='cascade'),
                                      primary_key=True),
                               Column('arch_id', Integer,
                                      ForeignKey('archive_architectures.id', ondelete='cascade'),
                                      primary_key=True)
                               )

suite_parents_assoc_table = Table('archive_suite_parents_association', Base.metadata,
                                  Column('suite_id', Integer,
                                         ForeignKey('archive_suites.id', ondelete='cascade'),
                                         primary_key=True),
                                  Column('parent_suite_id', Integer,
                                         ForeignKey('archive_suites.id', ondelete='cascade'),
                                         primary_key=True)
                                  )

srcpkg_suite_assoc_table = Table('archive_srcpkg_suite_association', Base.metadata,
                                 Column('src_package_uuid', UUID(as_uuid=True),
                                        ForeignKey('archive_pkgs_source.uuid', ondelete='cascade'),
                                        primary_key=True),
                                 Column('suite_id', Integer,
                                        ForeignKey('archive_suites.id', ondelete='cascade'),
                                        primary_key=True)
                                 )

binpkg_suite_assoc_table = Table('archive_binpkg_suite_association', Base.metadata,
                                 Column('bin_package_uuid', UUID(as_uuid=True),
                                        ForeignKey('archive_pkgs_binary.uuid', ondelete='cascade'),
                                        primary_key=True),
                                 Column('suite_id', Integer,
                                        ForeignKey('archive_suites.id', ondelete='cascade'),
                                        primary_key=True)
                                 )

swcpt_binpkg_assoc_table = Table('archive_swcpt_binpkg_association', Base.metadata,
                                 Column('sw_cpt_uuid', UUID(as_uuid=True),
                                        ForeignKey('archive_sw_components.uuid', ondelete='cascade'),
                                        primary_key=True),
                                 Column('bin_package_uuid', UUID(as_uuid=True),
                                        ForeignKey('archive_pkgs_binary.uuid', ondelete='cascade'),
                                        primary_key=True)
                                 )


class ArchiveSuite(Base):
    '''
    Information about suite in a distribution repository.
    '''
    __tablename__ = 'archive_suites'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the suite, usually the codename e.g. "sid"
    alias = Column(String(128), unique=True, nullable=True)  # Alternative name of the suite, e.g. "unstable"
    summary = Column(String(200), nullable=True)  # Short description string for this suite
    version = Column(String(64), nullable=True)  # Version string applicable for this suite
    is_debug = Column(Boolean(), default=False)  # True in case this suite contains debug symbol packages

    repos = relationship('ArchiveRepository', secondary=repo_suite_assoc_table, back_populates='suites')
    architectures = relationship('ArchiveArchitecture', secondary=suite_arch_assoc_table, back_populates='suites')
    components = relationship('ArchiveComponent', secondary=suite_component_assoc_table, back_populates='suites')

    debug_suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    debug_suite = relationship('ArchiveSuite', back_populates='debug_suite_for')
    debug_suite_for = relationship('ArchiveSuite',
                                   back_populates='debug_suite',
                                   remote_side=[id],
                                   uselist=True)

    repo_settings = relationship('ArchiveRepoSuiteSettings',
                                  back_populates='suite')

    parents = relationship('ArchiveSuite',
                           secondary=suite_parents_assoc_table,
                           foreign_keys=[suite_parents_assoc_table.c.parent_suite_id],
                           back_populates='overlays')
    overlays = relationship('ArchiveSuite',
                            secondary=suite_parents_assoc_table,
                            foreign_keys=[suite_parents_assoc_table.c.suite_id],
                            back_populates='parents')

    pkgs_source = relationship('SourcePackage',
                               secondary=srcpkg_suite_assoc_table,
                               back_populates='suites')
    pkgs_binary = relationship('BinaryPackage',
                               secondary=binpkg_suite_assoc_table,
                               back_populates='suites')

    _primary_arch = None

    def __init__(self, name):
        self.name = name

    @property
    def primary_architecture(self):
        if self._primary_arch:
            return self._primary_arch
        if len(self.architectures) == 0:
            return None
        self._primary_arch = self.architectures[0]
        for arch in self.architectures:
            if arch.name != 'all':
                self._primary_arch = arch
                break
        return self._primary_arch


class ArchiveRepoSuiteSettings(Base):
    '''
    Settings that are specific to a suite in a particular repository, but
    will not apply to the suite globally.
    '''
    __tablename__ = 'archive_repo_suite_settings'
    __table_args__ = (UniqueConstraint('repo_id', 'suite_id', name='_repo_suite_uc'),)

    id = Column(Integer, primary_key=True)

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository', back_populates='suite_settings')

    suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    suite = relationship('ArchiveSuite', back_populates='repo_settings')

    suite_summary = Column(String(200), nullable=True)  # Override the default suite summary text for the particular repository
    accept_uploads = Column(Boolean(), default=True)  # Whether new packages can arrive in this suite via regular uploads ("unstable", "staging", ...)
    devel_target = Column(Boolean(), default=False)  # Whether this is a development target suite ("testing", "green", ...)
    frozen = Column(Boolean(), default=False)  # Whether the suite is frozen and immutable for changes
    auto_overrides = Column(Boolean(), default=False)  # Automatically process overrides, no package will land in NEW
    manual_accept = Column(Boolean(), default=False)  # Every package will end up in the NEW queue for manual review, no automatic ACCEPT will happen

    not_automatic = Column(Boolean(), default=False)  # If set, packages from this source will not be installed automatically
    but_automatic_upgrades = Column(Boolean(), default=False)  # Packages will not be auto-installed, but auto-upgraded if already installed

    valid_time = Column(Integer, default=604800)  # time in seconds how long the suite index should be considered valid
    phased_update_delay = Column(Integer, default=0)  # delay before a package is available to 100% of all users (0 to disable phased updates)
    signingkeys = Column(ARRAY(String(64)))  # List of architectures this source package can be built for
    announce_emails = Column(ARRAY(Text()))  # E-Mail addresses that changes to this repository should be announced at

    def __init__(self, repo: ArchiveRepository, suite: ArchiveSuite):
        self.repo_id = repo.id
        self.suite_id = suite.id


class ArchiveComponent(Base):
    '''
    Information about an archive component within a suite.
    '''
    __tablename__ = 'archive_components'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the repository
    summary = Column(String(200), nullable=True)  # Short explanation of this component's purpose

    suites = relationship('ArchiveSuite', secondary=suite_component_assoc_table, back_populates='components')

    parent_component_id = Column(Integer, ForeignKey('archive_components.id'))
    parent_component = relationship('ArchiveComponent', remote_side=[id])  # Other components that need to be present to fulfill dependencies of packages in this component

    def __init__(self, name):
        self.name = name

    def is_primary(self):
        return self.name == 'main'

    def is_nonfree(self):
        return self.name == 'non-free'


class ArchiveArchitecture(Base):
    '''
    A system architecture software can be compiled for.
    Usually associated with an :ArchiveSuite
    '''
    __tablename__ = 'archive_architectures'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the architecture
    summary = Column(String(200))  # Short description of this architecture

    suites = relationship('ArchiveSuite',
                          secondary=suite_arch_assoc_table,
                          back_populates='architectures')  # Suites that contain this architecture

    pkgs_binary = relationship('BinaryPackage',
                               back_populates='architecture')

    def __init__(self, name):
        self.name = name


class ArchiveSection(Base):
    '''
    Known sections in the archive that packages are sorted into.
    See https://www.debian.org/doc/debian-policy/ch-archive.html#s-subsections for reference.
    '''
    __tablename__ = 'archive_sections'

    id = Column(Integer, primary_key=True)

    name = Column(String(128), unique=True)  # Name of the section
    summary = Column(String(200), nullable=True)  # Short description of this section

    def __init__(self, name: str, summary: str = None):
        self.name = name
        self.summary = summary


class PackageType(enum.IntEnum):
    '''
    Type of the package.
    '''
    UNKNOWN = 0
    SOURCE = enum.auto()
    BINARY = enum.auto()


class DebType(enum.IntEnum):
    '''
    Type of the Debian package.
    '''
    UNKNOWN = 0
    DEB = enum.auto()
    UDEB = enum.auto()

    def __str__(self):
        if self.value == self.DEB:
            return 'deb'
        elif self.value == self.UDEB:
            return 'udeb'
        return 'unknown'


def debtype_from_string(s):
    '''
    Convert the text representation into the enumerated type.
    '''
    if s == 'deb':
        return DebType.DEB
    elif s == 'udeb':
        return DebType.UDEB
    return DebType.UNKNOWN


class PackagePriority(enum.IntEnum):
    '''
    Priority of a Debian package.
    '''
    UNKNOWN = 0
    REQUIRED = enum.auto()
    IMPORTANT = enum.auto()
    STANDARD = enum.auto()
    OPTIONAL = enum.auto()
    EXTRA = enum.auto()


def packagepriority_from_string(s):
    '''
    Convert the text representation into the enumerated type.
    '''
    if s == 'optional':
        return PackagePriority.OPTIONAL
    elif s == 'extra':
        return PackagePriority.EXTRA
    elif s == 'standard':
        return PackagePriority.STANDARD
    elif s == 'important':
        return PackagePriority.IMPORTANT
    elif s == 'required':
        return PackagePriority.REQUIRED
    return PackagePriority.UNKNOWN


class VersionPriority(enum.IntEnum):
    '''
    Priority of a package upload.
    '''
    LOW = 0
    MEDIUM = enum.auto()
    HIGH = enum.auto()
    CRITICAL = enum.auto()
    EMERGENCY = enum.auto()

    def __str__(self):
        if self.value == self.LOW:
            return 'low'
        elif self.value == self.MEDIUM:
            return 'medium'
        elif self.value == self.HIGH:
            return 'high'
        elif self.value == self.CRITICAL:
            return 'critical'
        elif self.value == self.EMERGENCY:
            return 'emergency'
        return 'unknown'


class PackageInfo:
    '''
    Basic package information, used by
    :SourcePackage to refer to binary packages.
    '''
    deb_type = DebType.DEB
    name = None
    version = None
    section = None
    priority = PackagePriority.UNKNOWN
    architectures = None


class ArchiveFile(Base):
    '''
    A file in the archive.
    '''
    __tablename__ = 'archive_files'

    id = Column(Integer, primary_key=True)

    fname = Column(Text())
    size = Column(Integer())  # the size of the file
    time_created = Column(DateTime(), default=datetime.utcnow)  # Time when this file was created

    md5sum = Column(CHAR(32))  # the files' MD5 checksum
    sha1sum = Column(CHAR(40))  # the files' SHA1 checksum
    sha256sum = Column(CHAR(64))  # the files' SHA256 checksum

    srcpkg_id = Column(UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'))
    binpkg_id = Column(UUID(as_uuid=True), ForeignKey('archive_pkgs_binary.uuid'), unique=True, nullable=True)
    binpkg = relationship('BinaryPackage', back_populates='bin_file')
    srcpkg = relationship('SourcePackage', back_populates='files')

    def make_url(self, urlbase):
        if urlbase[-1] == '/':
            return urlbase + str(self.fname)
        else:
            return urlbase + '/' + str(self.fname)


class SourcePackage(Base):
    '''
    Data of a source package.
    '''
    __tablename__ = 'archive_pkgs_source'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)

    # The unique identifier for the whole source packaging project (stays the same even if the package version changes)
    source_uuid = Column(UUID(as_uuid=True), default=None, nullable=False)

    name = Column(String(256))  # Source package name
    version = Column(DebVersion())  # Version of this package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')

    suites = relationship('ArchiveSuite', secondary=srcpkg_suite_assoc_table, back_populates='pkgs_source')  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'))
    component = relationship('ArchiveComponent')  # Component this package is in

    time_added = Column(DateTime(), default=datetime.utcnow)  # Time when this package was first seen
    time_published = Column(DateTime(), nullable=True)  # Time when this package was published in the archive

    section_id = Column(Integer, ForeignKey('archive_sections.id'))
    section = relationship('ArchiveSection')  # Section of the source package

    architectures = Column(ARRAY(String(64)))  # List of architectures this source package can be built for

    standards_version = Column(String(256))
    format_version = Column(String(64))

    homepage = Column(Text())
    vcs_browser = Column(Text())

    maintainer = Column(Text())
    original_maintainer = Column(Text())
    uploaders = Column(ARRAY(Text()))

    build_depends = Column(ARRAY(Text()))
    build_depends_indep = Column(ARRAY(Text()))

    build_conflicts = Column(ARRAY(Text()))
    build_conflicts_indep = Column(ARRAY(Text()))

    files = relationship('ArchiveFile', back_populates='srcpkg', cascade='all, delete, delete-orphan')
    directory = Column(Text())

    binaries = relationship('BinaryPackage',
                            back_populates='source')

    _expected_binaries_json = Column('expected_binaries', JSON)
    extra_data = Column(MutableDict.as_mutable(JSONB))  # Additional key-value metadata that may be specific to this package

    _expected_binaries = None

    @property
    def expected_binaries(self):
        if self._expected_binaries is not None:
            return self._expected_binaries
        data = json.loads(self._expected_binaries_json)
        res = []
        for e in data:
            info = PackageInfo()
            info.deb_type = e.get('deb_type', DebType.DEB)
            info.name = e.get('name')
            info.version = e.get('version')
            info.section = e.get('section')
            info.priority = e.get('priority', PackagePriority.UNKNOWN)
            info.architectures = e.get('architectures')
            res.append(info)
        self._expected_binaries = res
        return res

    @expected_binaries.setter
    def expected_binaries(self, value):
        if not type(value) is list:
            value = [value]

        data = []
        for v in value:
            d = {'deb_type': v.deb_type,
                 'name': v.name,
                 'version': v.version,
                 'section': v.section,
                 'priority': v.priority,
                 'architectures': v.architectures}
            data.append(d)
        self._expected_binaries_json = json.dumps(data)
        self._expected_binaries = None  # Force the data to be re-loaded from JSON

    @staticmethod
    def generate_uuid(repo_name, name, version):
        return uuid.uuid5(UUID_NS_SRCPACKAGE, '{}::source/{}/{}'.format(repo_name, name, version))

    @staticmethod
    def generate_source_uuid(repo_name, name):
        return uuid.uuid5(UUID_NS_SRCPACKAGE, '{}::source/{}'.format(repo_name, name))

    def update_uuid(self):
        if not self.repo:
            raise Exception('Source package is not associated with a repository!')

        self.update_source_uuid()
        self.uuid = SourcePackage.generate_uuid(self.repo.name, self.name, self.version)

        return self.uuid

    def update_source_uuid(self):
        if not self.repo:
            raise Exception('Source package is not associated with a repository!')

        self.source_uuid = SourcePackage.generate_source_uuid(self.repo.name, self.name)
        return self.source_uuid

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        return '{}::source/{}/{}'.format(repo_name, self.name, self.version)


class PackageOverrides(Base):
    '''
    Data of a binary package.
    '''
    __tablename__ = 'archive_pkg_overrides'

    id = Column(Integer, primary_key=True)

    pkgname = Column(String(256))  # Name of the binary package name

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')

    suite_id = Column(Integer, ForeignKey('archive_suites.id'))
    suite = relationship('ArchiveSuite')

    essential = Column(Boolean(), default=False)  # Whether this package is marked as essential
    priority = Column(Enum(PackagePriority))  # Priority of the package

    section_id = Column(Integer, ForeignKey('archive_sections.id'))
    section = relationship('ArchiveSection')  # Section of the package


class BinaryPackage(Base):
    '''
    Data of a binary package.
    '''
    __tablename__ = 'archive_pkgs_binary'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=None, nullable=False)
    deb_type = Column(Enum(DebType))  # Deb package type

    name = Column(String(256))  # Package name
    version = Column(DebVersion())  # Version of this package

    repo_id = Column(Integer, ForeignKey('archive_repositories.id'))
    repo = relationship('ArchiveRepository')  # Repository this package belongs to

    suites = relationship('ArchiveSuite', secondary=binpkg_suite_assoc_table, back_populates='pkgs_binary')  # Suites this package is in

    component_id = Column(Integer, ForeignKey('archive_components.id'))
    component = relationship('ArchiveComponent')  # Component this package is in

    architecture_id = Column(Integer, ForeignKey('archive_architectures.id'))
    architecture = relationship('ArchiveArchitecture', back_populates='pkgs_binary')  # Architecture this binary was built for

    source_id = Column(UUID(as_uuid=True), ForeignKey('archive_pkgs_source.uuid'))
    source = relationship('SourcePackage', back_populates='binaries')

    size_installed = Column(Integer())  # Size of the installed package

    description = Column(Text())
    description_md5 = Column(CHAR(32))

    depends = Column(ARRAY(Text()))
    pre_depends = Column(ARRAY(Text()))

    replaces = Column(ARRAY(Text()))
    provides = Column(ARRAY(Text()))
    recommends = Column(ARRAY(Text()))
    suggests = Column(ARRAY(Text()))
    enhances = Column(ARRAY(Text()))
    conflicts = Column(ARRAY(Text()))
    breaks = Column(ARRAY(Text()))

    built_using = Column(ARRAY(Text()))

    maintainer = Column(Text())
    homepage = Column(Text())

    multi_arch = Column(CHAR(32))

    time_published = Column(DateTime(), nullable=True)  # Time when this package was published in the archive
    phased_update_percentage = Column(SmallInteger(), default=100)

    extra_data = Column(MutableDict.as_mutable(JSONB))  # Additional key-value metadata that may be specific to this package

    bin_file = relationship('ArchiveFile', uselist=False, back_populates='binpkg', cascade='all, delete, delete-orphan')
    sw_cpts = relationship('SoftwareComponent', secondary=swcpt_binpkg_assoc_table, back_populates='pkgs_binary')

    __ts_vector__ = create_tsvector(
        cast(func.coalesce(name, ''), TEXT),
        cast(func.coalesce(description, ''), TEXT)
    )

    __table_args__ = (
        Index(
            'idx_bin_package_fts',
            __ts_vector__,
            postgresql_using='gin'
        ),
    )

    @staticmethod
    def generate_uuid(repo_name, name, version, arch_name):
        return uuid.uuid5(UUID_NS_BINPACKAGE, '{}::{}/{}/{}'.format(repo_name, name, version, arch_name))

    def update_uuid(self):
        if not self.repo:
            raise Exception('Binary package is not associated with a repository!')

        self.uuid = BinaryPackage.generate_uuid(self.repo.name, self.name, self.version, self.architecture.name)
        return self.uuid

    def __str__(self):
        repo_name = '?'
        if self.repo:
            repo_name = self.repo.name
        arch_name = 'unknown'
        if self.architecture:
            arch_name = self.architecture.name
        return '{}::{}/{}/{}'.format(repo_name, self.name, self.version, arch_name)


# index to speed up data imports, where packages belonging to a certain repository/arch combination
# are requested frequently
bin_package_repo_arch_index = Index('idx_bin_package_repo_arch',
                                    BinaryPackage.repo_id,
                                    BinaryPackage.architecture_id)


class SoftwareComponent(Base):
    '''
    Description of a software component as described by the AppStream
    specification.
    '''
    __tablename__ = 'archive_sw_components'

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kind = Column(Integer())  # The component type

    cid = Column(Text())  # The component ID of this software
    gcid = Column(Text())  # The global component ID as used by appstream-generator

    name = Column(Text())  # Name of this component
    summary = Column(Text())  # Short description of this component
    description = Column(Text())  # Description of this component

    icon_name = Column(String(256))  # Name of the primary cached icon of this component

    is_free = Column(Boolean(), default=False)  # Whether this component is "free as in freedom" software
    project_license = Column(Text())  # License of this software
    developer_name = Column(Text())  # Name of the developer of this software

    supports_touch = Column(Boolean(), default=False)  # Whether this component supports touch input

    categories = Column(ARRAY(String(256)))  # Categories this component is in

    pkgs_binary = relationship('BinaryPackage',
                                secondary=swcpt_binpkg_assoc_table,
                                order_by='desc(BinaryPackage.version)',
                                back_populates='sw_cpts')  # Packages this software component is contained in

    flatpakref_uuid = Column(UUID(as_uuid=True), ForeignKey('flatpak_refs.uuid'))
    flatpakref = relationship('FlatpakRef')

    xml = Column(Text())  # XML representation in AppStream collection XML for this component

    __ts_vector__ = create_tsvector(
        cast(func.coalesce(name, ''), TEXT),
        cast(func.coalesce(summary, ''), TEXT),
        cast(func.coalesce(description, ''), TEXT)
    )

    __table_args__ = (
        Index(
            'idx_sw_components_fts',
            __ts_vector__,
            postgresql_using='gin'
        ),
    )

    cpt = None

    def update_uuid(self):
        '''
        Update the unique identifier for this component.
        '''
        if not self.gcid and not self.xml:
            raise Exception('Global component ID is not set for this component, and no XML data was found for it. Can not create UUID.')

        self.uuid = uuid.uuid5(UUID_NS_SWCOMPONENT, self.gcid if self.gcid else self.xml)
        return self.uuid

    def load(self, context=None):
        '''
        Load the actual AppStream component from stored XML data.
        An existing AppStream Context instance can be reused.
        '''

        # return the AppStream component if we already have it
        if self.cpt:
            return self.cpt

        # set up the context
        if not context:
            import gi
            gi.require_version('AppStream', '1.0')
            from gi.repository import AppStream
            context = AppStream.Context()
        context.set_style(AppStream.FormatStyle.COLLECTION)

        if not self.xml:
            raise Exception('Can not load AppStream component from empty data.')

        self.cpt = AppStream.Component()
        self.cpt.load_from_xml_data(context, self.xml)
        self.cpt.set_active_locale('C')

        return self.cpt


def get_archive_sections():
    '''
    Retrieve a list of dictionaries describing the archive
    sections that are currently supported.
    This function does read a local data file, instead of information
    from the database.
    '''
    from ..localconfig import get_data_file

    with open(get_data_file('archive-sections.json'), 'r') as f:
        sections = json.load(f)

    # validate & refine data
    for section in sections:
        if 'name' not in section:
            raise Exception('Invalid section contained in archive sections file (name missing).')
        if 'summary' not in section:
            section['summary'] = 'The {} section'.format(section['name'])

    return sections
