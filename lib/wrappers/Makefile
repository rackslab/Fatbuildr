CFLAGS ?= -Wall -Wextra
TEMPLATE = u-bin.c.in
WRAPPERS = u-nspawn u-mkosi

all: $(WRAPPERS)

u-nspawn.c: $(TEMPLATE)
	sed -e 's|#BIN#|/usr/bin/systemd-nspawn|' $^ > $@

u-mkosi.c: $(TEMPLATE)
	sed -e 's|#BIN#|/usr/bin/mkosi|' $^ > $@

%: %.c
	$(CC) $(CFLAGS) -o $@ $^

install:
	install -d -m 755 $(DESTDIR)/usr/libexec/fatbuildr
	for _WRAPPER in $(WRAPPERS); do \
		install -m 500 $$_WRAPPER $(DESTDIR)/usr/libexec/fatbuildr; \
	done
