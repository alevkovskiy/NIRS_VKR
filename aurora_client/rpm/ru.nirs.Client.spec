Name:       ru.nirs.Client
Version:    0.1.0
Release:    1
Summary:    NIRS native Aurora OS client
License:    Proprietary
Source0:    %{name}-%{version}.tar.gz

BuildRequires: pkgconfig(auroraapp)
BuildRequires: pkgconfig(Qt5Core)
BuildRequires: pkgconfig(Qt5Gui)
BuildRequires: pkgconfig(Qt5Qml)
BuildRequires: pkgconfig(Qt5Quick)
BuildRequires: pkgconfig(Qt5Network)
Requires: sailfishsilica-qt5 >= 0.10.9

%description
Native Qt/QML client for NIRS chats and pipeline monitoring.

%prep
%autosetup

%build
%qmake5
%make_build

%install
%make_install

%files
%defattr(-,root,root,-)
%{_bindir}/%{name}
%{_datadir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.png
