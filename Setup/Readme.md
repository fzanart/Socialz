# Install Gitlab - Docker:
1. For Docker installation, just follow the [official guide](https://docs.docker.com/engine/install/ubuntu/)  

2. Run: `docker pull yrzr/gitlab-ce-arm64v8` # Lastest gitlab version for ARM64
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
  --publish 9090:9090 \
  --env GITLAB_OMNIBUS_CONFIG=" \
    external_url 'http://localhost';
    node_exporter['enable'] = true;
    grafana['enable'] = true;
    prometheus['listen_address'] = '0.0.0.0:9090';
    gitlab_rails['monitoring_whitelist'] = ['127.0.0.0/8', '::1/128', '192.168.0.1', '0.0.0.0/0'];
    nginx['redirect_http_to_https'] = true; "\
  --volume /srv/gitlab-ce/conf:/etc/gitlab:z \
  --volume /srv/gitlab-ce/logs:/var/log/gitlab:z \
  --volume /srv/gitlab-ce/data:/var/opt/gitlab:z \
  yrzr/gitlab-ce-arm64v8:latest
```
3. Set root password:
```
docker exec -it gitlab-ce gitlab-rake 'gitlab:password:reset[root]'
```

4. Some helper functions in case of need to change configurations:   

4.1 Docker:
```
docker kill gitlab-ce # terminates the container.
docker rm gitlab-ce # removes the container.
sudo rm -r /srv/gitlab-ce/ # removes data.
docker ps # shows running containers.
```
4.2 Gitlab:

Trying to reach prometheus endpoint, the only thing that worked so far is:   
uncomment `prometheus['listen_address'] = '0.0.0.0:9090'`  
add this line too to access \-\metrics endopoint: `gitlab_rails['monitoring_whitelist'] = ['127.0.0.0/8', '::1/128', '192.168.0.1', '0.0.0.0/0']`  

```
sudo docker logs -f gitlab # check logs.
docker exec -it gitlab-ce editor /etc/gitlab/gitlab.rb # edit configurations.
docker exec -it gitlab-ce gitlab-ctl reconfigure # reconfigure changes.
```
4.3 Vim (To edit configurations):
```
i Start insert mode at/after cursor.
Esc Exit insert mode.
dd Delete line.
:wq Write (save) and quit.
:q! Quit and throw away changes.
/pattern Search for pattern.
n Repeat search in same direction.
```
