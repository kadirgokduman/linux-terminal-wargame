# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# wargame/base — tek konteyner, seviye başına bir UNIX kullanıcısı
#
# Neden tek konteyner? Seviye zinciri (player00 → player01 → ...) gerçek
# UNIX kimlikleri, dosya izinleri ve SUID biti üzerinden kurulur. Her
# seviyeyi ayrı konteynere koymak bu zinciri sahte bir köprüye dönüştürür.
# İzolasyon konteyner sınırında sağlanır (bkz. compose.yaml).
# ---------------------------------------------------------------------------

FROM debian:12-slim AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*

COPY docker/reader.c  /src/reader.c
COPY docker/checker.c /src/checker.c
RUN mkdir -p /out \
 && gcc -O2 -Wall -Wextra -Werror -o /out/reader /src/reader.c \
 && gcc -O0 -g -fno-builtin -Wall -Wextra -Werror -o /out/checker /src/checker.c


FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONPATH=/opt/wargame/engine \
    PYTHONUNBUFFERED=1 \
    WARGAME_LEVELS=/opt/wargame/levels

# Bulmaca araçları: seviyeler yalnızca burada kurulu olanlara güvenebilir.
RUN apt-get update && apt-get install -y --no-install-recommends \
      openssh-server \
      cron \
      at \
      iproute2 \
      net-tools \
      lsof \
      acl \
      netcat-openbsd \
      tcpdump \
      ltrace \
      gdb \
      openssl \
      xxd \
      binutils \
      file \
      git \
      curl \
      less \
      vim-tiny \
      procps \
      psmisc \
      tar \
      gzip \
      bzip2 \
      xz-utils \
      jq \
      sudo \
      python3 \
      python3-yaml \
      libpam-modules \
 && rm -rf /var/lib/apt/lists/*

COPY docker/sshd_config   /etc/ssh/sshd_config
COPY docker/pam_sshd      /etc/pam.d/sshd
COPY docker/limits.conf   /etc/security/limits.d/wargame.conf
COPY docker/banner        /etc/wargame/banner
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/record-login.sh /usr/local/bin/record-login.sh
COPY engine               /opt/wargame/engine
COPY levels               /opt/wargame/levels
COPY --from=builder /out/reader  /opt/wargame/bin/reader
COPY --from=builder /out/checker /opt/wargame/bin/checker

RUN chmod 0755 /usr/local/bin/entrypoint.sh /usr/local/bin/record-login.sh /opt/wargame/bin/reader /opt/wargame/bin/checker \
 && mkdir -p /etc/wargame/pass /var/log/wargame /var/spool/wargame /run/sshd \
 && ssh-keygen -A \
 && chmod 0600 /etc/ssh/ssh_host_*_key

EXPOSE 22

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
