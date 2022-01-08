- [x] Start containers w/o user namespaces so cowbuilder/mock have real permissions
- [x] Test build of real RPM
- [x] Test build of real Deb
- [x] mkosi fedora35 + debiansid
- [x] Test mock with output dir outside of chroot
- [ ] Test mock with ordinary user
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
- [ ] Save images build logs into files
- [ ] Archive builds
- [ ] Run fatbuildrd with dedicated system user with limited permissions
- [ ] Support build of mkosi images
- [ ] Add feature to prepare git dev environment to help adapt debian patches (inspired from `gbp pq`)
- [ ] Run lintian after build to check packages
- [x] Manage multiple instances on the same server
- [ ] Fix releasever error in rpm.img :
      ```
      [root@rpm ~]# dnf search rpmsign
      Unable to detect release version (use '--releasever' to specify release version)
      Fedora $releasever - …
      Errors during downloading metadata for repository 'fedora':
      - Status code: 404 for https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=x86_64 (IP: 18.133.140.134)
      Error: Failed to download metadata for repo 'fedora': Cannot prepare internal mirrorlist: Status code: 404 for https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=x86_64 (IP: 18.133.140.134)
      ```
- [ ] Properly manage packages architectures
