# Quote attachment upload limit

The API validates a maximum of 250 MiB per quote attachment. The reverse proxy
must accept the file plus multipart headers, so its request limit is 251 MiB.

Copy `management-projet-upload-limits.inc` into the shared nginx configuration
directory. Include it once inside each of these HTTPS server blocks:

- `management-projet.elbouazzatiholding.ma`
- `management-projet-api.elbouazzatiholding.ma`

```nginx
include /etc/nginx/conf.d/management-projet-upload-limits.inc;
```

Replace any existing `client_max_body_size` directive at that server scope.
Keep other applications unchanged. Back up the existing configuration, run
`docker exec nginx nginx -t`, then reload with `docker exec nginx nginx -s reload`.

Django's 20 MiB upload memory threshold remains unchanged: larger multipart files
are spooled to disk and validated against the separate 250 MiB file-size limit.
