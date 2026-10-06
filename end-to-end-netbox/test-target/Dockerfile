FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends openssh-server python3 python3-venv iproute2 ca-certificates && rm -rf /var/lib/apt/lists/* && useradd -m -s /bin/bash ansible && passwd -d ansible && mkdir -p /run/sshd /home/ansible/.ssh
COPY authorized_keys /home/ansible/.ssh/authorized_keys
RUN chown -R ansible:ansible /home/ansible/.ssh && chmod 700 /home/ansible/.ssh && chmod 600 /home/ansible/.ssh/authorized_keys && printf 'PasswordAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/test.conf
COPY stubs /opt/netbox-demo/bin
COPY fixtures /opt/netbox-demo/fixtures
RUN chmod 755 /opt/netbox-demo/bin/* && printf "simulation-only\n" > /opt/netbox-demo/SIMULATION
RUN python3 -m venv /opt/venv/FHS
CMD ["/usr/sbin/sshd", "-D", "-e"]
