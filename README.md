# Upload Service

This is simple upload service for uploading files to the server. It is written in Python 3.10 and uses Flask framework.

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