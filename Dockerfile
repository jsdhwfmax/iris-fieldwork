FROM containers.intersystems.com/intersystems/iris-community:2026.2@sha256:87c8b9062530093d30384d66caa9933b8399bfbace7ddb7f1bdb983c0bfdb85b

USER root
# The pinned image's initializer references bin/ while these files ship in csp/bin/.
RUN test -e /usr/irissys/bin/CSPpwd || cp -p /usr/irissys/csp/bin/CSPpwd /usr/irissys/bin/CSPpwd
RUN test -e /usr/irissys/bin/CSPx.so || cp -p /usr/irissys/csp/bin/CSPx.so /usr/irissys/bin/CSPx.so
COPY --chown=51773:51773 iris/ /opt/fieldwork/
USER irisowner
CMD ["--password-file", "/run/secrets/iris-password", "--after", "iris session IRIS -U %SYS < /opt/fieldwork/install.script"]
