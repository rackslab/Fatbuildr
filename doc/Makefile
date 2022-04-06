BIN ?= asciidoctor
MAN_OPTS ?= --backend manpage

all: man

man: man/fatbuildrctl.1

man/%.1: man/%.adoc modules/usage/pages/%.adoc
	$(BIN) $(MAN_OPTS) $<
