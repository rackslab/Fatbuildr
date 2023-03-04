#!/bin/sh

mkdir -p generated-doc/modules/misc/partials
pandoc --from markdown --to asciidoctor CHANGELOG.md --output generated-doc/modules/misc/partials/CHANGELOG.adoc
