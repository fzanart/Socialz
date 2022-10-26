# Configuring virtual Git server on Mac M1

## 1. Virtual Machine:
----
 1. Add virtual machine (Virtualize option on UTM)
 2. Complete initial instalation setup, and reboot. If it doesn't, shut down the virtual machine, go to its preferences and ```delete USB drive w/ ISO image```
 3. On the command line:

    ```
    sudo apt install tasksel
    sudo apt-get install ubuntu-desktop
    sudo apt update && sudo apt upgrade -y
    sudo apt install firefox
    ```
 4. Then,

    ```
    sudo reboot
    ```

5. Finally, select user and before clicking ok, change from Ubunto to Ubuntu on xorg (in settings) then Ok!

References:  
[1]: https://mac.getutm.app/gallery/ubuntu-20-04  
[2]: https://www.youtube.com/watch?v=MVLbb1aMk24

<br />

## 2. Install Gitea
----

1. Download Gitea from terminal with wget
   ```
   wget -O gitea https://dl.gitea.io/gitea/1.17.1/gitea-1.17.1-linux-arm64
   sudo chmod +x /usr/local/bin/gitea
   ```

2. Prepare enviorment

   2.1 Gitea requires Git version >= 2.0. Check with: ```git --version```

   2.2. Create a user to run Gitea:
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
   2.3. Create required directory structure
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
4. Copy the Gitea binary to a global location
   ```
   sudo cp gitea /usr/local/bin/gitea
   ```
5. Run Gitea as Linux service Using systemd
   ```
   sudo nano /etc/systemd/system/gitea.service
   ```
   Copy the following:
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

6. Running from command-line/terminal
   ```
   GITEA_WORK_DIR=/var/lib/gitea/ /usr/local/bin/gitea web -c /etc/gitea/app.ini
   ```

7. Enable metrics
   ```
   sudo nano /etc/gitea/app.ini
   ```
   ```
   [metrics]
   ENABLED:true
   ```
   ```
   systemctl restart gitea
   ```

References:  
[3] https://docs.gitea.io/en-us/install-from-binary/  
[4] https://linuxize.com/post/how-to-install-gitea-on-ubuntu-20-04/   
[5] https://linuxhint.com/install-gitea-ubuntu/

<br />

