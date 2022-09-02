Name:     hello
Version:  {{ version }}
Release:  {{ release }}
Summary:  Produces a familiar, friendly greeting
License:  GPLv3+
URL:      https://www.gnu.org/software/hello/
{{ source }}
{{ patches }}

BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  make

%description
The GNU Hello program produces a familiar, friendly greeting. Yes, this is
another implementation of the classic program that prints “Hello, world!” when
you run it.

%prep
{{ prep_sources }}
{{ prep_patches }}

%build
%configure
%make_build

%install
%make_install
rm %{buildroot}/%{_infodir}/dir
%find_lang %{name}

%files -f %{name}.lang
%{_mandir}/man1/hello.1.*
%{_infodir}/hello.info.*
%{_bindir}/hello
%doc AUTHORS ChangeLog NEWS README THANKS TODO
%license COPYING

{{ changelog }}
