# Upload Service

This is simple upload service for uploading files to the server. It is written in Python 3.10 and uses Flask framework
as a backend and HTMX for interactive UI.

## GitHub Application
In order to make authentication work, you need to [create](https://github.com/settings/developers) GitHub application.

The only scope is required is a `user:email` scope.

To run application locally you need to set callback URL to `http://localhost:8000/login/authorized`.

## Development

This project built using poetry. To start development, you need to install poetry.
Also, you need to create environment file. You can use `.env.example` as a template.
    
```bash
cp env.example .env
```

Install dependencies and run the project:

```bash
poetry install --no-root
poetry run upload-service
```

## Docker
To run application in docker container, you need to build it first.

### Using nix
If you are running ARM64 system, consider replace `x86_64-linux` with `aarch64-linux` or `aarch64-darwin` in the following command.

```bash
nix build .#dockerImage.x86_64-linux
docker load < result
```

### Using docker
```bash
docker build -t upload-service .
```

### Running
To run resulted image use the following command:
```bash
mkdir -p uploads
docker run --env-file .env -p 8000:8000 -v ./uploads:/uploads upload-service:<imagetag>
```

## Caveats and something to improve

- [ ] No coordination (locks) on disk operations. It is possible to get a race condition between two requests
- [ ] No API design
- [ ] More things to parametrize via environment variables
- [ ] No size limit for uploaded files
- [ ] Not all possible errors are handled
- [ ] Need background task for cleaning up temporary files
- [ ] API handler to persist temporary uploads
- [ ] Could be reimplemented using async framework
- [ ] Could be reimplemented using some other storage (like S3)
- [ ] Static assets are better to be served by nginx or CDN

## Deployment options

The most universal way to deploy this application is to use docker. You can use docker-compose or kubernetes to deploy.
Also, various cloud providers have their own deployment tools, like Fargate in AWS.

But this application could also be packaged as a python wheel and be deployed alongside with other WSGI application servers

Since this application does not maintain any database schema it could be easily updated
by just replacing docker image or python wheel.

## API
API contains two endpoints for uploading files:

- `/api/upload` - synchronous persistent upload
- `/api/upload_temporary` - temporary upload

Second hanlder is usually used for uploading files to be latter attached to some form.
You might create form with file upload control. And start uploading file without even sending form.
But after file being uploaded, you replace file control with hidden input and set its value to the token
you got from temporary upload handler. Then you submit the form and server will persist file in permanent
with all required metadata.

```bash
curl -X PUT http://localhost:8000/api/upload_temporary -H "Authorization: Bearer <github token>" -H "Content-type: application/json" -d "[{\"filename\": \"README.md\", \"content\": \"$(base64 -w 0 README.md)\"}]"
```

```bash
curl -X PUT http://localhost:8000/api/upload -H "Authorization: Bearer <github token>" -H "Content-type: application/json" -d "[{\"filename\": \"README.md\", \"content\": \"$(base64 -w 0 README.md)\"}]"
```