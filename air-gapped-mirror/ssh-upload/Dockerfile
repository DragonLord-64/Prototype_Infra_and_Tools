# ---- Dedicated, no-shell, chrooted SFTP endpoint for local-file uploads ----
FROM alpine:3.20

RUN apk add --no-cache openssh-server \
 && ssh-keygen -A \
 && adduser -D -H -s /sbin/nologin uploader \
 && mkdir -p /run/sshd /var/mirror/files /etc/ssh/authorized_keys \
 && chown root:root /var/mirror/files && chmod 755 /var/mirror/files

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2222
ENTRYPOINT ["/entrypoint.sh"]
