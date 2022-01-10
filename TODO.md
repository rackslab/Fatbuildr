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
- [ ] Implement fatbuildrd using dbus service for build and registry
- [ ] Run fatbuildrd with dedicated system user with limited permissions
- [ ] Implement fatbuildrctl registry
- [ ] Implement fatbuildrctl archives
- [ ] Support build of mkosi images
- [ ] Develop web services with JSON REST API and HTML pages
- [ ] Fix releasever error in rpm.img :
      ```
      [root@rpm ~]# dnf search rpmsign
      Unable to detect release version (use '--releasever' to specify release version)
      Fedora $releasever - …
      Errors during downloading metadata for repository 'fedora':
      - Status code: 404 for https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=x86_64 (IP: 18.133.140.134)
      Error: Failed to download metadata for repo 'fedora': Cannot prepare internal mirrorlist: Status code: 404 for https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=x86_64 (IP: 18.133.140.134)
      ```

# Nice to have

- [ ] Add logger formatter with colors when connected to tty
- [ ] Add logger formatter in build logs for watch post-processing
- [ ] Add feature to prepare git dev environment to help adapt debian patches (inspired from `gbp pq`)
- [ ] Run lintian after build to check packages
- [ ] Check image and build env exist before build
- [ ] Add fatbuildrctl images --shell option
- [ ] Add fatbuildrctl images --format filter
- [ ] Add debchanges/cowbuilder commands in conf
- [ ] Remove pbuilder hooks from deb image
- [ ] Properly manage packages architectures
- [ ] Rename BuilderArtefact class to ArtefactBuild
- [ ] Rename BuilderArtefact.tmpdir to ArtefactBuild.dir