## 3. Install Prometheus:
----

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
   sudo cp prometheus-2.38.0.linux-arm64/prometheus /usr/local/bin/
   sudo cp prometheus-2.38.0.linux-arm64/promtool /usr/local/bin/
   sudo chown prometheus:prometheus /usr/local/bin/prometheus
   sudo chown prometheus:prometheus /usr/local/bin/promtool
   sudo cp -r prometheus-2.38.0.linux-arm64/consoles /etc/prometheus
   sudo cp -r prometheus-2.38.0.linux-arm64/console_libraries /etc/prometheus
   rm -rf prometheus-2.38.0.linux-arm64.tar.gz prometheus-2.38.0.linux-arm64
   ```
2. Configuring prometheus
   ```
   sudo nano /etc/prometheus/prometheus.yml
   ```
   ```                   
   global:
     scrape_interval: 15s 
     evaluation_interval: 15s 

   alerting:
     alertmanagers:
       - static_configs:
           - targets:

   rule_files:

   scrape_configs:

     - job_name: "prometheus"
       static_configs:
         - targets: ["localhost:9090"]

     - job_name: "gitea"
       static_configs:
         - targets: ["localhost:3000"]
   ```
   ```
   sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
   ```
   ```
   sudo -u prometheus /usr/local/bin/prometheus \
       --config.file /etc/prometheus/prometheus.yml \
       --storage.tsdb.path /var/lib/prometheus/ \
       --web.console.templates=/etc/prometheus/consoles \
       --web.console.libraries=/etc/prometheus/console_libraries
   ```
3. Prometheus as Linux service Using systemd
   ```
   sudo nano /etc/systemd/system/prometheus.service
   ```
   Copy the following:
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

References:  
[6] https://www.digitalocean.com/community/tutorials/how-to-install-prometheus-on-ubuntu-16-04  
[7] https://www.robustperception.io/shutting-down-prometheus/  

<br />

## 4. Install Grafana:
----
1. Download and install the application   
   ```
   sudo apt-get install -y adduser libfontconfig1
   wget https://dl.grafana.com/enterprise/release/grafana-enterprise_9.1.0_arm64.deb
   sudo dpkg -i grafana-enterprise_9.1.0_arm64.deb
   ```

2. Change default http port (clashes with Gitea in 3000) remove trailing ; replace 3000 with 4000 on:
   ```
   sudo nano /etc/grafana/grafana.ini
   ```
   ```
   sudo nano /usr/share/grafana/conf/defaults.ini
   ```
   ```
   sudo /usr/share/grafana/conf/sample.ini
   ```

3. Finally: 

   ```
   sudo /bin/systemctl daemon-reload 
   sudo /bin/systemctl enable grafana-server
   sudo /bin/systemctl start grafana-server
   ```

References:  
[8] https://grafana.com/grafana/download/9.1.0?edition=enterprise&pg=get&platform=arm&plcmt=selfmanaged-box1-cta1  
[9] https://prometheus.io/docs/visualization/grafana/  

<br />

## 5. Install Python:
----
1. With micromamba package manager, download:
   ```
   wget -qO- https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xvj bin/micromamba
   ./bin/micromamba shell init -s bash -p ~/micromamba
   source ~/.bashrc
   ```

   ```
   micromamba activate
   micromamba install python=3.8 jupyterlab jupyterlab-git networkx scipy scikit-learn pandas numpy requests matplotlib seaborn python-gitlab tqdm -c conda-forge
   pip install prometheus-pandas
   ```
   or create other enviorments
   ```
   micromamba create -n env_name xtensor -c conda-forge
   micromamba activate env_name
   ```
2. Generate Jupyter configuration file
   ```
   jupyter notebook --generate-config
   ```
   Edit the configuration file 
   ```
   sudo nano ~/.jupyter/jupyter_notebook_config.py
   ```
   and  set ```c.NotebookApp.use_redirect_file = False```

References:  
[10]: https://mamba.readthedocs.io/en/latest/  
[11]: https://stackoverflow.com/questions/55756151/how-to-set-jupyter-notebook-to-open-on-browser-automatically  

<br />

## 6. Install Gitlab:
----
1. Establishing a fully qualifyed domain name (FQDN) as gitlab.example.com:
   
   Get your ip address:
   ```
   sudo hostname -I
   ```
   In case you whant to change the name, go to ```sudo nano /etc/hostname```
   
   Go to:
   
   ```
   sudo nano /etc/hosts
   ```
   and add ```192.168.64.10 gitlab.example.com gitserver``` below localhost (replacing 127.0.1.1 gitserver)
   
   verify the changes with:
   ```
   sudo hostname -f
   ```

2. Download GitLab:
   ```
   wget --content-disposition https://packages.gitlab.com/gitlab/gitlab-ce/packages/ubuntu/focal/gitlab-ce_15.3.3-ce.0_arm64.deb/download.deb
   ```
   
3. Install dependencies
   ```
   sudo apt-get install -y curl openssh-server ca-certificates tzdata perl libatomic1
   ```
   Install postfix, but not necessary to configure it.
   ```
   sudo apt-get install -y postfix
   ```
   ```
   sudo GITLAB_ROOT_PASSWORD="<strongpassword>" EXTERNAL_URL="gitlab.example.com" dpkg -i gitlab-ce_15.3.3-ce.0_arm64.deb
   ```
   
4. Edit 
   ```
   sudo nano /etc/gitlab/gitlab.rb
   ```
   and set ```external_url 'gitlab.example.com'```   
   also set ```grafana['enable'] = true```
   
5. Then:
   ```
   sudo gitlab-ctl reconfigure
   gitlab-ctl start
   ```
6. Go to: ```gitlab.example.com``` and access using user ```root``` and password.
   A workaround to reset root's password would be:
   ```
   sudo gitlab-rake 'gitlab:password:reset[root]'
   ```

7. Whithin root, go to ```'Admin Area' - 'Settings' - 'Metrics and profiling'``` and enable Prometheus / Grafana.
   Go to ```'Admin Area' - 'Operations' - 'Metrics'``` to complete Grafana integration and observe dashboards.
   Grafana dashboards will be also available on http://gitlab.example.com/-/grafana.

8. In case Prometheus targets gets out of bounds errors, go to terminal and check the logs with ```sudo gitlab-ctl tail```
   Try fixing the errors with:

    ```
    sudo gitlab-ctl stop prometheus
    sudo rm -r /var/opt/gitlab/prometheus/data/wal
    sudo gitlab-ctl start prometheus
    ```   
    or   
    
    ```
    sudo gitlab-ctl restart
    sudo su -
    cd /var/opt/gitlab/prometheus/data
    rm -rf 0* wal/0* wal/checkpoint.0*
    exit
    ```   
    
9. Update using the official repositories
   ```
   sudo apt-get update
   ```
   ```
   sudo apt-get install gitlab-ce
   ```
   ```
   sudo gitlab-ctl reconfigure
   ```
10. Deleting data, sometimes a "ghost" user appears, to delete it:
   ```
   sudo gitlab-rails console
   ```
    
   ```
   user = User.find_by(username: "ghost")
   User.delete(user.id)
   ```   
    If the user is removed then output would be 1, if 0 then user is not removed.

References:  
[12] https://packages.gitlab.com/gitlab/gitlab-ce  
[13] https://lindevs.com/reset-gitlab-ce-root-password-in-linux   
[14] https://gridscale.io/en/community/tutorials/hostname-fqdn-ubuntu/   
[15] https://gitlab.com/gitlab-org/omnibus-gitlab/-/issues/4166   
[16] https://stackoverflow.com/questions/44673257/how-to-delete-ghost-user-on-gitlab


## 7. Install Gitlab - Docker:

1. Run:
   ```
   docker run \
   --detach \
   --restart always \
   --name gitlab-ce \
   --privileged \
   --memory 4096M \
   --publish 22:22 \
   --publish 80:80 \
   --publish 443:443 \
   --env GITLAB_OMNIBUS_CONFIG="\
   external_url 'http://localhost' \
   nginx['redirect_http_to_https'] = true; \
   grafana['enable'] = true" \
   --volume /srv/gitlab-ce/conf:/etc/gitlab:z \
   --volume /srv/gitlab-ce/logs:/var/log/gitlab:z \
   --volume /srv/gitlab-ce/data:/var/opt/gitlab:z \
   --network=host \
   yrzr/gitlab-ce-arm64v8:latest
   ```
2. Set ```root``` password:
   ```
   docker exec -it gitlab-ce gitlab-rake 'gitlab:password:reset[root]'
   ```
3. Some helper functions in case of need to change configurations:   

3.1 Docker:   

   ```docker kill gitlab-ce``` # terminates the container.  
   ```docker rm gitlab-ce``` # removes the container.  
   ```docker ps``` # shows running containers.  
   
3.2 Gitlab:   

   ```docker exec -it gitlab-ce editor /etc/gitlab/gitlab.rb``` # edit configurations.  
   ```docker exec -it gitlab-ce gitlab-ctl reconfigure``` # reconfigure changes.  
   
3.3 Vim (To edit configurations):   

   ```i```   Start insert mode at/after cursor.  
   ```Esc```	Exit insert mode.  
   ```dd``` 	Delete line.  
   ```:wq```	Write (save) and quit.  
   ```:q!```	Quit and throw away changes.  
   ```/pattern```	Search for pattern.  
   ```n```	 	Repeat search in same direction.  
