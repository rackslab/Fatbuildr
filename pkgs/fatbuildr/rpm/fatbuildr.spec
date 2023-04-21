%?python_enable_dependency_generator

Name:           fatbuildr
Version:        {{ version }}
Release:        {{ release }}

License:        GPLv3+
Group:          System Environment/Base
URL:            https://github.com/rackslab/fatbuildr
{{ sources }}
{{ patches }}
Summary:        Software solution to build artifacts and publish them in registries
Requires:       %{name}-common
Requires:       %{name}-wrappers
Requires:       createrepo_c
Requires:       dnf
Requires:       mkosi >= 14
Requires:       reprepro
Requires:       rpm
Requires:       rpm-sign
Requires:       systemd-container
%if 0%{?rhel} <= 8
Requires:       python3-cached_property
%endif
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  make
BuildRequires:  gcc
BuildRequires:  asciidoctor
BuildRequires:  systemd
BuildRequires:  systemd-rpm-macros

%description
Software solution to build artifacts and publish them in registries
Fatbuildr is a software solution to build various forms of artifacts (eg. deb
and RPM packages) and publish them in managed registries with integrated
keyring.

This package contains the main Fatbuildr applications.

%package -n %{name}-common
Summary:        Shared requirements for Fatbuildr components
BuildArch:      noarch

%description -n %{name}-common
Fatbuildr is a software solution to build various forms of artifacts (eg. deb
and RPM packages) and publish them in managed registries with integrated
keyring.

This package contains the architecture independant requirements shared by
Fatbuildr components.

%package -n %{name}-wrappers
Summary:        Wrappers to run privileged operations in Fatbuildr
Requires:       %{name}-common

%description -n %{name}-wrappers
Fatbuildr is a software solution to build various forms of artifacts (eg. deb
and RPM packages) and publish them in managed registries with integrated
keyring.

This package contains the architecture independant requirements shared by
Fatbuildr components.

%prep
{{ prep_sources }}
{{ prep_patches }}

%build
%set_build_flags
%py3_build
make -C lib/wrappers
make -C docs

%install
%py3_install
make DESTDIR=%{buildroot} -C lib/wrappers install

install -d %{buildroot}%{_sysconfdir}/fatbuildr
install -d %{buildroot}%{_sysconfdir}/fatbuildr/instances.d
install -p -m 0644 conf/etc/fatbuildr.ini %{buildroot}%{_sysconfdir}/fatbuildr

install -d %{buildroot}%{_datadir}/fatbuildr
install -p -m 0644 conf/vendor/fatbuildr.ini %{buildroot}%{_datadir}/fatbuildr/
cp -vdr --no-preserve=ownership conf/registry %{buildroot}%{_datadir}/fatbuildr/
cp -vdr --no-preserve=ownership conf/images %{buildroot}%{_datadir}/fatbuildr/
cp -vdr --no-preserve=ownership conf/web %{buildroot}%{_datadir}/fatbuildr/
install -p -D -m 0644 conf/system/service/* -t %{buildroot}%{_unitdir}
install -p -D -m 0644 conf/dbus/*.conf -t %{buildroot}%{_datadir}/dbus-1/system.d
install -p -D -m 0644 conf/dbus/*.service -t %{buildroot}%{_datadir}/dbus-1/system-services
install -p -D -m 0644 conf/polkit/*.policy -t %{buildroot}%{_datadir}/polkit-1/actions
install -p -D -m 0644 conf/polkit/*.rules -t %{buildroot}%{_datadir}/polkit-1/rules.d

install -d %{buildroot}%{_datadir}/fatbuildr/web/static/js
install -d %{buildroot}%{_datadir}/fatbuildr/web/static/css
install -p -m 0644 bootstrap/js/*.js -t %{buildroot}%{_datadir}/fatbuildr/web/static/js
install -p -m 0644 bootstrap/css/*.css -t %{buildroot}%{_datadir}/fatbuildr/web/static/css
install -p -d assets/* %{buildroot}%{_datadir}/fatbuildr/web/static
install -d %{buildroot}%{_datadir}/fatbuildr/wsgi
install -d %{buildroot}%{_datadir}/fatbuildr/wsgi/uwsgi
install -p -D -m 0644 lib/wsgi/*.wsgi -t %{buildroot}%{_datadir}/fatbuildr/wsgi
install -p -D -m 0644 lib/wsgi/uwsgi/* -t %{buildroot}%{_datadir}/fatbuildr/wsgi/uwsgi

# Install utilities
install -d %{buildroot}%{_datadir}/fatbuildr/utils
install -p -D -m 0755 utils/* -t %{buildroot}%{_datadir}/fatbuildr/utils

# Move service executables out of $PATH in libexec directory
mv %{buildroot}%{_bindir}/fatbuildrd %{buildroot}%{_libexecdir}
mv %{buildroot}%{_bindir}/fatbuildrweb %{buildroot}%{_libexecdir}

# sysuser conf
install -p -D -m 0644 conf/system/sysuser/%{name}.conf -t %{buildroot}%{_sysusersdir}/

# man pages
install -d %{buildroot}/%{_mandir}/man1
install -p -m 0644 docs/man/fatbuildrctl.1 %{buildroot}/%{_mandir}/man1/

# examples
install -d %{buildroot}/%{_docdir}/fatbuildr/examples
cp -vdr --no-preserve=ownership examples/* %{buildroot}/%{_docdir}/fatbuildr/examples
cp -vdr --no-preserve=ownership conf/examples/* %{buildroot}/%{_docdir}/fatbuildr/examples

%clean
rm -rf %{buildroot}

%files
%license LICENSE
%doc README.md
%doc CHANGELOG.md
%doc %{_docdir}/fatbuildr
%{python3_sitelib}/fatbuildr/
%{python3_sitelib}/Fatbuildr-*.egg-info/
%config(noreplace) %{_sysconfdir}/fatbuildr/*
%{_bindir}/fatbuildrctl
%{_libexecdir}/fatbuildrd
%{_libexecdir}/fatbuildrweb
%{_datadir}/fatbuildr/
%{_datadir}/dbus-1/system.d/*
%{_datadir}/dbus-1/system-services/*
%{_datadir}/polkit-1/rules.d/*
%{_datadir}/polkit-1/actions/*
%{_unitdir}/*
%doc %{_mandir}/man1/*

%files -n %{name}-common
%{_sysusersdir}/%{name}.conf

%files -n %{name}-wrappers
%attr(0500,fatbuildr,fatbuildr) %caps(cap_setuid,cap_setgid=ep) %{_libexecdir}/fatbuildr/u-*

%post -n %{name}-common
systemd-sysusers %{_sysusersdir}/%{name}.conf

{{ changelog }}
