- [x] Start containers w/o user namespaces so cowbuilder/mock have real permissions
- [x] Test build of real RPM
- [~] Test build of real Deb → hfd5 error:

libtool: compile:  gcc -DHAVE_CONFIG_H -I. -I../../../../../src/plugins/acct_gather_profile/hdf5 -I../../../.. -I../../../../slurm -DSLURM_PLUGIN_DEBUG -I../../../../.. -I/usr/include/hdf5/serial -I/usr/include -Wdate-time -D_FORTIFY_SOURCE=2 -DNUMA_VERSION1_COMPATIBILITY -g -O2 -ffile-prefix-map=/build/slurm-wlm-20.11.8=. -fstack-protector-strong -Wformat -Werror=format-security -fno-omit-frame-pointer -pthread -c ../../../../../src/plugins/acct_gather_profile/hdf5/hdf5_api.c  -fPIC -DPIC -o .libs/hdf5_api.o
In file included from /usr/include/hdf5/serial/H5public.h:32,
                 from /usr/include/hdf5/serial/hdf5.h:22,
                 from ../../../../../../src/plugins/acct_gather_profile/hdf5/sh5util/../hdf5_api.h:49,
                 from ../../../../../../src/plugins/acct_gather_profile/hdf5/sh5util/sh5util.c:65:
/usr/include/hdf5/serial/H5version.h:39:4: error: #error "Can't choose old API versions when deprecated APIs are disabled"
   39 |   #error "Can't choose old API versions when deprecated APIs are disabled"
      |    ^~~~~
make[8]: *** [Makefile:602: sh5util.o] Error 1
make[8]: *** Waiting for unfinished jobs....

- [x] mkosi fedora35 + debiansid
- [ ] Test mock with output dir outside of chroot
- [ ] Test mock with ordinary user
- [ ] Script to setup images + builders on debian11
- [ ] GPG sign key for packages and mkosi images
