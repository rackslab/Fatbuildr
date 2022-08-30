# Based on Fedora python-dabus SRPM spec file, which can be found at:
# https://src.fedoraproject.org/rpms/python-dasbus

%global srcname dasbus

Name:           %{srcname}
Version:	{{ version }}
Release:	{{ release }}
Summary:        DBus library in Python 3

License:        LGPLv2+
URL:            https://pypi.python.org/pypi/dasbus
{{ source }}
{{ patches }}

BuildArch:      noarch

%global _description %{expand:
Dasbus is a DBus library written in Python 3, based on
GLib and inspired by pydbus. It is designed to be easy
to use and extend.}

%description %{_description}

%package -n python3-%{srcname}
Summary:        %{summary}
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
%if %{defined suse_version}
Requires:       python3-gobject
%else
Requires:       python3-gobject-base
%endif
%{?python_provide:%python_provide python3-%{srcname}}

%description -n python3-%{srcname} %{_description}

%prep
%autosetup -n %{srcname}-%{version}

%build
%py3_build

%install
%py3_install

%files -n python3-%{srcname}
%license LICENSE
%doc README.md
%{python3_sitelib}/%{srcname}-*.egg-info/
%{python3_sitelib}/%{srcname}/

{{ changelog }}
