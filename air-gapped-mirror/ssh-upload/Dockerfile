# ---- Dedicated, no-shell, chrooted SFTP endpoint for local-file uploads ----
#
# NOT currently deployed -- the mirror is git/apt/pip only for now, and the
# Helm chart has no template for this. Kept in-tree, and the fixes
# below are real ones found while testing it, but re-enabling still needs
# the chroot-vs-non-root-sync-job conflict resolved: sshd requires
# /var/mirror/files be root:root and not group-writable, while the sync
# job writes there as a non-root uid via fsGroup. A POSIX ACL granting
# uid 1000 write access (setfacl -m u:1000:rwx, hence `acl` below and the
# pinned uid) satisfies both, since ACLs don't change the mode bits
# sshd's check inspects -- verified as far as sshd accepting the login.
FROM alpine:3.20

RUN apk add --no-cache openssh-server acl \
 && ssh-keygen -A \
 # Pinned uid so the ACL above can reference it by number rather than
 # whatever adduser happens to pick next.
 && adduser -D -H -u 1000 -s /sbin/nologin uploader \
 # adduser -D leaves the shadow password field as "!" (administratively
 # locked), which makes sshd refuse *all* logins for the account -- pubkey
 # included -- regardless of PasswordAuthentication. "*" means "no valid
 # password" without the lock.
 && sed -i 's/^uploader:!:/uploader:*:/' /etc/shadow \
 && mkdir -p /run/sshd /var/mirror/files /etc/ssh/authorized_keys \
 && chown root:root /var/mirror/files && chmod 755 /var/mirror/files

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2222
ENTRYPOINT ["/entrypoint.sh"]
