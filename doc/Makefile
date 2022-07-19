BIN ?= asciidoctor
MAN_OPTS ?= --backend manpage
REVNUMBER := $(shell python3 -c 'exec(open("../fatbuildr/version.py").read()); print(__version__)')

all: man

man: man/fatbuildrctl.1

man/%.1: man/%.adoc modules/usage/pages/%.adoc
	$(BIN) $(MAN_OPTS) --attribute mansource="Fatbuildr v$(REVNUMBER)" $<
