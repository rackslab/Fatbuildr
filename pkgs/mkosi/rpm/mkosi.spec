Name:           mkosi
Version:	{{ version }}
Release:	{{ release }}
Summary:        Create bespoke OS images

License:        LGPLv2+
URL:            https://github.com/systemd/mkosi
{{ source }}
{{ patches }}

BuildArch:      noarch
%if 0%{?rhel} != 0 && 0%{?rhel} <= 8
BuildRequires:  python38-devel
BuildRequires:  python38-setuptools
BuildRequires:  python3-rpm-macros
BuildRequires:  python38-rpm-macros
%else
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pytest
BuildRequires:  python3-pexpect
%endif

%global recoreq %{?el7:Requires}%{!?el7:Recommends}

%{recoreq}:     dnf
%{recoreq}:     gnupg
%{recoreq}:     xz
%{recoreq}:     tar
%{recoreq}:     e2fsprogs
%{recoreq}:     squashfs-tools
%{recoreq}:     veritysetup
%if 0%{?el7} == 0
Recommends:     debootstrap
Recommends:     arch-install-scripts
Recommends:     edk2-ovmf
Recommends:     btrfs-progs
Recommends:     dosfstools
Recommends:     cpio
Recommends:     zstd
Recommends:     python3dist(argcomplete)
Recommends:     python3dist(cryptography)
%endif

%description
A fancy wrapper around "dnf --installroot", "debootstrap" and
"pacstrap", that may generate disk images with a number of bells and
whistles.

Generated images are tailed to the purose. This means GPT disk labels
are used by default, though MBR disk labels are supported, and only
systemd based images may be generated.

%prep
#%autosetup -p1
{{ prep_sources }}
{{ prep_patches }}

%build
%py3_build

%install
%py3_install

%files
%license LICENSE
%doc README.md
%_bindir/mkosi
%{python3_sitelib}/mkosi/
%{python3_sitelib}/mkosi-%{version}-py*.egg-info/
%_mandir/man1/mkosi.1*

%check
%if ! 0%{?el8}
%pytest tests/ -v

# just a smoke test for syntax or import errors
%buildroot/usr/bin/mkosi --help >/dev/null
%endif

{{ changelog }}
