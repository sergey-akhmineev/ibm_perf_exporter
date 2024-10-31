# IBM Performance Exporter

## Overview

The **IBM Performance Exporter** is a metrics exporter that aggregates and exports performance metrics from IBM XIV storage systems to Prometheus and VictoriaMetrics. This exporter connects to the IBM XIV using SSH, collects the necessary metrics, and exposes them in a Prometheus-compatible format through port 8000.

## Features

- **SSH Connectivity**: Securely connects to IBM XIV storage systems to gather performance data.
- **Metrics Exporting**: Exports collected metrics to Prometheus and VictoriaMetrics, providing insight into the storage system's performance.
- **Dockerized Environment**: Easily deployable via Docker, ensuring consistency across different environments.

## Getting Started

### Prerequisites

- Docker installed on your machine.
- `docker-compose` installed.
- Access to an IBM XIV storage system.

### Running the Exporter

To start the IBM Performance Exporter, follow these steps:

1. Clone this repository to your local machine.

bash
   git clone https://github.com/yourusername/ibm_perf_exporter.git
   cd ibm_perf_exporter

2. Create a `docker-compose.yml` file with the following content:

yaml
   version: '3.8'

   services:
     ibm_perf_exporter:
       build: .
       container_name: ibm_perf_exporter
       volumes:
         - iostats-data:/app/iostats
       ports:
         - "8000:8000"
       restart: unless-stopped
   
   volumes:
     iostats-data:
   
3. Build and start the Docker container using Docker Compose:

bash
   docker-compose up -d

4. Verify that the exporter is running and metrics are being served by accessing:

http://localhost:8000/metrics


### Configuration

You may need to configure SSH access to your IBM XIV storage system. Ensure that the credentials and permissions are correctly set up in your environment for the exporter to function properly.

## Accessing Metrics

The metrics will be exposed on port 8000, and you can scrape them from your Prometheus or VictoriaMetrics instances by adding the following configuration to your Prometheus configuration file (`prometheus.yml`):

yaml
scrape_configs:
  - job_name: 'ibm_perf_exporter'
    static_configs:
      - targets: ['localhost:8000']

  

## Contributing

Contributions are welcome! Please create an issue or submit a pull request for any enhancements or bug fixes.