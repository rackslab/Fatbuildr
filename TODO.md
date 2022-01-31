# Must have v1.0

- [x] Start containers w/o user namespaces so cowbuilder/mock have real permissions
- [x] Test build of real RPM
- [x] Test build of real Deb
- [x] mkosi fedora35 + debiansid
- [x] Test mock with output dir outside of chroot
- [x] Script to setup images + builders on debian11
- [x] Script to generate GPG key
- [x] Add configuration parameters in input repository for GPG keys
- [x] Add code to publish packages in repositories
- [x] GPG sign key for packages
- [x] Add logger to build-pkg
- [x] Add real arg parser
- [x] Configuration (at least with paths)
- [x] Redevelop build-images.sh in Python
- [x] Use mimetype to open tarball with correct options according to format
- [x] Support images and build environment updates in build-images
- [x] Add force mode in build-images to recreating the images when they exists
- [x] Use prefix instead of subdir for tmpdir so ordinary user can create them
- [x] Avoid shell instanciation in cowbuilder environments with fatbuildrd
- [x] Archive builds
- [x] Move build exception handling in BuilderArtefact.run() to write errors in build log
- [x] Save artefact build logs into files
- [x] Implement fatbuildrctl watch
- [x] Add fatbuildrctl build --watch option
- [x] Manage multiple instances on the same server
- [x] Show jobs states with fatbuildrctl list
- [x] Implement fatbuildrd using dbus service for build and registry
- [x] Implement fatbuildrctl registry
- [x] Implement fatbuildrctl archives
- [x] Support build of mkosi images
- [x] Develop web services with HTML pages
- [ ] Fix releasever error in rpm.img :
      ```
      [root@rpm ~]# dnf search rpmsign
      Unable to detect release version (use '--releasever' to specify release version)
      Fedora $releasever - …
      Errors during downloading metadata for repository 'fedora':
      - Status code: 404 for https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=x86_64 (IP: 18.133.140.134)
      Error: Failed to download metadata for repo 'fedora': Cannot prepare internal mirrorlist: Status code: 404 for https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=x86_64 (IP: 18.133.140.134)
      ```
- [x] Support build submission through REST API and fatbuildrctl
- [x] Support build watch through REST API and fatbuildrctl
- [x] Support fatbuildrctl list through REST API
- [x] Avoid timer reaching its end during builds
- [x] Filter out server/timer threads logs from build logs
- [ ] Get access to registries and their artefacts through web app
- [ ] Working REST API
- [ ] WSGI script for web app
- [ ] pep8 code formatting
- [ ] Run fatbuildrd with dedicated system user with limited permissions
- [ ] Polkit rules to restrict access to dbus service
- [ ] Support distributions derivatives
- [ ] Deb and RPM packages
- [ ] Documentation for installation and usage
- [ ] Online hosted documentation

# Nice to have (maybe in next releases)

- [ ] Logo!
- [ ] Make CleanupRegistry handle tmp directory creation using a Singleton
- [x] Add logger formatter with colors when connected to tty
- [ ] Add logger formatter in build logs for watch post-processing
- [ ] Define dbus structure from dict definitions with custom DbusData
- [ ] Run lintian after build to check packages
- [ ] Check image and build env exist before build
- [ ] Browse archives in the web app
- [ ] Add fatbuildrctl images --shell option
- [ ] Add fatbuildrctl images --format filter
- [ ] Add debchanges/cowbuilder commands in conf
- [ ] Remove pbuilder hooks from deb image
- [ ] Properly manage packages architectures
- [ ] Manage images and build environment through dbus
- [ ] Manage keyring through dbus
- [x] Rename BuilderArtefact class to ArtefactBuild
- [x] Rename BuilderArtefact.tmpdir to ArtefactBuild.place
- [ ] Add option to avoid fatbuildr log filter (ie. full debug mode for libs logs)
- [ ] Hooks for build submissions, build start and end
- [ ] Service hardening and sandboxing with systemd: https://www.ctrl.blog/entry/systemd-service-hardening.html
- [ ] Use f-strings everywhere
- [ ] Remove string format usage in logger
- [ ] Authentication in web app (JSON web token?)
- [ ] Get list of files in binary artefacts in web app
- [ ] Add feature to prepare git dev environment to help adapt debian patches (inspired from `gbp pq`)
- [ ] Define a plan for OSI build support regarding PT https://github.com/systemd/mkosi/pull/892
