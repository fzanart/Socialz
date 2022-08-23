# Configuring virtual Git server on Mac M1

## 1. Virtual Machine:

from: https://mac.getutm.app/gallery/ubuntu-20-04  
from: https://www.youtube.com/watch?v=MVLbb1aMk24 

 1. Add virtual machine (Virtualize option on UTM)
 2. Complete initial instalation setup 
 3. Deleting USB drive w/ ISO image is important!
 ```
 sudo apt install tasksel
 sudo apt-get install ubuntu-desktop
 sudo apt update && sudo apt upgrade -y
 ```
 7. ```sudo reboot```

Then select user and before clicl ok change from Ubunto to Ubuntu on xorg (in settings) then Ok!

## 2. Install Gitea
from: https://docs.gitea.io/en-us/install-from-binary/  
from: https://linuxize.com/post/how-to-install-gitea-on-ubuntu-20-04/ 
from: https://linuxhint.com/install-gitea-ubuntu/

1. First ensure you have Firefox ```firefox --version``` otherwise, install it:
```
sudo apt install firefox
```
2. Download Gitea from terminal with wget
```
wget -O gitea https://dl.gitea.io/gitea/1.17.1/gitea-1.17.1-linux-arm64
sudo chmod +x /usr/local/bin/gitea
```

2. Prepare enviorment

 - 2.1 Gitea requires Git version >= 2.0.
Check with: ```git --version```

 - 2.2. Create a user to run Gitea:
```
sudo adduser \
   --system \
   --shell /bin/bash \
   --gecos 'Git Version Control' \
   --group \
   --disabled-password \
   --home /home/git \
   git
```
 - 2.3. Create required directory structure
```
sudo mkdir -pv /var/lib/gitea/{custom,data,log}
sudo chown -Rv git:git /var/lib/gitea
sudo chmod -Rv 750 /var/lib/gitea
sudo mkdir -v /etc/gitea
sudo chown -Rv root:git /etc/gitea
sudo chmod -Rv 770 /etc/gitea
```
3. Configure Gitea’s working directory
```
export GITEA_WORK_DIR=/var/lib/gitea/
```
5. Copy the Gitea binary to a global location
```
sudo cp gitea /usr/local/bin/gitea
```
7. Run Gitea as Linux service Using systemd
```
sudo nano /etc/systemd/system/gitea.service
```
 - copy the following:
```
[Unit]
Description=Gitea (Git with a cup of tea)
After=syslog.target
After=network.target
[Service]
RestartSec=2s
Type=simple
User=git
Group=git
WorkingDirectory=/var/lib/gitea/
ExecStart=/usr/local/bin/gitea web --config /etc/gitea/app.ini
Restart=always
Environment=USER=git HOME=/home/git GITEA_WORK_DIR=/var/lib/gitea
[Install]
WantedBy=multi-user.target
```
```
sudo systemctl daemon-reload
sudo systemctl enable gitea
sudo systemctl start gitea
```

8. Running from command-line/terminal
```
GITEA_WORK_DIR=/var/lib/gitea/ /usr/local/bin/gitea web -c /etc/gitea/app.ini
```

9. Enable metrics
```
sudo nano /etc/gitea/app.ini
```
```
[metrics]
ENABLED:true
```
## 3. Install prometheus
from: https://www.digitalocean.com/community/tutorials/how-to-install-prometheus-on-ubuntu-16-04 
from: https://www.robustperception.io/shutting-down-prometheus/ 

1. Copy:
```
sudo useradd --no-create-home --shell /bin/false prometheus
sudo useradd --no-create-home --shell /bin/false node_exporter
sudo mkdir /etc/prometheus
sudo mkdir /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus
sudo chown prometheus:prometheus /var/lib/prometheus
```
```
cd ~
curl -LO https://github.com/prometheus/prometheus/releases/download/v2.38.0/prometheus-2.38.0.linux-arm64.tar.gz
tar xvf prometheus-2.38.0.linux-arm64.tar.gz
sudo cp prometheus-2.0.0.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-2.0.0.linux-amd64/promtool /usr/local/bin/
sudo chown prometheus:prometheus /usr/local/bin/prometheus
sudo chown prometheus:prometheus /usr/local/bin/promtool
sudo cp -r prometheus-2.0.0.linux-amd64/consoles /etc/prometheus
sudo cp -r prometheus-2.0.0.linux-amd64/console_libraries /etc/prometheus
rm -rf prometheus-2.38.0.linux-arm64.tar.gz prometheus-2.38.0.linux-arm64
```
2. Configuring prometheus
```
sudo nano /etc/prometheus/prometheus.yml
sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
```
```
sudo -u prometheus /usr/local/bin/prometheus \
    --config.file /etc/prometheus/prometheus.yml \
    --storage.tsdb.path /var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries
```
7. Prometheus as Linux service Using systemd
```
sudo nano /etc/systemd/system/prometheus.service
```
 - copy the following:
```
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
    --config.file /etc/prometheus/prometheus.yml \
    --storage.tsdb.path /var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus
```
## 4. Install Grafana:
from: https://grafana.com/grafana/download/9.1.0?edition=enterprise&pg=get&platform=arm&plcmt=selfmanaged-box1-cta1  
from: https://prometheus.io/docs/visualization/grafana/ 
```
sudo apt-get install -y adduser libfontconfig1
wget https://dl.grafana.com/enterprise/release/grafana-enterprise_9.1.0_arm64.deb
sudo dpkg -i grafana-enterprise_9.1.0_arm64.deb
```
